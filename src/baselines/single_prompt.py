"""Baseline `single_prompt` — una sola llamada a Claude, sin tools ni framework.

Construye un prompt masivo con (1) toda la información de las interacciones
de entrada y (2) instrucciones para analizarlas, agruparlas y generar
artículos KCS en un único turno. Sin function calling, sin loops de revisión,
sin verificación posterior por LLM (sólo `validate_article` local opcional
sobre la salida para reportar in is_valid en traces).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

from src.tools.tool_contract import get_interaction, validate_article


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Carga de configuración
# ---------------------------------------------------------------------------


def _load_budget() -> Dict[str, Any]:
    with open(
        _PROJECT_ROOT / "configs" / "experiments" / "budget.yaml", "r", encoding="utf-8"
    ) as f:
        return yaml.safe_load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _client() -> Anthropic:
    load_dotenv(_PROJECT_ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY no está definido en .env")
    return Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """Eres un editor sénior de la base de conocimiento de Davivienda Colombia.
Tu trabajo es leer un lote de interacciones reales de WhatsApp Business con clientes
y producir, en UNA SOLA salida JSON, todos los artículos de KB que corresponda
generar — decidiendo tú mismo cómo agrupar las interacciones por tema.

## Contexto
- Banco: Davivienda Colombia. Audiencia: persona natural.
- Canales: App Davivienda, Davivienda en Línea (web), DaviPlata, Línea de
  Atención, oficinas, cajeros.
- Productos: cuentas, tarjetas crédito/débito, créditos de consumo, hipotecarios,
  transferencias (ACH, Bre-b), pagos de servicios, SOAT, seguros, CDTs.

## Heurísticas para agrupar interacciones
- Dos interacciones van al MISMO grupo si tratan el mismo problema funcional,
  mismo producto y comparten ≥ 2 hechos clave.
- Dos interacciones van a grupos DISTINTOS si una es FAQ y otra how-to, o si
  tratan productos diferentes.
- Si una interacción es única en el lote, forma su propio grupo de un solo ID.

## Estilo de redacción
- Vocabulario del cliente (sin jerga interna del banco).
- Pasos imperativos con canal y opción literal de la UI cuando aplique.
- Cita cada afirmación verificable en `evidence_pack.claim_evidence_map`.
- CERO PII (cédulas, emails, celulares, tarjetas). Reescribe si la fuente la trae.

## Plantilla KCS por artículo
{
  "title": "≤ 150 caracteres",
  "environment": {"product": "...", "segment": "Banca Personal", "version": "2024"},
  "problem": "...",
  "cause": null | "...",
  "resolution": ["1. ...", "2. ...", ...],
  "evidence_pack": {
    "interaction_ids": ["INT-...", ...],
    "key_fragments": ["fragmento literal o casi literal", ...],
    "claim_evidence_map": {"afirmación": ["INT-..."], ...}
  },
  "metadata": {
    "status": "draft",
    "author": "baseline-single-prompt",
    "confidence": "low" | "medium" | "high",
    "created_at": "YYYY-MM-DD"
  }
}

## Formato de salida
Devuelve EXCLUSIVAMENTE un objeto JSON con esta estructura:
{
  "articles": [<artículo KCS>, <artículo KCS>, ...],
  "groupings": [
    {"article_index": 0, "interaction_ids": ["INT-...", ...]},
    ...
  ]
}

`groupings[i].interaction_ids` debe ser exactamente igual a
`articles[i].evidence_pack.interaction_ids` y los índices deben corresponder
1:1 con la posición del artículo en el array `articles`. Sin texto fuera del JSON.
"""


def _summarize_interaction(interaction: Dict[str, Any]) -> Dict[str, Any]:
    """Resumen compacto por interacción para no inflar el prompt."""
    meta = interaction.get("metadata", {}) or {}
    ke = interaction.get("knowledge_extracted", {}) or {}
    turns = []
    for t in interaction.get("turns", []) or []:
        msg = (t.get("message") or "").strip()
        if not msg:
            continue
        turns.append({"role": t.get("role"), "message": msg[:300]})
    return {
        "interaction_id": interaction["interaction_id"],
        "product_category": meta.get("product_category"),
        "product_specific": meta.get("product_specific"),
        "query_type": meta.get("query_type"),
        "severity": meta.get("severity"),
        "gap_topic": meta.get("gap_topic"),
        "main_topic": ke.get("main_topic"),
        "key_facts": ke.get("key_facts", []),
        "turns": turns,
    }


def _build_user_message(interactions: List[Dict[str, Any]]) -> str:
    payload = [_summarize_interaction(i) for i in interactions]
    return (
        "## Lote a procesar\n\n"
        f"Recibes {len(payload)} interacciones reales del corpus de WhatsApp "
        "Davivienda. Agrúpalas y genera los artículos KCS correspondientes en "
        "una sola salida JSON.\n\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n"
    )


# ---------------------------------------------------------------------------
# Parseo de JSON tolerante
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("respuesta vacía")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError(f"No se encontró JSON parseable en: {text[:300]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_single_prompt(
    interaction_ids: List[str], auto_approve: bool = True
) -> Dict[str, Any]:
    """Una sola llamada a Claude para todo el lote. Mismo contrato de retorno."""
    started = time.time()
    traces: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    articles: List[Dict[str, Any]] = []
    article_interaction_map: Dict[str, List[str]] = {}
    aborted_reason: Optional[str] = None

    budget = _load_budget()
    model_cfg = budget["model"]
    pricing = budget["pricing"][model_cfg["name"]]

    # ---- carga ----
    interactions: List[Dict[str, Any]] = []
    for iid in interaction_ids:
        try:
            out = get_interaction(iid)
            interactions.append(out["interaction"])
        except Exception as e:  # noqa: BLE001
            errors.append(
                {
                    "phase": "ingest_batch",
                    "interaction_id": iid,
                    "error": str(e),
                    "ts": _now_iso(),
                }
            )
    traces.append(
        {
            "phase": "ingest_batch",
            "type": "phase_complete",
            "loaded": len(interactions),
            "requested": len(interaction_ids),
            "ts": _now_iso(),
        }
    )

    tokens_in = 0
    tokens_out = 0
    cache_read = 0
    cache_create = 0

    if not interactions:
        aborted_reason = "no_interactions_loaded"
    else:
        try:
            client = _client()
            resp = client.messages.create(
                model=model_cfg["name"],
                max_tokens=model_cfg["max_tokens"],
                temperature=model_cfg["temperature"],
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": "user", "content": _build_user_message(interactions)}
                ],
            )
            tokens_in = int(getattr(resp.usage, "input_tokens", 0) or 0)
            tokens_out = int(getattr(resp.usage, "output_tokens", 0) or 0)
            cache_create = int(
                getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
            )
            cache_read = int(getattr(resp.usage, "cache_read_input_tokens", 0) or 0)

            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            )
            traces.append(
                {
                    "phase": "single_call",
                    "type": "llm_response",
                    "stop_reason": resp.stop_reason,
                    "raw_preview": text[:400],
                    "ts": _now_iso(),
                }
            )

            parsed = _extract_json(text)
            if not isinstance(parsed, dict):
                raise ValueError("la respuesta no es un objeto JSON")
            raw_articles = parsed.get("articles") or []
            groupings = parsed.get("groupings") or []
            # índice → interaction_ids
            grouping_by_idx: Dict[int, List[str]] = {}
            for g in groupings:
                if not isinstance(g, dict):
                    continue
                idx = g.get("article_index")
                ids = g.get("interaction_ids") or []
                if isinstance(idx, int):
                    grouping_by_idx[idx] = [i for i in ids if isinstance(i, str)]

            for i, art in enumerate(raw_articles):
                if not isinstance(art, dict):
                    errors.append(
                        {
                            "phase": "parse_output",
                            "article_index": i,
                            "error": "articulo_no_es_dict",
                            "ts": _now_iso(),
                        }
                    )
                    continue
                # Fuerza metadata.created_at si el modelo lo omitió o usó otro formato.
                md = art.setdefault("metadata", {})
                md.setdefault("status", "draft")
                md.setdefault("author", "baseline-single-prompt")
                md.setdefault("confidence", "low")
                md.setdefault("created_at", date.today().isoformat())

                article_id = f"ART-{len(articles) + 1:03d}"
                # interaction_ids: prefer groupings, fallback evidence_pack.
                ids = grouping_by_idx.get(i)
                if not ids:
                    ev = art.get("evidence_pack") or {}
                    ids = [
                        x
                        for x in (ev.get("interaction_ids") or [])
                        if isinstance(x, str)
                    ]
                articles.append(
                    {
                        "article_id": article_id,
                        "unit_id": f"G-SP-{i + 1:03d}",
                        "topic": art.get("title", "Sin título"),
                        "article": art,
                    }
                )
                article_interaction_map[article_id] = ids or []

                # validación local (informativa, no bloqueante)
                try:
                    v = validate_article(art)
                    traces.append(
                        {
                            "phase": "validate",
                            "type": "validation_result",
                            "article_id": article_id,
                            "is_valid": v["is_valid"],
                            "errors": len(v["errors"]),
                            "pii_findings": len(v["pii_findings"]),
                            "ts": _now_iso(),
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    errors.append(
                        {
                            "phase": "validate",
                            "article_id": article_id,
                            "error": str(e),
                            "ts": _now_iso(),
                        }
                    )

        except Exception as e:  # noqa: BLE001
            aborted_reason = f"unhandled_error: {type(e).__name__}: {e}"
            errors.append(
                {"phase": "single_call", "error": str(e), "ts": _now_iso()}
            )

    elapsed = round(time.time() - started, 3)
    fresh_input = max(tokens_in - cache_read, 0)
    cost = (
        fresh_input * pricing["input_per_mtok"]
        + tokens_out * pricing["output_per_mtok"]
        + cache_create * pricing["cache_write_per_mtok"]
        + cache_read * pricing["cache_read_per_mtok"]
    ) / 1_000_000

    metrics = {
        "total_time_seconds": elapsed,
        "total_tokens_in": tokens_in,
        "total_tokens_out": tokens_out,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_create,
        "total_tool_calls": 0,
        "cost_usd": round(cost, 6),
        "revision_cycles": 0,
        "articles_generated": len(articles),
    }

    if aborted_reason:
        errors.append({"reason": aborted_reason, "ts": _now_iso()})

    return {
        "articles": articles,
        "article_interaction_map": article_interaction_map,
        "traces": traces,
        "metrics": metrics,
        "errors": errors,
        "aborted": aborted_reason is not None,
    }

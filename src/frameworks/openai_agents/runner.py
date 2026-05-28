"""Orquestación del prototipo OpenAI Agents SDK.

# Decisión de diseño (relevante para la tesis)
-------------------------------------------------
El OpenAI Agents SDK (paquete `openai-agents`) está diseñado para modelos
OpenAI por defecto. Para mantener la variable de control del experimento
(Claude `claude-sonnet-4-6` igual para los 3 frameworks) se evaluaron
tres caminos:

1. **Adapter LiteLLM oficial del SDK** — `agents.extensions.models.litellm_model.LitellmModel`,
   que enchufa cualquier proveedor soportado por LiteLLM (Anthropic, Gemini,
   Bedrock, etc.) al runtime del SDK. **Esta es la opción adoptada**: usamos
   `LitellmModel(model="anthropic/claude-sonnet-4-6")` como `model`
   de cada `Agent`. Conserva la maquinaria nativa del SDK (function tools,
   tracing, guardrails, handoffs) y permite la comparación directa con los
   prototipos de LangGraph y CrewAI sin re-implementar el paradigma.
2. Implementar un adapter custom contra `Anthropic()` directamente.
3. Simular el patrón de handoffs sobre el SDK de Anthropic, sin SDK de agentes.

La opción 1 fue suficiente y la más limpia. La diferencia con los otros dos
frameworks queda aislada al runtime de orquestación, no al modelo subyacente
ni al protocolo de tools.

## Orquestación
4 Agents nativos del SDK (analyzer, generator, verifier, governance) más una
topología de handoffs orquestada explícitamente en Python: igual que en
LangGraph (edges deterministas) y CrewAI (tasks secuenciales) — esto evita
que el LLM decida cuándo cortar el bucle de revisión y permite presupuesto
duro de 3 revisiones por unidad.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import load_dotenv

from agents import Agent, Runner, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel

from src.frameworks.openai_agents.tools import RUN_STATE, reset_run_state, tools_for


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Carga de configuración
# ---------------------------------------------------------------------------


def load_budget() -> Dict[str, Any]:
    with open(
        _PROJECT_ROOT / "configs" / "experiments" / "budget.yaml", "r", encoding="utf-8"
    ) as f:
        return yaml.safe_load(f)


def load_prompt(name: str) -> Dict[str, Any]:
    with open(
        _PROJECT_ROOT / "configs" / "prompts" / "v1" / f"system_{name}.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        return yaml.safe_load(f)


def _ensure_api_key() -> None:
    load_dotenv(_PROJECT_ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY no está definido en .env")


def _configure_litellm_retries() -> None:
    """Activa reintentos en LiteLLM para errores transitorios (529 overloaded, etc.)."""
    try:
        import litellm

        litellm.num_retries = 3
        litellm.request_timeout = 120
    except ImportError:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("respuesta vacía")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    import re

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
# Construcción del modelo y los agentes
# ---------------------------------------------------------------------------


def _build_model(model_cfg: Dict[str, Any]) -> LitellmModel:
    return LitellmModel(
        model=f"anthropic/{model_cfg['name']}",
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )


def _build_agents(
    model: LitellmModel, prompts: Dict[str, Dict[str, Any]]
) -> Dict[str, Agent]:
    """Crea los 4 agentes con instrucciones tomadas de configs/prompts/v1.

    No se enlazan handoffs nativos del SDK: la transición entre agentes la
    decide el runner en Python (ver docstring del módulo).
    """
    analyzer = Agent(
        name="Knowledge Analyst",
        instructions=prompts["analyzer"]["system"],
        model=model,
        tools=tools_for(
            ["search_interactions", "list_interactions", "extract_knowledge"]
        ),
        handoff_description=(
            "Analiza interacciones de WhatsApp Davivienda y las agrupa en "
            "unidades de conocimiento."
        ),
    )
    generator = Agent(
        name="KB Article Writer",
        instructions=prompts["generator"]["system"],
        model=model,
        tools=tools_for(
            ["extract_knowledge", "get_interaction", "check_pii", "validate_article"]
        ),
        handoff_description="Genera el borrador KCS a partir de una unidad de conocimiento.",
    )
    verifier = Agent(
        name="Quality Reviewer",
        instructions=prompts["critic"]["system"],
        model=model,
        tools=tools_for(["validate_article", "check_pii", "get_interaction"]),
        handoff_description="Verifica calidad del borrador y emite veredicto.",
    )
    governance = Agent(
        name="Final Editor",
        instructions=prompts["governance"]["system"],
        model=model,
        tools=tools_for(["get_interaction", "validate_article", "check_pii"]),
        handoff_description="Empaqueta evidencia y prepara el artículo para revisión humana.",
    )
    return {
        "analyzer": analyzer,
        "generator": generator,
        "verifier": verifier,
        "governance": governance,
    }


# ---------------------------------------------------------------------------
# Tracking de usage
# ---------------------------------------------------------------------------


class UsageAccumulator:
    """Acumula usage de todos los Runner.run que se ejecutan en una corrida."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self.requests = 0

    def add(self, result_usage) -> None:
        if result_usage is None:
            return
        self.input_tokens += int(getattr(result_usage, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(result_usage, "output_tokens", 0) or 0)
        details = getattr(result_usage, "input_tokens_details", None)
        if details is not None:
            self.cached_input_tokens += int(
                getattr(details, "cached_tokens", 0) or 0
            )
        self.requests += int(getattr(result_usage, "requests", 0) or 0)


# ---------------------------------------------------------------------------
# Resumen ligero por interacción
# ---------------------------------------------------------------------------


def _summarize_interaction(interaction: Dict[str, Any]) -> Dict[str, Any]:
    meta = interaction.get("metadata", {}) or {}
    ke = interaction.get("knowledge_extracted", {}) or {}
    first_client = ""
    for t in interaction.get("turns", []) or []:
        if t.get("role") == "cliente":
            first_client = (t.get("message") or "")[:200]
            break
    return {
        "interaction_id": interaction["interaction_id"],
        "product_category": meta.get("product_category"),
        "product_specific": meta.get("product_specific"),
        "query_type": meta.get("query_type"),
        "severity": meta.get("severity"),
        "gap_topic": meta.get("gap_topic"),
        "main_topic": ke.get("main_topic"),
        "article_type": ke.get("article_type"),
        "key_facts": ke.get("key_facts", []),
        "first_client_message": first_client,
    }


# ---------------------------------------------------------------------------
# Fases del pipeline
# ---------------------------------------------------------------------------


async def _phase_analyze(
    agent: Agent, interactions: List[Dict[str, Any]], usage: UsageAccumulator
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    summaries = [_summarize_interaction(i) for i in interactions]
    user_input = (
        "## Lote a analizar\n\n"
        f"Recibes el resumen de {len(summaries)} interacciones reales. Aplica las "
        "heurísticas de tu system prompt para agruparlas en unidades de "
        "conocimiento. Usa tus tools cuando necesites más detalle o quieras "
        "confirmar similitud.\n\n"
        "```json\n"
        + json.dumps(summaries, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Devuelve EXCLUSIVAMENTE el JSON con `groups` y `summary` (sin texto extra)."
    )
    result = await Runner.run(agent, input=user_input, max_turns=12)
    usage.add(result.context_wrapper.usage)
    raw = str(result.final_output or "")
    trace = {
        "type": "phase_complete",
        "phase": "analyze",
        "raw_preview": raw[:400],
        "ts": _now_iso(),
    }
    try:
        parsed = _extract_json(raw)
        groups = parsed.get("groups", []) if isinstance(parsed, dict) else []
    except Exception as e:  # noqa: BLE001
        groups = []
        trace["parse_error"] = str(e)
    return groups, trace


async def _phase_write(
    agent: Agent,
    unit: Dict[str, Any],
    feedback: Optional[str],
    revision: int,
    usage: UsageAccumulator,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    knowledge = unit.get("knowledge", {})
    feedback_block = (
        ("\n\n## Feedback del revisor anterior — DEBES CORREGIR:\n" + feedback)
        if feedback
        else ""
    )
    user_input = (
        f"## Unidad de conocimiento (revisión #{revision})\n"
        f"- Tema: {unit.get('topic')}\n"
        f"- Tipo: {unit.get('query_type')}\n"
        f"- Producto: {unit.get('product_category')}\n"
        f"- Fuentes: {', '.join(unit.get('interaction_ids', []))}\n\n"
        "## Hechos ya extraídos\n```json\n"
        + json.dumps(knowledge, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Genera el artículo KCS completo en JSON, siguiendo el output_schema "
        "de tu system prompt. Puedes usar `get_interaction` o `check_pii` antes "
        "de entregar. Devuelve EXCLUSIVAMENTE el JSON del artículo."
        + feedback_block
    )
    result = await Runner.run(agent, input=user_input, max_turns=12)
    usage.add(result.context_wrapper.usage)
    raw = str(result.final_output or "")
    trace = {
        "type": "phase_complete",
        "phase": "write",
        "revision": revision,
        "raw_preview": raw[:400],
        "ts": _now_iso(),
    }
    try:
        draft = _extract_json(raw)
        if not isinstance(draft, dict):
            raise ValueError("draft no es objeto JSON")
    except Exception as e:  # noqa: BLE001
        draft = None
        trace["parse_error"] = str(e)
    return draft, trace


async def _phase_review(
    agent: Agent, draft: Dict[str, Any], usage: UsageAccumulator
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    user_input = (
        "## Artículo KCS a revisar\n```json\n"
        + json.dumps(draft, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Evalúa las 5 dimensiones de tu system prompt (1-5 cada una), invoca "
        "`validate_article` y `check_pii`, y produce el veredicto JSON con "
        "`approved`, `scores`, `feedback`, `blocking_issues`, "
        "`checked_with_tools`. Sin texto fuera del JSON."
    )
    result = await Runner.run(agent, input=user_input, max_turns=10)
    usage.add(result.context_wrapper.usage)
    raw = str(result.final_output or "")
    trace = {
        "type": "phase_complete",
        "phase": "review",
        "raw_preview": raw[:400],
        "ts": _now_iso(),
    }
    try:
        verdict = _extract_json(raw)
        if not isinstance(verdict, dict):
            raise ValueError("review no es objeto JSON")
        verdict.setdefault("approved", False)
    except Exception as e:  # noqa: BLE001
        verdict = {
            "approved": False,
            "scores": {},
            "feedback": [],
            "blocking_issues": [f"review_parse_failed: {e}"],
            "feedback_text": str(e),
        }
        trace["parse_error"] = str(e)
    return verdict, trace


async def _phase_governance(
    agent: Agent,
    draft: Dict[str, Any],
    unit: Dict[str, Any],
    usage: UsageAccumulator,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    user_input = (
        "## Artículo aprobado por el revisor\n```json\n"
        + json.dumps(draft, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        f"Fuentes del grupo: {', '.join(unit.get('interaction_ids', []))}\n\n"
        "Verifica que `evidence_pack.claim_evidence_map` cubre cada afirmación "
        "verificable. Si encuentras una afirmación sin mapeo, AGRÉGALA al mapa "
        "(usa `get_interaction` para confirmar). NO modifiques otros campos. "
        "Devuelve el artículo final en JSON, idéntico al original salvo por "
        "refuerzos al claim_evidence_map y/o key_fragments."
    )
    result = await Runner.run(agent, input=user_input, max_turns=8)
    usage.add(result.context_wrapper.usage)
    raw = str(result.final_output or "")
    trace = {
        "type": "phase_complete",
        "phase": "governance",
        "raw_preview": raw[:400],
        "ts": _now_iso(),
    }
    final = draft
    try:
        candidate = _extract_json(raw)
        if isinstance(candidate, dict) and "title" in candidate:
            final = candidate
        else:
            trace["parse_warning"] = "governance_output_no_es_articulo_completo"
    except Exception as e:  # noqa: BLE001
        trace["parse_error"] = str(e)
    return final, trace


# ---------------------------------------------------------------------------
# Construcción de unidades
# ---------------------------------------------------------------------------


def _build_knowledge_units(
    groups: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    from src.tools.tool_contract import extract_knowledge as _ek

    units: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for g in groups:
        ids = [i for i in g.get("interaction_ids", []) if isinstance(i, str)]
        if not ids:
            continue
        try:
            knowledge = _ek(ids)
            units.append(
                {
                    "group_id": g.get("group_id"),
                    "topic": g.get("topic"),
                    "interaction_ids": ids,
                    "product_category": g.get("product_category"),
                    "query_type": g.get("query_type"),
                    "priority": g.get("priority"),
                    "rationale": g.get("rationale"),
                    "knowledge": knowledge,
                }
            )
        except Exception as e:  # noqa: BLE001
            errors.append(
                {
                    "phase": "build_units",
                    "group_id": g.get("group_id"),
                    "interaction_ids": ids,
                    "error": str(e),
                    "ts": _now_iso(),
                }
            )
    return units, errors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run_async(
    interaction_ids: List[str], auto_approve: bool
) -> Dict[str, Any]:
    _ensure_api_key()
    _configure_litellm_retries()
    # Sin tracing remoto: el SDK lo intenta enviar a OpenAI por defecto.
    set_tracing_disabled(True)

    budget = load_budget()
    model_cfg = budget["model"]
    pricing = budget["pricing"][model_cfg["name"]]
    max_tool_calls = budget["budget"]["max_tool_calls"]
    max_cost_usd = budget["budget"]["max_cost_usd"]
    timeout_seconds = budget["budget"]["timeout_seconds"]
    max_revisions = 3

    reset_run_state(max_tool_calls=max_tool_calls)
    prompts = {n: load_prompt(n) for n in ("analyzer", "generator", "critic", "governance")}
    model = _build_model(model_cfg)
    agents = _build_agents(model, prompts)
    usage = UsageAccumulator()

    started = time.time()
    articles: List[Dict[str, Any]] = []
    article_interaction_map: Dict[str, List[str]] = {}
    errors: List[Dict[str, Any]] = []
    traces: List[Dict[str, Any]] = []
    aborted_reason: Optional[str] = None
    revision_cycles = 0

    def _estimated_cost() -> float:
        fresh_in = max(usage.input_tokens - usage.cached_input_tokens, 0)
        return (
            fresh_in * pricing["input_per_mtok"]
            + usage.output_tokens * pricing["output_per_mtok"]
            + usage.cached_input_tokens * pricing["cache_read_per_mtok"]
        ) / 1_000_000

    def _check_global_budget() -> Optional[str]:
        if RUN_STATE["budget_exceeded"]:
            return "max_tool_calls_excedido"
        elapsed = time.time() - started
        if elapsed > timeout_seconds:
            return f"timeout_seconds_excedido: {elapsed:.1f}s"
        if _estimated_cost() > max_cost_usd:
            return f"max_cost_usd_excedido: ${_estimated_cost():.4f}"
        return None

    try:
        # ---- ingest_batch ----
        from src.tools.tool_contract import get_interaction as _gi

        interactions: List[Dict[str, Any]] = []
        for iid in interaction_ids:
            try:
                out = _gi(iid)
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
                "type": "phase_complete",
                "phase": "ingest_batch",
                "loaded": len(interactions),
                "requested": len(interaction_ids),
                "ts": _now_iso(),
            }
        )

        if not interactions:
            aborted_reason = "no_interactions_loaded"
        else:
            # ---- analyze ----
            reason = _check_global_budget()
            if reason:
                aborted_reason = reason
            else:
                groups, t = await _phase_analyze(
                    agents["analyzer"], interactions, usage
                )
                traces.append(t)

                units, build_errors = _build_knowledge_units(groups)
                errors.extend(build_errors)

                # Fallback: singletons si analyzer falla.
                if not units and interactions:
                    fb = []
                    for inter in interactions:
                        fb.append(
                            {
                                "group_id": f"G-FALLBACK-{inter['interaction_id'][-3:]}",
                                "topic": (inter.get("knowledge_extracted") or {}).get(
                                    "main_topic", "Tema sin nombre"
                                ),
                                "interaction_ids": [inter["interaction_id"]],
                                "product_category": (inter.get("metadata") or {}).get(
                                    "product_category"
                                ),
                                "query_type": (inter.get("metadata") or {}).get(
                                    "query_type"
                                ),
                                "priority": "media",
                                "rationale": "Fallback: el analyzer no produjo agrupaciones.",
                            }
                        )
                    units, more_errs = _build_knowledge_units(fb)
                    errors.extend(more_errs)
                    traces.append(
                        {
                            "type": "fallback_to_singleton_groups",
                            "count": len(units),
                            "ts": _now_iso(),
                        }
                    )

                # ---- write → review → governance por unidad ----
                for idx, unit in enumerate(units):
                    reason = _check_global_budget()
                    if reason:
                        aborted_reason = reason
                        break

                    feedback: Optional[str] = None
                    approved = False
                    final_draft: Optional[Dict[str, Any]] = None
                    last_verdict: Dict[str, Any] = {}

                    for revision in range(max_revisions + 1):
                        reason = _check_global_budget()
                        if reason:
                            aborted_reason = reason
                            break
                        draft, write_trace = await _phase_write(
                            agents["generator"], unit, feedback, revision, usage
                        )
                        traces.append(write_trace)
                        if not isinstance(draft, dict):
                            feedback = (
                                "El borrador anterior no fue parseable como JSON. "
                                "Devuelve EXCLUSIVAMENTE el objeto JSON del artículo."
                            )
                            revision_cycles += 1
                            continue

                        verdict, review_trace = await _phase_review(
                            agents["verifier"], draft, usage
                        )
                        traces.append(review_trace)
                        last_verdict = verdict

                        if verdict.get("approved"):
                            approved = True
                            final_draft = draft
                            break

                        feedback_lines: List[str] = []
                        for fb in verdict.get("feedback", []) or []:
                            if isinstance(fb, dict):
                                feedback_lines.append(
                                    f"- [{fb.get('field', '?')}] "
                                    f"{fb.get('message', '')} "
                                    f"(fix: {fb.get('suggested_fix', '-')})"
                                )
                        for bi in verdict.get("blocking_issues", []) or []:
                            feedback_lines.append(f"- [blocking] {bi}")
                        feedback = (
                            "\n".join(feedback_lines)
                            or "El revisor rechazó sin detalles. Reescribe asegurando "
                            "exactitud y consistencia con la plantilla."
                        )
                        revision_cycles += 1

                    if aborted_reason:
                        break

                    if not approved or final_draft is None:
                        errors.append(
                            {
                                "phase": "review_loop",
                                "unit_idx": idx,
                                "group_id": unit.get("group_id"),
                                "reason": "max_revisions_or_unapproved",
                                "last_verdict": last_verdict,
                                "ts": _now_iso(),
                            }
                        )
                        traces.append(
                            {
                                "type": "article_dropped",
                                "unit_idx": idx,
                                "ts": _now_iso(),
                            }
                        )
                        continue

                    # ---- governance ----
                    reason = _check_global_budget()
                    if reason:
                        aborted_reason = reason
                        break
                    edited, gov_trace = await _phase_governance(
                        agents["governance"], final_draft, unit, usage
                    )
                    traces.append(gov_trace)

                    # ---- human review (auto) ----
                    if not auto_approve:
                        raise NotImplementedError(
                            "human_review manual no está implementado en este prototipo."
                        )
                    traces.append(
                        {
                            "type": "auto_approved",
                            "unit_idx": idx,
                            "ts": _now_iso(),
                        }
                    )

                    article_id = f"ART-{len(articles) + 1:03d}"
                    record = {
                        "article_id": article_id,
                        "unit_id": unit.get("group_id"),
                        "topic": unit.get("topic"),
                        "article": edited,
                    }
                    articles.append(record)
                    article_interaction_map[article_id] = unit.get(
                        "interaction_ids", []
                    )
                    traces.append(
                        {
                            "type": "article_finalized",
                            "article_id": article_id,
                            "unit_idx": idx,
                            "ts": _now_iso(),
                        }
                    )

    except Exception as e:  # noqa: BLE001
        aborted_reason = f"unhandled_error: {type(e).__name__}: {e}"

    elapsed = round(time.time() - started, 3)
    cost = _estimated_cost()
    metrics = {
        "total_time_seconds": elapsed,
        "total_tokens_in": usage.input_tokens,
        "total_tokens_out": usage.output_tokens,
        "cache_read_tokens": usage.cached_input_tokens,
        "cache_creation_tokens": 0,  # No expuesto por LitellmModel
        "total_tool_calls": RUN_STATE["tool_calls"],
        "cost_usd": round(cost, 6),
        "revision_cycles": revision_cycles,
        "articles_generated": len(articles),
        "successful_requests": usage.requests,
    }

    all_traces = sorted(traces + RUN_STATE["traces"], key=lambda t: t.get("ts", ""))
    all_errors = errors + list(RUN_STATE["errors"])
    if aborted_reason:
        all_errors.append({"reason": aborted_reason, "ts": _now_iso()})

    return {
        "articles": articles,
        "article_interaction_map": article_interaction_map,
        "traces": all_traces,
        "metrics": metrics,
        "errors": all_errors,
        "aborted": aborted_reason is not None,
    }


def run_openai_agents(
    interaction_ids: List[str], auto_approve: bool = True
) -> Dict[str, Any]:
    """Punto de entrada síncrono. Internamente orquesta `Runner.run` async."""
    return asyncio.run(_run_async(interaction_ids, auto_approve))

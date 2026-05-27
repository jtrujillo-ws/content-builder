"""Nodos del grafo LangGraph para el Content Builder."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.frameworks.langgraph.llm import (
    call_claude_with_tools,
    extract_json,
    load_prompt,
)
from src.frameworks.langgraph.state import ContentBuilderState
from src.tools.tool_contract import (
    check_pii,
    extract_knowledge,
    get_interaction,
    validate_article,
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
# Nodos
# ---------------------------------------------------------------------------


def ingest_batch(state: ContentBuilderState) -> Dict[str, Any]:
    cfg = state["config"]
    ids: List[str] = cfg["interaction_ids"]
    interactions: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for iid in ids:
        try:
            out = get_interaction(iid)
            interactions.append(out["interaction"])
        except Exception as e:  # noqa: BLE001
            errors.append(
                {
                    "node": "ingest_batch",
                    "interaction_id": iid,
                    "error": str(e),
                    "ts": _now_iso(),
                }
            )

    update: Dict[str, Any] = {
        "interactions": interactions,
        "traces": [
            {
                "node": "ingest_batch",
                "type": "node_complete",
                "ts": _now_iso(),
                "loaded": len(interactions),
                "requested": len(ids),
            }
        ],
    }
    if errors:
        update["errors"] = errors
    return update


def analyze_and_cluster(state: ContentBuilderState) -> Dict[str, Any]:
    prompt = load_prompt("analyzer")
    system_prompt = prompt["system"]
    inputs = [_summarize_interaction(i) for i in state["interactions"]]
    user_message = (
        "## Lote a analizar\n\n"
        "A continuación recibes el resumen de "
        f"{len(inputs)} interacciones reales de WhatsApp Davivienda. Agrúpalas "
        "según las heurísticas del system prompt y devuelve el JSON solicitado.\n\n"
        "Si necesitas más detalle de alguna, usa la tool `get_interaction`. "
        "Si quieres confirmar similitud con otras interacciones del corpus, usa "
        "`search_interactions`.\n\n"
        "```json\n"
        + json.dumps(inputs, ensure_ascii=False, indent=2)
        + "\n```\n"
    )

    text, local_traces = call_claude_with_tools(
        state, system_prompt, user_message, node_name="analyze_and_cluster"
    )

    errors: List[Dict[str, Any]] = []
    units: List[Dict[str, Any]] = []
    try:
        parsed = extract_json(text)
        groups = parsed.get("groups", []) if isinstance(parsed, dict) else []
        for g in groups:
            ids = [i for i in g.get("interaction_ids", []) if isinstance(i, str)]
            if not ids:
                continue
            knowledge = extract_knowledge(ids)
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
                "node": "analyze_and_cluster",
                "error": f"parse_failed: {e}",
                "raw_preview": text[:400],
                "ts": _now_iso(),
            }
        )

    # Fallback: si el analyzer no produjo grupos válidos, agrupar cada interacción sola.
    if not units and state["interactions"]:
        for inter in state["interactions"]:
            iid = inter["interaction_id"]
            units.append(
                {
                    "group_id": f"G-FALLBACK-{iid[-3:]}",
                    "topic": (inter.get("knowledge_extracted") or {}).get(
                        "main_topic", "Tema sin nombre"
                    ),
                    "interaction_ids": [iid],
                    "product_category": (inter.get("metadata") or {}).get(
                        "product_category"
                    ),
                    "query_type": (inter.get("metadata") or {}).get("query_type"),
                    "priority": "media",
                    "rationale": "Fallback: el analyzer no produjo agrupaciones válidas.",
                    "knowledge": extract_knowledge([iid]),
                }
            )
        errors.append(
            {
                "node": "analyze_and_cluster",
                "warning": "fallback_to_singleton_groups",
                "ts": _now_iso(),
            }
        )

    update: Dict[str, Any] = {
        "knowledge_units": units,
        "current_unit_index": 0,
        "revision_count": 0,
        "traces": local_traces
        + [
            {
                "node": "analyze_and_cluster",
                "type": "node_complete",
                "ts": _now_iso(),
                "groups_produced": len(units),
            }
        ],
    }
    if errors:
        update["errors"] = errors
    return update


def generate_article(state: ContentBuilderState) -> Dict[str, Any]:
    prompt = load_prompt("generator")
    system_prompt = prompt["system"]
    idx = state["current_unit_index"]
    unit = state["knowledge_units"][idx]
    feedback = state.get("last_feedback") or ""

    user_parts = [
        "## Unidad de conocimiento a redactar\n",
        f"- Tema: {unit.get('topic')}\n",
        f"- Tipo de artículo sugerido: {unit.get('query_type')}\n",
        f"- Producto: {unit.get('product_category')}\n",
        f"- Prioridad: {unit.get('priority')}\n",
        f"- Interacciones fuente: {', '.join(unit.get('interaction_ids', []))}\n\n",
        "## Hechos extraídos (extract_knowledge)\n```json\n"
        + json.dumps(unit.get("knowledge", {}), ensure_ascii=False, indent=2)
        + "\n```\n\n",
        "Genera el artículo KCS completo en JSON, siguiendo el output_schema. "
        "Si necesitas releer una interacción puedes usar `get_interaction`. "
        "Antes de entregar, llama `check_pii` sobre cada campo de texto y "
        "`validate_article` sobre el JSON completo; corrige hasta que ambos pasen.\n",
    ]
    if feedback:
        user_parts.append(
            "\n## Feedback del revisor anterior (debes corregir):\n" + feedback + "\n"
        )

    text, local_traces = call_claude_with_tools(
        state,
        system_prompt,
        "".join(user_parts),
        node_name="generate_article",
    )

    errors: List[Dict[str, Any]] = []
    draft = None
    try:
        draft = extract_json(text)
    except Exception as e:  # noqa: BLE001
        errors.append(
            {
                "node": "generate_article",
                "unit_idx": idx,
                "error": f"parse_failed: {e}",
                "raw_preview": text[:400],
                "ts": _now_iso(),
            }
        )

    update: Dict[str, Any] = {
        "current_draft": draft,
        "traces": local_traces
        + [
            {
                "node": "generate_article",
                "type": "node_complete",
                "unit_idx": idx,
                "revision": state.get("revision_count", 0),
                "draft_title": (draft or {}).get("title") if isinstance(draft, dict) else None,
                "ts": _now_iso(),
            }
        ],
    }
    if errors:
        update["errors"] = errors
    return update


def verify_article(state: ContentBuilderState) -> Dict[str, Any]:
    idx = state["current_unit_index"]
    draft = state.get("current_draft")

    # Sin borrador parseable: rechazo inmediato.
    if not isinstance(draft, dict):
        verdict = {
            "approved": False,
            "stage": "structural",
            "blocking_issues": ["draft_no_disponible_o_no_parseable"],
            "feedback_text": "El generador no produjo un JSON parseable.",
        }
        return {
            "last_verification": verdict,
            "last_feedback": verdict["feedback_text"],
            "traces": [
                {
                    "node": "verify_article",
                    "type": "hard_rejected",
                    "unit_idx": idx,
                    "ts": _now_iso(),
                    "verdict": verdict,
                }
            ],
        }

    # Reglas duras: validate_article + check_pii.
    val = validate_article(draft)
    if not val["is_valid"]:
        feedback_lines = ["Errores duros de validate_article:"]
        for e in val["errors"]:
            feedback_lines.append(f"- [{e['field']}] {e['message']}")
        feedback_text = "\n".join(feedback_lines)
        verdict = {
            "approved": False,
            "stage": "structural",
            "validate_article": val,
            "blocking_issues": [e["message"] for e in val["errors"]],
            "feedback_text": feedback_text,
        }
        return {
            "last_verification": verdict,
            "last_feedback": feedback_text,
            "traces": [
                {
                    "node": "verify_article",
                    "type": "hard_rejected",
                    "unit_idx": idx,
                    "errors_count": len(val["errors"]),
                    "pii_count": len(val["pii_findings"]),
                    "ts": _now_iso(),
                }
            ],
        }

    # Pasa reglas duras: invocar critic.
    prompt = load_prompt("critic")
    system_prompt = prompt["system"]
    user_message = (
        "## Artículo KCS a revisar\n```json\n"
        + json.dumps(draft, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Las interacciones fuente son: "
        f"{', '.join(draft.get('evidence_pack', {}).get('interaction_ids', []))}. "
        "Usa `get_interaction` y `extract_knowledge` para verificar exactitud, "
        "y `validate_article` para consistencia. Devuelve el JSON del veredicto.\n"
    )
    text, local_traces = call_claude_with_tools(
        state, system_prompt, user_message, node_name="verify_article"
    )

    errors: List[Dict[str, Any]] = []
    critic_verdict: Dict[str, Any]
    try:
        critic_verdict = extract_json(text)
        if not isinstance(critic_verdict, dict):
            raise ValueError("critic no devolvió un objeto JSON")
        critic_verdict.setdefault("approved", False)
        critic_verdict["stage"] = "critic"
        critic_verdict["validate_article"] = val
    except Exception as e:  # noqa: BLE001
        errors.append(
            {
                "node": "verify_article",
                "unit_idx": idx,
                "error": f"critic_parse_failed: {e}",
                "raw_preview": text[:400],
                "ts": _now_iso(),
            }
        )
        critic_verdict = {
            "approved": False,
            "stage": "critic",
            "blocking_issues": ["critic_parse_failed"],
            "feedback_text": "El revisor automático no produjo un JSON parseable.",
            "validate_article": val,
        }

    feedback_text = critic_verdict.get("feedback_text")
    if not feedback_text:
        fb_items = critic_verdict.get("feedback", []) or []
        feedback_text = "\n".join(
            f"- [{f.get('field', '?')}] ({f.get('severity', '?')}) {f.get('message', '')}"
            for f in fb_items
            if isinstance(f, dict)
        )
    if not feedback_text:
        feedback_text = "Sin feedback explícito."

    update: Dict[str, Any] = {
        "last_verification": critic_verdict,
        "last_feedback": feedback_text,
        "traces": local_traces
        + [
            {
                "node": "verify_article",
                "type": "critic_complete",
                "unit_idx": idx,
                "approved": bool(critic_verdict.get("approved")),
                "scores": critic_verdict.get("scores"),
                "ts": _now_iso(),
            }
        ],
    }
    if errors:
        update["errors"] = errors
    return update


def human_review(state: ContentBuilderState) -> Dict[str, Any]:
    cfg = state["config"]
    auto_approve = bool(cfg.get("auto_approve", True))
    idx = state["current_unit_index"]

    if not auto_approve:
        # Hook para integración real. En este prototipo no está cableado.
        raise NotImplementedError(
            "human_review en modo manual no está implementado en el prototipo."
        )

    return {
        "traces": [
            {
                "node": "human_review",
                "type": "auto_approved",
                "unit_idx": idx,
                "ts": _now_iso(),
            }
        ]
    }


def finalize(state: ContentBuilderState) -> Dict[str, Any]:
    idx = state["current_unit_index"]
    units = state["knowledge_units"]
    unit = units[idx] if idx < len(units) else {}
    verdict = state.get("last_verification") or {}
    draft = state.get("current_draft")

    metrics = dict(state.get("metrics", {}))
    metrics["revision_cycles"] = (
        metrics.get("revision_cycles", 0) + state.get("revision_count", 0)
    )

    update: Dict[str, Any] = {
        "current_unit_index": idx + 1,
        "current_draft": None,
        "revision_count": 0,
        "last_verification": None,
        "last_feedback": None,
        "metrics": metrics,
    }

    if verdict.get("approved") and isinstance(draft, dict):
        article_id = f"ART-{idx + 1:03d}"
        article_record = {
            "article_id": article_id,
            "unit_id": unit.get("group_id"),
            "topic": unit.get("topic"),
            "article": draft,
        }
        update["generated_articles"] = [article_record]
        update["article_interaction_map"] = {
            **state.get("article_interaction_map", {}),
            article_id: unit.get("interaction_ids", []),
        }
        update["traces"] = [
            {
                "node": "finalize",
                "type": "article_finalized",
                "unit_idx": idx,
                "article_id": article_id,
                "ts": _now_iso(),
            }
        ]
    else:
        update["errors"] = [
            {
                "node": "finalize",
                "unit_idx": idx,
                "reason": "max_revisions_or_unapproved",
                "verdict": verdict,
                "ts": _now_iso(),
            }
        ]
        update["traces"] = [
            {
                "node": "finalize",
                "type": "article_dropped",
                "unit_idx": idx,
                "ts": _now_iso(),
            }
        ]

    return update


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


def route_after_verify(state: ContentBuilderState) -> str:
    verdict = state.get("last_verification") or {}
    if verdict.get("approved"):
        return "human_review"
    if state.get("revision_count", 0) >= state["config"]["max_revisions"]:
        return "finalize"
    return "regenerate"


def increment_revision(state: ContentBuilderState) -> Dict[str, Any]:
    """Nodo trivial: incrementa revision_count antes de volver a generate."""
    return {
        "revision_count": state.get("revision_count", 0) + 1,
        "traces": [
            {
                "node": "increment_revision",
                "type": "revision_bumped",
                "to": state.get("revision_count", 0) + 1,
                "ts": _now_iso(),
            }
        ],
    }


def route_after_finalize(state: ContentBuilderState) -> str:
    if state["current_unit_index"] >= len(state.get("knowledge_units", [])):
        return "end"
    return "generate_article"

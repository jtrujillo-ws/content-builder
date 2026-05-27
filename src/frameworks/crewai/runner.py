"""Orquestación de la Crew (4 agentes) y punto de entrada run_crewai.

Mantiene paridad funcional con `src/frameworks/langgraph/graph.py::run_langgraph`:
mismo formato de retorno, mismas métricas y mismos límites de presupuesto.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from crewai import LLM, Agent, Crew, Process, Task
from dotenv import load_dotenv

from src.frameworks.crewai.tools import (
    RUN_STATE,
    build_tools,
    reset_run_state,
)


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    # fence ```json ... ```
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
# Construcción del LLM y los 4 agentes
# ---------------------------------------------------------------------------


def _build_llm(model_cfg: Dict[str, Any]) -> LLM:
    return LLM(
        model=f"anthropic/{model_cfg['name']}",
        temperature=model_cfg["temperature"],
        max_tokens=model_cfg["max_tokens"],
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )


def _build_agents(llm: LLM, prompts: Dict[str, Dict[str, Any]]) -> Dict[str, Agent]:
    investigador = Agent(
        role="Knowledge Analyst",
        goal=(
            "Detectar patrones recurrentes en interacciones de WhatsApp Davivienda "
            "y agruparlas en unidades de conocimiento mínimas y específicas."
        ),
        backstory=prompts["analyzer"]["system"],
        tools=build_tools(
            ["search_interactions", "list_interactions", "extract_knowledge"]
        ),
        llm=llm,
        verbose=False,
        max_iter=8,
        allow_delegation=False,
    )
    escritor = Agent(
        role="KB Article Writer",
        goal=(
            "Redactar artículos KCS accionables a partir de una unidad de "
            "conocimiento, usando vocabulario del cliente y citando fuentes."
        ),
        backstory=prompts["generator"]["system"],
        tools=build_tools(["extract_knowledge", "get_interaction"]),
        llm=llm,
        verbose=False,
        max_iter=8,
        allow_delegation=False,
    )
    revisor = Agent(
        role="Quality Reviewer",
        goal=(
            "Evaluar la calidad de un artículo KCS, contrastarlo contra la "
            "evidencia y emitir un veredicto approved/rejected con feedback."
        ),
        backstory=prompts["critic"]["system"],
        tools=build_tools(["validate_article", "check_pii", "get_interaction"]),
        llm=llm,
        verbose=False,
        max_iter=8,
        allow_delegation=False,
    )
    editor = Agent(
        role="Final Editor",
        goal=(
            "Verificar que el evidence_pack mapea cada afirmación verificable a "
            "interacciones fuente, y preparar el artículo para revisión humana."
        ),
        backstory=prompts["governance"]["system"],
        tools=build_tools(["get_interaction"]),
        llm=llm,
        verbose=False,
        max_iter=6,
        allow_delegation=False,
    )
    return {
        "investigador": investigador,
        "escritor": escritor,
        "revisor": revisor,
        "editor": editor,
    }


# ---------------------------------------------------------------------------
# Resumen ligero por interacción (para evitar inflar prompts)
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


def _phase_analyze(
    agents: Dict[str, Agent], interactions: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    summaries = [_summarize_interaction(i) for i in interactions]
    desc = (
        "## Lote a analizar\n\n"
        "Recibes el resumen de "
        f"{len(summaries)} interacciones reales de WhatsApp Davivienda. "
        "Agrúpalas siguiendo las heurísticas de tu backstory. Usa tus tools "
        "(`search_interactions`, `list_interactions`, `extract_knowledge`) "
        "para desambiguar cuando sea necesario.\n\n"
        "Datos del lote:\n```json\n"
        + json.dumps(summaries, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Devuelve EXCLUSIVAMENTE el JSON con `groups` y `summary` según el "
        "output_schema. Sin texto fuera del JSON."
    )
    task = Task(
        description=desc,
        agent=agents["investigador"],
        expected_output=(
            "JSON con la forma {\"groups\": [...], \"summary\": {...}}. Cada "
            "grupo contiene group_id, topic, interaction_ids, priority, rationale."
        ),
    )
    crew = Crew(
        agents=[agents["investigador"]],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    output = crew.kickoff()
    raw = str(output.raw if hasattr(output, "raw") else output)

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


def _phase_write(
    agents: Dict[str, Agent],
    unit: Dict[str, Any],
    feedback: Optional[str],
    revision: int,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    knowledge = unit.get("knowledge", {})
    feedback_block = (
        ("\n\n## Feedback del revisor anterior — DEBES CORREGIR:\n" + feedback)
        if feedback
        else ""
    )
    desc = (
        f"## Unidad de conocimiento (revisión #{revision})\n"
        f"- Tema: {unit.get('topic')}\n"
        f"- Tipo: {unit.get('query_type')}\n"
        f"- Producto: {unit.get('product_category')}\n"
        f"- Fuentes: {', '.join(unit.get('interaction_ids', []))}\n\n"
        "## Hechos ya extraídos\n```json\n"
        + json.dumps(knowledge, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Redacta el artículo KCS completo siguiendo el output_schema de tu "
        "backstory. Puedes usar `get_interaction` si necesitas releer alguna "
        "fuente literalmente. Cita cada afirmación verificable en "
        "`evidence_pack.claim_evidence_map`."
        + feedback_block
        + "\n\nDevuelve EXCLUSIVAMENTE el JSON del artículo KCS."
    )
    task = Task(
        description=desc,
        agent=agents["escritor"],
        expected_output=(
            "JSON con title, environment, problem, cause, resolution, "
            "evidence_pack (con interaction_ids, key_fragments, "
            "claim_evidence_map) y metadata (status, author, confidence, created_at)."
        ),
    )
    crew = Crew(
        agents=[agents["escritor"]],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    output = crew.kickoff()
    raw = str(output.raw if hasattr(output, "raw") else output)
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


def _phase_review(
    agents: Dict[str, Agent], draft: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    desc = (
        "## Artículo KCS a revisar\n```json\n"
        + json.dumps(draft, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "Evalúa las 5 dimensiones de tu backstory (1-5 cada una), llama "
        "`validate_article` y `check_pii`, y produce el veredicto JSON con "
        "`approved`, `scores`, `feedback`, `blocking_issues` y "
        "`checked_with_tools`. Sin texto fuera del JSON."
    )
    task = Task(
        description=desc,
        agent=agents["revisor"],
        expected_output=(
            "JSON con approved (bool), scores (5 dimensiones), feedback (lista), "
            "blocking_issues (lista), checked_with_tools (lista)."
        ),
    )
    crew = Crew(
        agents=[agents["revisor"]],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    output = crew.kickoff()
    raw = str(output.raw if hasattr(output, "raw") else output)
    trace = {
        "type": "phase_complete",
        "phase": "review",
        "raw_preview": raw[:400],
        "ts": _now_iso(),
    }
    verdict: Dict[str, Any]
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
            "feedback_text": f"El revisor no devolvió JSON parseable: {e}",
        }
        trace["parse_error"] = str(e)
    return verdict, trace


def _phase_edit(
    agents: Dict[str, Agent], draft: Dict[str, Any], unit: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    desc = (
        "## Artículo aprobado por el revisor\n```json\n"
        + json.dumps(draft, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        f"Fuentes del grupo: {', '.join(unit.get('interaction_ids', []))}\n\n"
        "Como editor final, verifica que `evidence_pack.claim_evidence_map` "
        "cubre cada afirmación verificable. Si encuentras una afirmación sin "
        "mapeo claro, AGRÉGALA al mapa citando los interaction_ids correctos "
        "(usa `get_interaction` para confirmar). NO modifiques otros campos del "
        "artículo. Devuelve el artículo final en JSON, idéntico al original "
        "salvo por mejoras al claim_evidence_map y/o key_fragments."
    )
    task = Task(
        description=desc,
        agent=agents["editor"],
        expected_output="JSON del artículo final, con el evidence_pack reforzado.",
    )
    crew = Crew(
        agents=[agents["editor"]],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    output = crew.kickoff()
    raw = str(output.raw if hasattr(output, "raw") else output)
    trace = {
        "type": "phase_complete",
        "phase": "edit",
        "raw_preview": raw[:400],
        "ts": _now_iso(),
    }
    final = draft  # fallback
    try:
        candidate = _extract_json(raw)
        if isinstance(candidate, dict) and "title" in candidate:
            final = candidate
        else:
            trace["parse_warning"] = "editor_output_no_es_articulo_completo"
    except Exception as e:  # noqa: BLE001
        trace["parse_error"] = str(e)
    return final, trace


# ---------------------------------------------------------------------------
# Carga de unidades de conocimiento (anexa knowledge a cada grupo)
# ---------------------------------------------------------------------------


def _build_knowledge_units(
    groups: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    from src.tools.tool_contract import extract_knowledge as _extract_knowledge

    units: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for g in groups:
        ids = [i for i in g.get("interaction_ids", []) if isinstance(i, str)]
        if not ids:
            continue
        try:
            knowledge = _extract_knowledge(ids)
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
# Punto de entrada
# ---------------------------------------------------------------------------


def run_crewai(
    interaction_ids: List[str], auto_approve: bool = True
) -> Dict[str, Any]:
    """Ejecuta el pipeline CrewAI sobre un lote y devuelve el mismo formato que
    `run_langgraph`: {articles, article_interaction_map, traces, metrics, errors,
    aborted}.
    """
    _ensure_api_key()
    budget = load_budget()
    model_cfg = budget["model"]
    pricing = budget["pricing"][model_cfg["name"]]
    max_tool_calls = budget["budget"]["max_tool_calls"]
    max_cost_usd = budget["budget"]["max_cost_usd"]
    timeout_seconds = budget["budget"]["timeout_seconds"]
    max_revisions = 3

    reset_run_state(max_tool_calls=max_tool_calls)

    prompts = {
        n: load_prompt(n) for n in ("analyzer", "generator", "critic", "governance")
    }

    llm = _build_llm(model_cfg)
    agents = _build_agents(llm, prompts)

    started = time.time()
    articles: List[Dict[str, Any]] = []
    article_interaction_map: Dict[str, List[str]] = {}
    errors: List[Dict[str, Any]] = []
    traces: List[Dict[str, Any]] = []
    aborted_reason: Optional[str] = None
    revision_cycles = 0

    def _check_global_budget() -> Optional[str]:
        if RUN_STATE["budget_exceeded"]:
            return "max_tool_calls_excedido"
        elapsed = time.time() - started
        if elapsed > timeout_seconds:
            return f"timeout_seconds_excedido: {elapsed:.1f}s"
        # Cost estimation (parcial, se recalcula al final también)
        usage = llm.get_token_usage_summary()
        est_cost = (
            (usage.prompt_tokens - usage.cached_prompt_tokens)
            * pricing["input_per_mtok"]
            + usage.completion_tokens * pricing["output_per_mtok"]
            + usage.cached_prompt_tokens * pricing["cache_read_per_mtok"]
        ) / 1_000_000
        if est_cost > max_cost_usd:
            return f"max_cost_usd_excedido: ${est_cost:.4f}"
        return None

    try:
        # ---- ingest_batch ----
        interactions: List[Dict[str, Any]] = []
        from src.tools.tool_contract import get_interaction as _get_interaction

        for iid in interaction_ids:
            try:
                out = _get_interaction(iid)
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
                groups, analyze_trace = _phase_analyze(agents, interactions)
                traces.append(analyze_trace)

                # Fallback: si analyzer no produjo grupos, agrupar como singletons.
                units, build_errors = _build_knowledge_units(groups)
                errors.extend(build_errors)
                if not units and interactions:
                    fallback_groups = []
                    for inter in interactions:
                        fallback_groups.append(
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
                    units, build_errors = _build_knowledge_units(fallback_groups)
                    errors.extend(build_errors)
                    traces.append(
                        {
                            "type": "fallback_to_singleton_groups",
                            "count": len(units),
                            "ts": _now_iso(),
                        }
                    )

                # ---- write → review → edit por unidad ----
                for idx, unit in enumerate(units):
                    reason = _check_global_budget()
                    if reason:
                        aborted_reason = reason
                        break

                    feedback: Optional[str] = None
                    approved = False
                    final_draft: Optional[Dict[str, Any]] = None
                    verdict: Dict[str, Any] = {}

                    for revision in range(max_revisions + 1):
                        reason = _check_global_budget()
                        if reason:
                            aborted_reason = reason
                            break
                        draft, write_trace = _phase_write(
                            agents, unit, feedback, revision
                        )
                        traces.append(write_trace)
                        if not isinstance(draft, dict):
                            feedback = (
                                "El borrador anterior no fue parseable como JSON. "
                                "Devuelve EXCLUSIVAMENTE el objeto JSON del artículo."
                            )
                            revision_cycles += 1
                            continue

                        verdict, review_trace = _phase_review(agents, draft)
                        traces.append(review_trace)

                        if verdict.get("approved"):
                            approved = True
                            final_draft = draft
                            break

                        # Reglas duras desde validate_article (si el revisor las trajo)
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
                            or "El revisor rechazó sin detalles concretos. "
                            "Reescribe asegurando exactitud y consistencia con la plantilla."
                        )
                        revision_cycles += 1

                    if not approved or final_draft is None:
                        errors.append(
                            {
                                "phase": "review_loop",
                                "unit_idx": idx,
                                "group_id": unit.get("group_id"),
                                "reason": "max_revisions_or_unapproved",
                                "last_verdict": verdict,
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

                    # ---- edit (editor final) ----
                    reason = _check_global_budget()
                    if reason:
                        aborted_reason = reason
                        break
                    edited, edit_trace = _phase_edit(agents, final_draft, unit)
                    traces.append(edit_trace)

                    # ---- human_review ----
                    if not auto_approve:
                        raise NotImplementedError(
                            "human_review manual no está implementado en el prototipo."
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

    # ---- métricas finales ----
    elapsed = round(time.time() - started, 3)
    usage = llm.get_token_usage_summary()
    prompt_tokens = int(usage.prompt_tokens or 0)
    cached_prompt_tokens = int(usage.cached_prompt_tokens or 0)
    completion_tokens = int(usage.completion_tokens or 0)
    # Tokens "frescos" de entrada = prompt - cached
    fresh_input = max(prompt_tokens - cached_prompt_tokens, 0)
    cost_usd = (
        fresh_input * pricing["input_per_mtok"]
        + completion_tokens * pricing["output_per_mtok"]
        + cached_prompt_tokens * pricing["cache_read_per_mtok"]
    ) / 1_000_000

    metrics = {
        "total_time_seconds": elapsed,
        "total_tokens_in": prompt_tokens,
        "total_tokens_out": completion_tokens,
        "cache_read_tokens": cached_prompt_tokens,
        "cache_creation_tokens": 0,  # CrewAI no expone este split
        "total_tool_calls": RUN_STATE["tool_calls"],
        "cost_usd": round(cost_usd, 6),
        "revision_cycles": revision_cycles,
        "articles_generated": len(articles),
        "successful_requests": int(usage.successful_requests or 0),
    }

    # Mezcla trazas de tools (RUN_STATE) con trazas de fases en orden temporal.
    all_traces = sorted(
        traces + RUN_STATE["traces"], key=lambda t: t.get("ts", "")
    )
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

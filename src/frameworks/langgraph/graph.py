"""Composición del StateGraph y punto de entrada run_langgraph."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from src.frameworks.langgraph.llm import BudgetExceeded, load_budget
from src.frameworks.langgraph.nodes import (
    analyze_and_cluster,
    finalize,
    generate_article,
    human_review,
    ingest_batch,
    increment_revision,
    route_after_finalize,
    route_after_verify,
    verify_article,
)
from src.frameworks.langgraph.state import ContentBuilderState


def build_graph():
    """Construye y compila el StateGraph."""
    builder = StateGraph(ContentBuilderState)

    builder.add_node("ingest_batch", ingest_batch)
    builder.add_node("analyze_and_cluster", analyze_and_cluster)
    builder.add_node("generate_article", generate_article)
    builder.add_node("verify_article", verify_article)
    builder.add_node("increment_revision", increment_revision)
    builder.add_node("human_review", human_review)
    builder.add_node("finalize", finalize)

    builder.set_entry_point("ingest_batch")
    builder.add_edge("ingest_batch", "analyze_and_cluster")
    builder.add_edge("analyze_and_cluster", "generate_article")
    builder.add_edge("generate_article", "verify_article")

    builder.add_conditional_edges(
        "verify_article",
        route_after_verify,
        {
            "human_review": "human_review",
            "regenerate": "increment_revision",
            "finalize": "finalize",
        },
    )
    builder.add_edge("increment_revision", "generate_article")
    builder.add_edge("human_review", "finalize")

    builder.add_conditional_edges(
        "finalize",
        route_after_finalize,
        {
            "generate_article": "generate_article",
            "end": END,
        },
    )

    return builder.compile()


def _initial_state(
    interaction_ids: List[str],
    *,
    auto_approve: bool,
    budget: Dict[str, Any],
) -> ContentBuilderState:
    model_cfg = budget["model"]
    pricing = budget["pricing"][model_cfg["name"]]
    cfg = {
        "interaction_ids": list(interaction_ids),
        "auto_approve": auto_approve,
        "max_revisions": 3,
        "max_tool_calls": budget["budget"]["max_tool_calls"],
        "timeout_seconds": budget["budget"]["timeout_seconds"],
        "max_cost_usd": budget["budget"]["max_cost_usd"],
        "model_name": model_cfg["name"],
        "temperature": model_cfg["temperature"],
        "max_tokens": model_cfg["max_tokens"],
        "pricing": pricing,
    }
    metrics: Dict[str, Any] = {
        "_started_at": time.time(),
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_tool_calls": 0,
        "cost_usd": 0.0,
        "revision_cycles": 0,
    }
    return {
        "interactions": [],
        "knowledge_units": [],
        "current_unit_index": 0,
        "current_draft": None,
        "revision_count": 0,
        "generated_articles": [],
        "article_interaction_map": {},
        "traces": [],
        "errors": [],
        "metrics": metrics,
        "config": cfg,
        "last_verification": None,
        "last_feedback": None,
    }


def run_langgraph(
    interaction_ids: List[str],
    auto_approve: bool = True,
) -> Dict[str, Any]:
    """Ejecuta el pipeline completo sobre el lote y devuelve el resumen.

    Returns:
        dict con: articles, article_interaction_map, traces, metrics, errors.
    """
    budget = load_budget()
    initial = _initial_state(
        interaction_ids, auto_approve=auto_approve, budget=budget
    )
    graph = build_graph()

    started = time.time()
    final_state: ContentBuilderState
    aborted_reason = None

    try:
        final_state = graph.invoke(
            initial,
            config={"recursion_limit": 200},
        )
    except BudgetExceeded as e:
        aborted_reason = f"budget_exceeded: {e}"
        final_state = initial  # type: ignore[assignment]
    except Exception as e:  # noqa: BLE001
        aborted_reason = f"unhandled_error: {e}"
        final_state = initial  # type: ignore[assignment]

    elapsed = time.time() - started
    metrics = dict(final_state.get("metrics", {}))
    metrics.pop("_started_at", None)
    metrics["total_time_seconds"] = round(elapsed, 3)
    metrics["articles_generated"] = len(final_state.get("generated_articles", []))
    metrics["cost_usd"] = round(metrics.get("cost_usd", 0.0), 6)

    return {
        "articles": final_state.get("generated_articles", []),
        "article_interaction_map": final_state.get("article_interaction_map", {}),
        "traces": final_state.get("traces", []),
        "metrics": metrics,
        "errors": final_state.get("errors", [])
        + ([{"reason": aborted_reason}] if aborted_reason else []),
        "aborted": aborted_reason is not None,
    }

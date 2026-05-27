"""Wrappers de las 6 herramientas del tool contract al formato function_tool
del OpenAI Agents SDK.

Comparten un RUN_STATE por-corrida igual que el wrapper de CrewAI: counter
de tool calls, traza estructurada y aplicación de presupuesto.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents import function_tool

from src.tools.tool_contract import (
    check_pii as _check_pii,
    extract_knowledge as _extract_knowledge,
    get_interaction as _get_interaction,
    list_interactions as _list_interactions,
    search_interactions as _search_interactions,
    validate_article as _validate_article,
)


# ---------------------------------------------------------------------------
# Estado por corrida — reset en cada run_openai_agents.
# ---------------------------------------------------------------------------

RUN_STATE: Dict[str, Any] = {
    "tool_calls": 0,
    "max_tool_calls": 50,
    "budget_exceeded": False,
    "traces": [],
    "errors": [],
}


def reset_run_state(max_tool_calls: int = 50) -> None:
    RUN_STATE["tool_calls"] = 0
    RUN_STATE["max_tool_calls"] = max_tool_calls
    RUN_STATE["budget_exceeded"] = False
    RUN_STATE["traces"] = []
    RUN_STATE["errors"] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record(entry: Dict[str, Any]) -> None:
    entry.setdefault("ts", _now_iso())
    RUN_STATE["traces"].append(entry)


def _execute(name: str, fn, kwargs: Dict[str, Any]) -> str:
    """Lógica común a todas las tools: cuenta llamadas, aplica presupuesto,
    serializa el resultado y registra trazas.
    """
    if RUN_STATE["budget_exceeded"]:
        return "Error: presupuesto de tool calls excedido. No invoques más tools."

    RUN_STATE["tool_calls"] += 1
    if RUN_STATE["tool_calls"] > RUN_STATE["max_tool_calls"]:
        RUN_STATE["budget_exceeded"] = True
        _record(
            {"type": "budget_exceeded", "tool": name, "tool_calls": RUN_STATE["tool_calls"]}
        )
        return (
            f"Error: se alcanzó el límite de {RUN_STATE['max_tool_calls']} "
            "tool calls. Detente y produce tu mejor respuesta con lo que tienes."
        )

    try:
        result = fn(**kwargs)
        payload = json.dumps(result, ensure_ascii=False, default=str)
        _record(
            {
                "type": "tool_call",
                "tool": name,
                "input": kwargs,
                "is_error": False,
                "result_preview": payload[:300],
            }
        )
        return payload
    except Exception as e:  # noqa: BLE001
        msg = f"Error ejecutando {name}: {e}"
        _record(
            {
                "type": "tool_call",
                "tool": name,
                "input": kwargs,
                "is_error": True,
                "result_preview": msg[:300],
            }
        )
        RUN_STATE["errors"].append(
            {"tool": name, "input": kwargs, "error": str(e), "ts": _now_iso()}
        )
        return msg


# ---------------------------------------------------------------------------
# function_tool wrappers
# ---------------------------------------------------------------------------


@function_tool(strict_mode=False)
def search_interactions(query: str, k: int = 10) -> str:
    """Búsqueda semántica multilingüe sobre el corpus de WhatsApp Davivienda.

    Args:
        query: Consulta en lenguaje natural (español).
        k: Número máximo de resultados (1-50).
    """
    return _execute("search_interactions", _search_interactions, {"query": query, "k": k})


@function_tool(strict_mode=False)
def get_interaction(interaction_id: str) -> str:
    """Devuelve la interacción completa por ID, con el nombre del cliente enmascarado.

    Args:
        interaction_id: Identificador con formato INT-YYYY-NNN.
    """
    return _execute(
        "get_interaction", _get_interaction, {"interaction_id": interaction_id}
    )


@function_tool(strict_mode=False)
def extract_knowledge(interaction_ids: List[str]) -> str:
    """Combina los hechos documentables (knowledge_extracted) de varias interacciones.

    Args:
        interaction_ids: Lista de IDs INT-YYYY-NNN a combinar.
    """
    return _execute(
        "extract_knowledge", _extract_knowledge, {"interaction_ids": interaction_ids}
    )


@function_tool(strict_mode=False)
def validate_article(article_json: Dict[str, Any]) -> str:
    """Valida un artículo contra la plantilla KCS: estructura, longitudes, PII.

    Args:
        article_json: Objeto JSON del artículo KCS a validar.
    """
    return _execute(
        "validate_article", _validate_article, {"article_json": article_json}
    )


@function_tool(strict_mode=False)
def check_pii(text: str) -> str:
    """Detecta PII (cédulas, emails, celulares CO, tarjetas). Retorna findings enmascarados.

    Args:
        text: Texto a inspeccionar.
    """
    return _execute("check_pii", _check_pii, {"text": text})


@function_tool(strict_mode=False)
def list_interactions(
    product_category: Optional[str] = None,
    query_type: Optional[str] = None,
    severity: Optional[str] = None,
) -> str:
    """Inventario de interacciones con filtros opcionales.

    Args:
        product_category: transferencias | cuentas | tarjetas | creditos | canales_digitales | otros.
        query_type: faq | howto | politica | troubleshooting.
        severity: informativa | operativa | critica.
    """
    filters = {
        k: v
        for k, v in {
            "product_category": product_category,
            "query_type": query_type,
            "severity": severity,
        }.items()
        if v
    }
    return _execute("list_interactions", _list_interactions, {"filters": filters or None})


ALL_TOOLS = {
    "search_interactions": search_interactions,
    "get_interaction": get_interaction,
    "extract_knowledge": extract_knowledge,
    "validate_article": validate_article,
    "check_pii": check_pii,
    "list_interactions": list_interactions,
}


def tools_for(names: List[str]) -> list:
    return [ALL_TOOLS[n] for n in names if n in ALL_TOOLS]

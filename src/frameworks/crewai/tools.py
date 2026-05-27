"""Wrappers de las 6 herramientas del tool contract al formato BaseTool de CrewAI.

Comparten un estado por-corrida (RUN_STATE) que el runner reinicia al inicio
de cada `run_crewai`. Cada wrapper incrementa el contador de tool calls,
verifica el presupuesto y serializa el resultado a JSON para que el agente lo
consuma como observación.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.tools.tool_contract import (
    check_pii,
    extract_knowledge,
    get_interaction,
    list_interactions,
    search_interactions,
    validate_article,
)


# ---------------------------------------------------------------------------
# Estado por corrida — el runner lo reinicia antes de cada run_crewai.
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


# ---------------------------------------------------------------------------
# Args schemas (Pydantic v2)
# ---------------------------------------------------------------------------


class SearchArgs(BaseModel):
    query: str = Field(..., description="Consulta en lenguaje natural (español).")
    k: int = Field(10, ge=1, le=50, description="Número máximo de resultados.")


class GetInteractionArgs(BaseModel):
    interaction_id: str = Field(
        ..., pattern=r"^INT-\d{4}-\d{3}$", description="Formato INT-YYYY-NNN."
    )


class ExtractKnowledgeArgs(BaseModel):
    interaction_ids: List[str] = Field(
        ..., min_length=1, description="Lista de IDs INT-YYYY-NNN a combinar."
    )


class ValidateArticleArgs(BaseModel):
    article_json: Dict[str, Any] = Field(
        ..., description="Objeto JSON del artículo KCS a validar."
    )


class CheckPIIArgs(BaseModel):
    text: str = Field(..., description="Texto a inspeccionar.")


class ListInteractionsArgs(BaseModel):
    product_category: Optional[str] = Field(
        None, description="Filtro: categoría de producto (transferencias, cuentas, ...)."
    )
    query_type: Optional[str] = Field(
        None, description="Filtro: faq | howto | politica | troubleshooting."
    )
    severity: Optional[str] = Field(
        None, description="Filtro: informativa | operativa | critica."
    )


# ---------------------------------------------------------------------------
# Base + ejecución compartida
# ---------------------------------------------------------------------------


class _CBBaseTool(BaseTool):
    """Base con tracking de presupuesto, trazas y serialización JSON."""

    def _execute(self, fn, **kwargs) -> str:
        if RUN_STATE["budget_exceeded"]:
            return "Error: presupuesto de tool calls excedido. No invoques más tools."

        RUN_STATE["tool_calls"] += 1
        if RUN_STATE["tool_calls"] > RUN_STATE["max_tool_calls"]:
            RUN_STATE["budget_exceeded"] = True
            _record(
                {
                    "type": "budget_exceeded",
                    "tool": self.name,
                    "tool_calls": RUN_STATE["tool_calls"],
                }
            )
            return (
                f"Error: se alcanzó el límite de {RUN_STATE['max_tool_calls']} "
                "tool calls. Detén las invocaciones y produce tu mejor respuesta."
            )

        try:
            result = fn(**kwargs)
            payload = json.dumps(result, ensure_ascii=False, default=str)
            _record(
                {
                    "type": "tool_call",
                    "tool": self.name,
                    "input": kwargs,
                    "is_error": False,
                    "result_preview": payload[:300],
                }
            )
            return payload
        except Exception as e:  # noqa: BLE001
            msg = f"Error ejecutando {self.name}: {e}"
            _record(
                {
                    "type": "tool_call",
                    "tool": self.name,
                    "input": kwargs,
                    "is_error": True,
                    "result_preview": msg[:300],
                }
            )
            RUN_STATE["errors"].append(
                {"tool": self.name, "input": kwargs, "error": str(e), "ts": _now_iso()}
            )
            return msg


# ---------------------------------------------------------------------------
# Wrappers concretos
# ---------------------------------------------------------------------------


class SearchInteractionsTool(_CBBaseTool):
    name: str = "search_interactions"
    description: str = (
        "Búsqueda semántica multilingüe sobre el corpus de interacciones de "
        "WhatsApp Davivienda. Retorna los k resultados más relevantes con score."
    )
    args_schema: Type[BaseModel] = SearchArgs

    def _run(self, query: str, k: int = 10) -> str:
        return self._execute(search_interactions, query=query, k=k)


class GetInteractionTool(_CBBaseTool):
    name: str = "get_interaction"
    description: str = (
        "Devuelve la interacción completa por ID. El nombre del cliente viene "
        "enmascarado (primera letra + ***)."
    )
    args_schema: Type[BaseModel] = GetInteractionArgs

    def _run(self, interaction_id: str) -> str:
        return self._execute(get_interaction, interaction_id=interaction_id)


class ExtractKnowledgeTool(_CBBaseTool):
    name: str = "extract_knowledge"
    description: str = (
        "Extrae y combina los hechos documentables (knowledge_extracted) de las "
        "interacciones indicadas, incluyendo preguntas del cliente y pasos del asesor."
    )
    args_schema: Type[BaseModel] = ExtractKnowledgeArgs

    def _run(self, interaction_ids: List[str]) -> str:
        return self._execute(extract_knowledge, interaction_ids=interaction_ids)


class ValidateArticleTool(_CBBaseTool):
    name: str = "validate_article"
    description: str = (
        "Valida un artículo contra la plantilla KCS: estructura, longitudes, "
        "valores enumerados y ausencia de PII."
    )
    args_schema: Type[BaseModel] = ValidateArticleArgs

    def _run(self, article_json: Dict[str, Any]) -> str:
        return self._execute(validate_article, article_json=article_json)


class CheckPIITool(_CBBaseTool):
    name: str = "check_pii"
    description: str = (
        "Detecta cédulas, emails, celulares colombianos y números de tarjeta. "
        "Retorna findings enmascarados."
    )
    args_schema: Type[BaseModel] = CheckPIIArgs

    def _run(self, text: str) -> str:
        return self._execute(check_pii, text=text)


class ListInteractionsTool(_CBBaseTool):
    name: str = "list_interactions"
    description: str = (
        "Inventario de interacciones con filtros opcionales por product_category, "
        "query_type y severity."
    )
    args_schema: Type[BaseModel] = ListInteractionsArgs

    def _run(
        self,
        product_category: Optional[str] = None,
        query_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> str:
        filters = {
            "product_category": product_category,
            "query_type": query_type,
            "severity": severity,
        }
        filters = {k: v for k, v in filters.items() if v}
        return self._execute(list_interactions, filters=filters or None)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


_TOOL_BY_NAME: Dict[str, Type[_CBBaseTool]] = {
    "search_interactions": SearchInteractionsTool,
    "get_interaction": GetInteractionTool,
    "extract_knowledge": ExtractKnowledgeTool,
    "validate_article": ValidateArticleTool,
    "check_pii": CheckPIITool,
    "list_interactions": ListInteractionsTool,
}


def build_tools(names: List[str]) -> List[_CBBaseTool]:
    return [_TOOL_BY_NAME[n]() for n in names if n in _TOOL_BY_NAME]

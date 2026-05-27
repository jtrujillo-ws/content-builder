"""TypedDict y reducers para el grafo LangGraph del Content Builder."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class ContentBuilderState(TypedDict, total=False):
    """Estado compartido entre nodos del grafo.

    Campos anotados con `operator.add` se agregan (append) cuando un nodo retorna
    nuevos elementos; los demás se reemplazan con el valor devuelto.
    """

    # Datos de entrada / orquestación
    interactions: List[Dict[str, Any]]
    knowledge_units: List[Dict[str, Any]]
    current_unit_index: int
    current_draft: Optional[Dict[str, Any]]
    revision_count: int

    # Salidas acumulativas
    generated_articles: Annotated[List[Dict[str, Any]], operator.add]
    article_interaction_map: Dict[str, List[str]]
    traces: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[Dict[str, Any]], operator.add]

    # Métricas y configuración
    metrics: Dict[str, Any]
    config: Dict[str, Any]

    # Veredicto efímero del nodo verify_article
    last_verification: Optional[Dict[str, Any]]
    last_feedback: Optional[str]

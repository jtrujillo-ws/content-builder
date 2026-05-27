"""Test end-to-end del prototipo LangGraph.

Ejecuta el pipeline completo contra la API de Anthropic con auto_approve=True
sobre 2 interacciones de calibración. Requiere ANTHROPIC_API_KEY en .env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(_PROJECT_ROOT / ".env")

from src.frameworks.langgraph import run_langgraph  # noqa: E402


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY no disponible — test omitido.",
)


def test_pipeline_smoke_two_calibration_interactions():
    """Smoke test: 2 interacciones, auto-approve, debe completar y dejar métricas."""
    result = run_langgraph(
        ["INT-2024-001", "INT-2024-002"], auto_approve=True
    )

    # Estructura del resultado
    assert set(result.keys()) >= {
        "articles",
        "article_interaction_map",
        "traces",
        "metrics",
        "errors",
        "aborted",
    }

    # No debería abortar con tan pocos inputs.
    assert result["aborted"] is False, f"Pipeline abortó: {result['errors']}"

    # Métricas mínimas
    m = result["metrics"]
    assert m["total_time_seconds"] > 0
    assert m["total_time_seconds"] < 300
    assert m["total_tool_calls"] <= 50
    assert m["cost_usd"] >= 0
    assert m["cost_usd"] < 2.0
    assert m["total_tokens_in"] > 0
    assert m["total_tokens_out"] > 0
    assert "articles_generated" in m

    # Al menos un artículo (los dos casos de calibración tratan de seguros y
    # SOAT — el analyzer puede agruparlos en 1 o 2 unidades).
    assert m["articles_generated"] >= 1
    assert len(result["articles"]) == m["articles_generated"]

    # Cada artículo debe tener la estructura KCS mínima.
    for record in result["articles"]:
        assert "article_id" in record
        article = record["article"]
        assert isinstance(article, dict)
        for required in (
            "title",
            "environment",
            "problem",
            "resolution",
            "evidence_pack",
            "metadata",
        ):
            assert required in article, f"Falta {required} en {record['article_id']}"

    # article_interaction_map debe tener la misma cardinalidad.
    assert len(result["article_interaction_map"]) == m["articles_generated"]

    # Traces no debe estar vacío.
    assert len(result["traces"]) > 0
    nodes_visitados = {t.get("node") for t in result["traces"] if "node" in t}
    assert "ingest_batch" in nodes_visitados
    assert "analyze_and_cluster" in nodes_visitados
    assert "generate_article" in nodes_visitados
    assert "verify_article" in nodes_visitados

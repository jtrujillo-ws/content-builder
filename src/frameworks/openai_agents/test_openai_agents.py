"""Smoke test del prototipo OpenAI Agents SDK.

Ejecuta `run_openai_agents` con auto_approve=True sobre INT-2024-001 y
INT-2024-002. Requiere ANTHROPIC_API_KEY en .env (se usa vía LitellmModel).
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

from src.frameworks.openai_agents import run_openai_agents  # noqa: E402


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY no disponible — test omitido.",
)


def test_openai_agents_smoke_two_calibration_interactions():
    """Pipeline completo sobre 2 interacciones, auto-approve, mismo contrato."""
    result = run_openai_agents(
        ["INT-2024-001", "INT-2024-002"], auto_approve=True
    )

    # Mismo contrato que LangGraph y CrewAI.
    assert set(result.keys()) >= {
        "articles",
        "article_interaction_map",
        "traces",
        "metrics",
        "errors",
        "aborted",
    }

    assert result["aborted"] is False, f"Pipeline abortó: {result['errors']}"

    m = result["metrics"]
    assert m["total_time_seconds"] > 0
    assert m["total_time_seconds"] < 300
    assert m["total_tool_calls"] <= 50
    assert m["cost_usd"] >= 0
    assert m["cost_usd"] < 2.0
    assert m["total_tokens_in"] > 0
    assert m["total_tokens_out"] > 0
    assert len(result["articles"]) == m["articles_generated"]
    assert len(result["article_interaction_map"]) == m["articles_generated"]

    # El pipeline debe haber producido al menos un artículo APROBADO, o haber
    # descartado todos los borradores documentando el motivo (el verificador
    # rechazó las 3 revisiones por baja exactitud / fidelidad a la evidencia).
    # Ambas trayectorias indican que la maquinaria del pipeline funcionó —
    # la primera demuestra el happy path, la segunda demuestra que el
    # guardrail de calidad bloquea drafts pobres antes del HITL.
    if m["articles_generated"] == 0:
        review_dropped = [
            e for e in result["errors"]
            if e.get("phase") == "review_loop"
            and "max_revisions" in (e.get("reason") or "")
        ]
        assert review_dropped, (
            "Sin artículos generados y sin errores documentados de "
            f"review_loop: {result['errors']}"
        )

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

    assert len(result["traces"]) > 0
    phases = {t.get("phase") for t in result["traces"] if "phase" in t}
    assert "ingest_batch" in phases
    assert "analyze" in phases
    assert "write" in phases
    assert "review" in phases

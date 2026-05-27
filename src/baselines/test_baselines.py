"""Tests de los dos baselines.

- `test_heuristic_*` corren siempre (no requieren API key).
- `test_single_prompt_*` requieren ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(_PROJECT_ROOT / ".env")

from src.baselines import run_heuristic, run_single_prompt  # noqa: E402


# Schema común que devuelven los frameworks y baselines.
EXPECTED_KEYS = {
    "articles",
    "article_interaction_map",
    "traces",
    "metrics",
    "errors",
    "aborted",
}

ARTICLE_REQUIRED_FIELDS = (
    "title",
    "environment",
    "problem",
    "resolution",
    "evidence_pack",
    "metadata",
)


def _assert_common_contract(result: dict) -> None:
    assert set(result.keys()) >= EXPECTED_KEYS
    m = result["metrics"]
    for field in (
        "total_time_seconds",
        "total_tokens_in",
        "total_tokens_out",
        "total_tool_calls",
        "cost_usd",
        "revision_cycles",
        "articles_generated",
    ):
        assert field in m, f"falta metric {field}"
    assert len(result["articles"]) == m["articles_generated"]
    assert len(result["article_interaction_map"]) == m["articles_generated"]
    for record in result["articles"]:
        assert "article_id" in record
        article = record["article"]
        assert isinstance(article, dict)
        for required in ARTICLE_REQUIRED_FIELDS:
            assert required in article, f"falta {required} en {record['article_id']}"


# ---------------------------------------------------------------------------
# Heurístico — siempre corre
# ---------------------------------------------------------------------------


def test_heuristic_two_calibration_interactions():
    result = run_heuristic(["INT-2024-001", "INT-2024-002"], auto_approve=True)
    _assert_common_contract(result)
    assert result["aborted"] is False
    # Sin LLM
    assert result["metrics"]["total_tokens_in"] == 0
    assert result["metrics"]["total_tokens_out"] == 0
    assert result["metrics"]["total_tool_calls"] == 0
    assert result["metrics"]["cost_usd"] == 0.0
    # Al menos un artículo
    assert result["metrics"]["articles_generated"] >= 1
    # Cada artículo debe tener al menos un interaction_id mapeado
    for art_id, ids in result["article_interaction_map"].items():
        assert len(ids) >= 1, f"{art_id} sin interaction_ids"


def test_heuristic_singleton():
    result = run_heuristic(["INT-2024-001"], auto_approve=True)
    _assert_common_contract(result)
    assert result["metrics"]["articles_generated"] == 1


def test_heuristic_invalid_ids_aborts():
    result = run_heuristic(["INT-9999-999"], auto_approve=True)
    assert result["aborted"] is True
    assert result["metrics"]["articles_generated"] == 0


# ---------------------------------------------------------------------------
# Single prompt — requiere API
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY no disponible.",
)
def test_single_prompt_two_calibration_interactions():
    result = run_single_prompt(
        ["INT-2024-001", "INT-2024-002"], auto_approve=True
    )
    _assert_common_contract(result)
    assert result["aborted"] is False, f"Pipeline abortó: {result['errors']}"
    m = result["metrics"]
    assert m["total_tokens_in"] > 0
    assert m["total_tokens_out"] > 0
    assert m["total_tool_calls"] == 0  # sin tool use
    assert m["revision_cycles"] == 0  # sin loop de revisión
    assert m["cost_usd"] >= 0
    assert m["cost_usd"] < 2.0
    assert m["articles_generated"] >= 1

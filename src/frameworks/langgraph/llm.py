"""Wrapper del SDK Anthropic con loop de tool use y contabilidad de presupuesto."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

from src.tools.tool_contract import TOOL_REGISTRY, get_tool


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class BudgetExceeded(Exception):
    """Se levanta cuando una corrida supera alguno de los topes."""


def load_budget() -> Dict[str, Any]:
    path = _PROJECT_ROOT / "configs" / "experiments" / "budget.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompt(name: str) -> Dict[str, Any]:
    path = _PROJECT_ROOT / "configs" / "prompts" / "v1" / f"system_{name}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_anthropic_tools() -> List[Dict[str, Any]]:
    """Convierte TOOL_REGISTRY al formato de tool definitions de Anthropic."""
    tools = []
    for name, entry in TOOL_REGISTRY.items():
        tools.append(
            {
                "name": name,
                "description": entry["description"],
                "input_schema": entry["parameters"],
            }
        )
    return tools


def get_client() -> Anthropic:
    load_dotenv(_PROJECT_ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY no está definido en .env")
    return Anthropic(api_key=api_key)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Extrae un objeto JSON del texto retornado por el modelo.

    Tolera tres formatos: JSON puro, JSON envuelto en fence ```json...```,
    o JSON embebido en prosa (toma el primer { ... } o [ ... ] balanceado).
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_FENCE_RE.search(text)
    if m:
        return json.loads(m.group(1))
    # Búsqueda greedy balanceada por conteo de llaves
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
    raise ValueError(f"No se encontró JSON parseable en la respuesta: {text[:300]}")


def _update_cost(metrics: Dict[str, Any], usage, pricing: Dict[str, Any]) -> None:
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

    metrics["total_tokens_in"] = metrics.get("total_tokens_in", 0) + input_tokens
    metrics["total_tokens_out"] = metrics.get("total_tokens_out", 0) + output_tokens
    metrics["cache_creation_tokens"] = (
        metrics.get("cache_creation_tokens", 0) + cache_create
    )
    metrics["cache_read_tokens"] = metrics.get("cache_read_tokens", 0) + cache_read

    cost = (
        input_tokens * pricing["input_per_mtok"]
        + output_tokens * pricing["output_per_mtok"]
        + cache_create * pricing["cache_write_per_mtok"]
        + cache_read * pricing["cache_read_per_mtok"]
    ) / 1_000_000
    metrics["cost_usd"] = metrics.get("cost_usd", 0.0) + cost


def _check_budget(state: Dict[str, Any]) -> None:
    cfg = state["config"]
    metrics = state["metrics"]
    if metrics.get("total_tool_calls", 0) > cfg["max_tool_calls"]:
        raise BudgetExceeded(
            f"max_tool_calls excedido: {metrics['total_tool_calls']} > {cfg['max_tool_calls']}"
        )
    if metrics.get("cost_usd", 0.0) > cfg["max_cost_usd"]:
        raise BudgetExceeded(
            f"max_cost_usd excedido: ${metrics['cost_usd']:.4f} > ${cfg['max_cost_usd']}"
        )
    elapsed = time.time() - metrics["_started_at"]
    if elapsed > cfg["timeout_seconds"]:
        raise BudgetExceeded(
            f"timeout_seconds excedido: {elapsed:.1f}s > {cfg['timeout_seconds']}s"
        )


def call_claude_with_tools(
    state: Dict[str, Any],
    system_prompt: str,
    user_message: str,
    *,
    node_name: str,
    max_iterations: int = 12,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Ejecuta un loop tool-use contra Claude y retorna (texto_final, trazas_locales).

    Las trazas locales incluyen cada llamada a tool y la respuesta final del modelo;
    se anexan al estado en `state["traces"]` también.
    """
    cfg = state["config"]
    metrics = state["metrics"]
    client = get_client()
    tools = build_anthropic_tools()

    messages: List[Dict[str, Any]] = [{"role": "user", "content": user_message}]
    local_traces: List[Dict[str, Any]] = []

    for iteration in range(max_iterations):
        _check_budget(state)

        resp = client.messages.create(
            model=cfg["model_name"],
            max_tokens=cfg["max_tokens"],
            temperature=cfg["temperature"],
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tools,
            messages=messages,
        )

        _update_cost(metrics, resp.usage, cfg["pricing"])

        if resp.stop_reason == "tool_use":
            # Conserva el turno del asistente con los tool_use blocks intactos.
            messages.append({"role": "assistant", "content": resp.content})
            tool_results_content: List[Dict[str, Any]] = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                metrics["total_tool_calls"] = metrics.get("total_tool_calls", 0) + 1
                _check_budget(state)
                tool_name = block.name
                tool_input = dict(block.input or {})
                try:
                    fn = get_tool(tool_name)
                    result = fn(**tool_input)
                    is_error = False
                    payload = json.dumps(result, ensure_ascii=False, default=str)
                except Exception as e:  # noqa: BLE001
                    is_error = True
                    payload = f"Error ejecutando {tool_name}: {e}"
                tool_results_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": payload,
                        "is_error": is_error,
                    }
                )
                trace_entry = {
                    "node": node_name,
                    "iteration": iteration,
                    "type": "tool_call",
                    "tool": tool_name,
                    "input": tool_input,
                    "is_error": is_error,
                    "result_preview": payload[:400],
                }
                local_traces.append(trace_entry)
            messages.append({"role": "user", "content": tool_results_content})
            continue

        if resp.stop_reason == "end_turn":
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            local_traces.append(
                {
                    "node": node_name,
                    "iteration": iteration,
                    "type": "final_message",
                    "text_preview": text[:400],
                    "stop_reason": resp.stop_reason,
                }
            )
            return text, local_traces

        # max_tokens, pause_turn u otros — terminamos lo mejor posible.
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        local_traces.append(
            {
                "node": node_name,
                "iteration": iteration,
                "type": "stopped_unexpectedly",
                "stop_reason": resp.stop_reason,
                "text_preview": text[:400],
            }
        )
        return text, local_traces

    raise RuntimeError(
        f"call_claude_with_tools no convergió en {max_iterations} iteraciones"
    )

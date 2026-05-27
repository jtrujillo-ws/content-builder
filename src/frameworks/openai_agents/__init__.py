"""Prototipo OpenAI Agents SDK del Content Builder.

Usa `LitellmModel` para enchufar Claude (Anthropic) al SDK — ver
`runner.py` para la decisión de diseño completa.
"""

from src.frameworks.openai_agents.runner import (
    load_budget,
    load_prompt,
    run_openai_agents,
)
from src.frameworks.openai_agents.tools import (
    ALL_TOOLS,
    RUN_STATE,
    reset_run_state,
    tools_for,
)

__all__ = [
    "ALL_TOOLS",
    "RUN_STATE",
    "load_budget",
    "load_prompt",
    "reset_run_state",
    "run_openai_agents",
    "tools_for",
]

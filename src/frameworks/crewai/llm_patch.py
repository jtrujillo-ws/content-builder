"""Wrapper de CrewAI LLM que evita el "assistant message prefill" contra Anthropic.

Claude Sonnet 4.5 / 4.6 retiraron el soporte de assistant prefill. CrewAI 1.6.1
ejecuta un loop ReAct que tras cada tool call concatena ``\\nObservation: ...`` al
mismo mensaje assistant y re-prompta, dejando la conversación terminando en
``role=assistant`` — lo que Anthropic rechaza con HTTP 400:

    "This model does not support assistant message prefill.
     The conversation must end with a user message."

Importante: la fábrica ``crewai.LLM.__new__`` enruta ``LLM("anthropic/...", ...)`` al
provider nativo ``AnthropicCompletion`` (NO al loop LiteLLM). El parcheo correcto es
subclasear ``AnthropicCompletion`` y reescribir ``_format_messages_for_anthropic``
para convertir la "prefill ReAct" en (assistant, user(Observation+Continúa)). Así
preservamos el rastreo de tokens nativo (``get_token_usage_summary``) que usa el
runner para reportar costo.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from crewai.llms.providers.anthropic.completion import AnthropicCompletion


_CONTINUE_PROMPT = (
    "Continúa con el siguiente paso del razonamiento "
    "(Thought / Action / Action Input o Final Answer)."
)


def _split_trailing_assistant(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reescribe el último turno assistant para que la conversación termine en user.

    - Si el contenido contiene ``\\nObservation:``, se parte en cabeza (assistant) y
      cola (user). Esto convierte la "prefill ReAct" en un turno limpio
      assistant → user, sin perder la observación que ya se inyectó.
    - Si no hay ``Observation:`` (caso raro: el agente terminó sin tool result),
      se añade un user ``Continúa…`` para destrabar el turno.
    """
    if not messages:
        return messages
    last = messages[-1]
    if not isinstance(last, dict) or last.get("role") != "assistant":
        return messages
    content = last.get("content", "")
    if not isinstance(content, str):
        # Bloques estructurados (p.ej. tool_use): solo añadimos un user de cierre.
        return [*messages, {"role": "user", "content": _CONTINUE_PROMPT}]
    if "\nObservation:" in content:
        head, _, obs_tail = content.rpartition("\nObservation:")
        head = head.rstrip()
        user_content = f"Observation:{obs_tail}".rstrip() + f"\n\n{_CONTINUE_PROMPT}"
        user_msg = {"role": "user", "content": user_content}
        if head:
            return [*messages[:-1], {"role": "assistant", "content": head}, user_msg]
        return [*messages[:-1], user_msg]
    return [*messages, {"role": "user", "content": _CONTINUE_PROMPT}]


class PrefillSafeAnthropicCompletion(AnthropicCompletion):
    """Drop-in del provider nativo de CrewAI segura para claude-sonnet-4-5+."""

    def _format_messages_for_anthropic(
        self, messages: Any
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        formatted, system = super()._format_messages_for_anthropic(messages)
        return _split_trailing_assistant(list(formatted)), system


__all__ = ["PrefillSafeAnthropicCompletion", "_split_trailing_assistant"]

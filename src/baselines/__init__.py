"""Baselines no-agénticos para comparar contra los 3 frameworks.

- `heuristic`: pipeline puramente algorítmico (TF-IDF + KMeans, sin LLM).
- `single_prompt`: una sola llamada a Claude con todo el contexto, sin tools.

Ambos devuelven el mismo contrato que `run_langgraph` / `run_crewai` /
`run_openai_agents`.
"""

from src.baselines.heuristic import run_heuristic
from src.baselines.single_prompt import run_single_prompt

__all__ = ["run_heuristic", "run_single_prompt"]

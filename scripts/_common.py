"""Helpers compartidos por los scripts de orquestación.

Provee:
- `PROJECT_ROOT` y `bootstrap_path()` para asegurar imports de `src.*`.
- `setup_logging()` con formato uniforme.
- `load_splits()` para leer `data/splits/splits.yaml`.
- `dispatch_runner()` para mapear el nombre del framework a su `run_*`.
- `git_info()` y `config_hash()` para registrar metadata reproducible.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def bootstrap_path() -> None:
    """Inserta la raíz del proyecto en sys.path si no está ya."""
    p = str(PROJECT_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)


def setup_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silenciar logs verbosos de dependencias.
    for noisy in ("LiteLLM", "litellm", "httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("content-builder")


def load_splits() -> Dict[str, Any]:
    path = PROJECT_ROOT / "data" / "splits" / "splits.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_interactions() -> List[Dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "processed" / "interactions.jsonl"
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def load_kb_articles() -> List[Dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "processed" / "kb_articles.jsonl"
    if not path.exists():
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


# ---------------------------------------------------------------------------
# Framework dispatch
# ---------------------------------------------------------------------------

FRAMEWORK_CHOICES = (
    "langgraph",
    "crewai",
    "openai_agents",
    "baseline_heuristic",
    "baseline_prompt",
)


def dispatch_runner(name: str) -> Callable[[List[str], bool], Dict[str, Any]]:
    """Mapea el nombre canónico del framework a su función `run_*`.

    Todas las funciones tienen firma `(interaction_ids: List[str], auto_approve: bool) -> dict`
    y devuelven el contrato común {articles, article_interaction_map, traces,
    metrics, errors, aborted}.
    """
    bootstrap_path()
    if name == "langgraph":
        from src.frameworks.langgraph import run_langgraph

        return run_langgraph  # type: ignore[return-value]
    if name == "crewai":
        from src.frameworks.crewai import run_crewai

        return run_crewai  # type: ignore[return-value]
    if name == "openai_agents":
        from src.frameworks.openai_agents import run_openai_agents

        return run_openai_agents  # type: ignore[return-value]
    if name == "baseline_heuristic":
        from src.baselines import run_heuristic

        return run_heuristic  # type: ignore[return-value]
    if name == "baseline_prompt":
        from src.baselines import run_single_prompt

        return run_single_prompt  # type: ignore[return-value]
    raise ValueError(f"Framework desconocido: {name}. Opciones: {FRAMEWORK_CHOICES}")


# ---------------------------------------------------------------------------
# Persistencia de resultados
# ---------------------------------------------------------------------------


def write_run_artifacts(out_dir: Path, result: Dict[str, Any]) -> None:
    """Escribe los 5 artefactos canónicos de una corrida."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # generated_articles.jsonl — un artículo por línea
    with open(out_dir / "generated_articles.jsonl", "w", encoding="utf-8") as f:
        for record in result.get("articles", []):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # article_interaction_map.json
    with open(out_dir / "article_interaction_map.json", "w", encoding="utf-8") as f:
        json.dump(result.get("article_interaction_map", {}), f, ensure_ascii=False, indent=2)

    # execution_traces.jsonl
    with open(out_dir / "execution_traces.jsonl", "w", encoding="utf-8") as f:
        for trace in result.get("traces", []):
            f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")

    # metrics.json
    with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(result.get("metrics", {}), f, ensure_ascii=False, indent=2)

    # errors.json
    with open(out_dir / "errors.json", "w", encoding="utf-8") as f:
        json.dump(result.get("errors", []), f, ensure_ascii=False, indent=2, default=str)


# ---------------------------------------------------------------------------
# Metadata reproducible
# ---------------------------------------------------------------------------


def _run_git(args: List[str]) -> str:
    try:
        out = subprocess.run(
            ["git"] + args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def git_info() -> Dict[str, str]:
    commit = _run_git(["rev-parse", "HEAD"])
    short = _run_git(["rev-parse", "--short", "HEAD"])
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    tag = _run_git(["describe", "--tags", "--abbrev=0"])
    dirty = _run_git(["status", "--porcelain"])
    return {
        "commit": commit,
        "commit_short": short,
        "branch": branch,
        "latest_tag": tag,
        "dirty": bool(dirty),  # type: ignore[dict-item]
    }


_CONFIG_FILES = [
    "configs/experiments/budget.yaml",
    "configs/policies/governance_policy.yaml",
    "configs/policies/pii_policy.yaml",
    "configs/prompts/v1/system_analyzer.yaml",
    "configs/prompts/v1/system_generator.yaml",
    "configs/prompts/v1/system_critic.yaml",
    "configs/prompts/v1/system_governance.yaml",
]


def config_hash() -> Tuple[str, List[str]]:
    """SHA-256 del concatenado de los configs que afectan la corrida."""
    h = hashlib.sha256()
    used: List[str] = []
    for rel in _CONFIG_FILES:
        p = PROJECT_ROOT / rel
        if not p.exists():
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\n")
        h.update(p.read_bytes())
        h.update(b"\n")
        used.append(rel)
    return h.hexdigest(), used


def load_model_name() -> str:
    path = PROJECT_ROOT / "configs" / "experiments" / "budget.yaml"
    with open(path, "r", encoding="utf-8") as f:
        budget = yaml.safe_load(f)
    return budget["model"]["name"]

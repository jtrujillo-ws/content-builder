"""Helpers compartidos por los scripts de orquestación.

Provee:
- `PROJECT_ROOT` y `bootstrap_path()` para asegurar imports de `src.*`.
- `setup_logging()` con formato uniforme.
- `load_splits()` para leer `data/splits/splits.yaml`.
- `dispatch_runner()` para mapear el nombre del framework a su `run_*`.
- `run_in_batches()` para invocar el runner por lotes y agregar resultados.
- `git_info()` y `config_hash()` para registrar metadata reproducible.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable, Dict, List, Optional, Tuple

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
# Batched runner
# ---------------------------------------------------------------------------

_AGGREGATABLE_METRIC_KEYS = (
    "total_tokens_in",
    "total_tokens_out",
    "cache_read_tokens",
    "cache_creation_tokens",
    "total_tool_calls",
    "cost_usd",
    "revision_cycles",
    "articles_generated",
    "successful_requests",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _chunks(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def run_in_batches(
    runner: Callable[..., Dict[str, Any]],
    interaction_ids: List[str],
    *,
    batch_size: int,
    auto_approve: bool,
    log: logging.Logger,
    max_total_cost_usd: Optional[float] = None,
) -> Dict[str, Any]:
    """Invoca al runner en lotes de tamaño `batch_size` y agrega los resultados.

    Cada lote es una llamada independiente al runner — cada una con su propio
    presupuesto (timeout / tool_calls / cost) leído de `configs/experiments/budget.yaml`.
    Las fallas o abortos de un lote individual se registran como entradas en
    `errors` y el helper continúa con el siguiente lote.

    Reglas de agregación:
    - `articles`: concatenación con `article_id` renumerado globalmente y
      con `batch_idx` añadido a cada record.
    - `article_interaction_map`: las claves se traducen a los nuevos
      `article_id` globales.
    - `traces` y `errors`: concatenación con `batch_idx` añadido.
    - `metrics`: campos numéricos se suman (`total_tokens_in/out`,
      `cache_*`, `total_tool_calls`, `cost_usd`, `revision_cycles`,
      `articles_generated`, `successful_requests`). `total_time_seconds`
      es el wall-clock real del conjunto de lotes.
    - Se añaden tres campos a `metrics` no presentes en los runners:
      `batch_count`, `batch_size`, `latency_per_batch_median`.
    - El campo `batches` (sibling de `metrics`) describe cada lote.
    """
    batches = _chunks(interaction_ids, batch_size)
    log.info(
        "Batching: %d interacciones → %d lotes de hasta %d",
        len(interaction_ids),
        len(batches),
        batch_size,
    )

    agg_articles: List[Dict[str, Any]] = []
    agg_map: Dict[str, List[str]] = {}
    agg_traces: List[Dict[str, Any]] = []
    agg_errors: List[Dict[str, Any]] = []
    agg_batches: List[Dict[str, Any]] = []
    agg_metrics: Dict[str, Any] = {k: 0 for k in _AGGREGATABLE_METRIC_KEYS}
    agg_metrics["cost_usd"] = 0.0
    aborted_global = False

    total_started = time.time()

    for b_idx, batch_ids in enumerate(batches, start=1):
        if max_total_cost_usd is not None and agg_metrics["cost_usd"] >= max_total_cost_usd:
            log.warning(
                "Lote %d/%d omitido: costo acumulado $%.4f ≥ tope $%.2f",
                b_idx,
                len(batches),
                agg_metrics["cost_usd"],
                max_total_cost_usd,
            )
            agg_errors.append(
                {
                    "phase": "batch_runner",
                    "batch_idx": b_idx,
                    "reason": "max_total_cost_reached",
                    "cost_acumulado": round(agg_metrics["cost_usd"], 6),
                    "ts": _now_iso(),
                }
            )
            aborted_global = True
            break

        log.info(
            "─── Lote %d/%d: %d interacciones (%s) ───",
            b_idx,
            len(batches),
            len(batch_ids),
            ", ".join(batch_ids),
        )
        t0 = time.time()
        try:
            result = runner(batch_ids, auto_approve=auto_approve)
            status = "aborted" if result.get("aborted") else "completed"
            crashed = False
        except Exception as e:  # noqa: BLE001
            elapsed = round(time.time() - t0, 3)
            log.exception("Lote %d crasheó: %s", b_idx, e)
            agg_errors.append(
                {
                    "phase": "batch_runner",
                    "batch_idx": b_idx,
                    "batch_ids": batch_ids,
                    "error": f"crash: {type(e).__name__}: {e}",
                    "elapsed_seconds": elapsed,
                    "ts": _now_iso(),
                }
            )
            agg_batches.append(
                {
                    "batch_idx": b_idx,
                    "batch_ids": batch_ids,
                    "status": "crashed",
                    "elapsed_seconds": elapsed,
                    "articles_generated": 0,
                    "errors": 1,
                    "cost_usd": 0.0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tool_calls": 0,
                }
            )
            continue

        elapsed = round(time.time() - t0, 3)
        m = result.get("metrics") or {}
        batch_articles = result.get("articles") or []

        # Renumerar article_id globalmente y conservar el original.
        old_to_new: Dict[str, str] = {}
        for art in batch_articles:
            old_id = art.get("article_id")
            new_id = f"ART-{len(agg_articles) + 1:03d}"
            new_record = dict(art)
            new_record["article_id"] = new_id
            new_record["batch_idx"] = b_idx
            if old_id and old_id != new_id:
                new_record["original_article_id"] = old_id
            agg_articles.append(new_record)
            if old_id is not None:
                old_to_new[old_id] = new_id

        # Mapping
        for old_id, ids in (result.get("article_interaction_map") or {}).items():
            new_id = old_to_new.get(old_id, old_id)
            agg_map[new_id] = list(ids)

        # Traces — añadir batch_idx
        for trace in result.get("traces") or []:
            t2 = dict(trace) if isinstance(trace, dict) else {"raw": str(trace)}
            t2["batch_idx"] = b_idx
            agg_traces.append(t2)

        # Errors del lote
        for err in result.get("errors") or []:
            e2 = dict(err) if isinstance(err, dict) else {"raw": str(err)}
            e2["batch_idx"] = b_idx
            agg_errors.append(e2)

        # Sumar métricas numéricas
        for k in _AGGREGATABLE_METRIC_KEYS:
            if k in m and isinstance(m[k], (int, float)):
                agg_metrics[k] = agg_metrics.get(k, 0) + m[k]

        agg_batches.append(
            {
                "batch_idx": b_idx,
                "batch_ids": batch_ids,
                "status": status,
                "elapsed_seconds": elapsed,
                "articles_generated": len(batch_articles),
                "errors": len(result.get("errors") or []),
                "cost_usd": float(m.get("cost_usd", 0)),
                "tokens_in": int(m.get("total_tokens_in", 0)),
                "tokens_out": int(m.get("total_tokens_out", 0)),
                "tool_calls": int(m.get("total_tool_calls", 0)),
                "revision_cycles": int(m.get("revision_cycles", 0)),
            }
        )
        log.info(
            "Lote %d done: status=%s arts=%d errs=%d cost=$%.4f tiempo=%.1fs",
            b_idx,
            status,
            len(batch_articles),
            len(result.get("errors") or []),
            float(m.get("cost_usd", 0)),
            elapsed,
        )

    total_elapsed = round(time.time() - total_started, 3)
    # Recalcular articles_generated = conteo real
    agg_metrics["articles_generated"] = len(agg_articles)
    agg_metrics["cost_usd"] = round(float(agg_metrics["cost_usd"]), 6)
    agg_metrics["total_time_seconds"] = total_elapsed
    agg_metrics["batch_count"] = len(batches)
    agg_metrics["batch_size"] = batch_size
    if agg_batches:
        latencies = [b["elapsed_seconds"] for b in agg_batches]
        agg_metrics["latency_per_batch_median"] = float(median(latencies))
        agg_metrics["latency_per_batch_max"] = float(max(latencies))
        agg_metrics["batches_aborted"] = sum(
            1 for b in agg_batches if b["status"] != "completed"
        )
    else:
        agg_metrics["latency_per_batch_median"] = 0.0
        agg_metrics["latency_per_batch_max"] = 0.0
        agg_metrics["batches_aborted"] = 0

    return {
        "articles": agg_articles,
        "article_interaction_map": agg_map,
        "traces": agg_traces,
        "metrics": agg_metrics,
        "errors": agg_errors,
        "aborted": aborted_global,
        "batches": agg_batches,
    }


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

    # batches.json — solo si la corrida fue batched
    if "batches" in result:
        with open(out_dir / "batches.json", "w", encoding="utf-8") as f:
            json.dump(result.get("batches", []), f, ensure_ascii=False, indent=2, default=str)


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

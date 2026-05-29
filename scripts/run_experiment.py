#!/usr/bin/env python
"""Corre el estudio principal sobre el split de evaluación (109 IDs), N veces.

Uso:
    .venv/bin/python scripts/run_experiment.py --framework langgraph --runs 3
    .venv/bin/python scripts/run_experiment.py --framework crewai --runs 3 \\
        --ablation no_critic

Salida:
    runs/experiment/<framework>/[<ablation>/]run_<n>/
        generated_articles.jsonl
        article_interaction_map.json
        execution_traces.jsonl
        metrics.json
        errors.json
        run_metadata.json
    runs/experiment/<framework>/[<ablation>/]experiment_summary.json

Notas sobre ablaciones:
    --ablation puede ser uno de {no_grouping, no_critic, no_evidence, no_memory}.
    Por ahora la bandera SE REGISTRA en run_metadata.json para análisis posterior,
    pero el comportamiento de los runners no se altera en este script — eso
    requiere wiring específico dentro de cada framework (TODO documentado en el
    issue tracker). La excepción es `no_grouping`: el script aplica la ablación
    a nivel de orquestación ejecutando el runner una vez por interaction_id
    (singletons) y agregando los resultados.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._common import (  # noqa: E402
    FRAMEWORK_CHOICES,
    PROJECT_ROOT,
    config_hash,
    git_info,
    load_model_name,
    load_splits,
    run_in_batches,
    setup_logging,
    write_run_artifacts,
)


ABLATION_CHOICES = ("no_grouping", "no_critic", "no_evidence", "no_memory")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Corre N repeticiones del estudio principal."
    )
    parser.add_argument(
        "--framework", required=True, choices=FRAMEWORK_CHOICES
    )
    parser.add_argument("--runs", type=int, default=3, help="Repeticiones (default 3).")
    parser.add_argument(
        "--ablation",
        choices=ABLATION_CHOICES,
        default=None,
        help="Ablación opcional. `no_grouping` fuerza batch_size=1; las otras se "
        "registran como metadata y no alteran el comportamiento del runner.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Interacciones por invocación del runner (default 5). "
        "Si --ablation=no_grouping, se fuerza a 1.",
    )
    parser.add_argument(
        "--max-total-cost",
        type=float,
        default=20.0,
        help="Tope global de costo USD por run (default $20).",
    )
    parser.add_argument(
        "--no-auto-approve",
        dest="auto_approve",
        action="store_false",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita el número de interacciones (humo).",
    )
    parser.add_argument(
        "--eval-subset",
        type=str,
        default=None,
        metavar="YAML",
        help=(
            "Ruta a un YAML con `interaction_ids: [...]` (p. ej. "
            "`data/splits/eval_subset_50.yaml`). Si se pasa, se usa esa lista "
            "en vez del split completo de evaluación. Los IDs deben pertenecer "
            "al split de evaluación."
        ),
    )
    parser.add_argument(
        "--start-run",
        type=int,
        default=1,
        help="Índice de la primera repetición (útil para reanudar).",
    )
    args = parser.parse_args(argv)
    log = setup_logging("INFO")

    if args.batch_size < 1:
        log.error("--batch-size debe ser ≥ 1")
        return 2

    splits = load_splits()
    ids = list(splits.get("evaluation") or [])
    subset_meta: Dict[str, Any] = {}
    if args.eval_subset:
        import yaml as _yaml

        subset_path = Path(args.eval_subset)
        if not subset_path.is_absolute():
            subset_path = PROJECT_ROOT / subset_path
        if not subset_path.exists():
            log.error("No existe --eval-subset: %s", subset_path)
            return 2
        with open(subset_path, "r", encoding="utf-8") as f:
            subset_doc = _yaml.safe_load(f) or {}
        subset_ids = list(subset_doc.get("interaction_ids") or [])
        if not subset_ids:
            log.error("--eval-subset YAML no contiene `interaction_ids`")
            return 2
        eval_set = set(ids)
        out_of_split = [i for i in subset_ids if i not in eval_set]
        if out_of_split:
            log.error(
                "--eval-subset contiene IDs fuera del split de evaluación: %s",
                out_of_split[:5],
            )
            return 2
        log.info(
            "Usando subset %s: %d/%d IDs del split evaluation",
            subset_path.name,
            len(subset_ids),
            len(ids),
        )
        ids = subset_ids
        subset_meta = {
            "path": str(subset_path.relative_to(PROJECT_ROOT)),
            "name": subset_doc.get("name"),
            "subset_n": subset_doc.get("subset_n"),
            "source_split": subset_doc.get("source_split"),
            "sampling": subset_doc.get("sampling"),
        }
    if args.limit:
        ids = ids[: args.limit]
    if not ids:
        log.error("No hay IDs en evaluation/splits.yaml")
        return 2

    effective_batch_size = 1 if args.ablation == "no_grouping" else args.batch_size

    log.info(
        "Evaluación: %d interaction_ids, %d repeticiones, batch_size=%d",
        len(ids),
        args.runs,
        effective_batch_size,
    )
    if args.ablation:
        if args.ablation == "no_grouping":
            log.warning(
                "Ablación no_grouping: forzando batch_size=1 (cada interacción en su propia invocación)."
            )
        else:
            log.warning(
                "Ablación %s registrada en metadata; requiere wiring en el runner para tener efecto.",
                args.ablation,
            )

    # Carpeta base
    base_dir = PROJECT_ROOT / "runs" / "experiment" / args.framework
    if args.ablation:
        base_dir = base_dir / args.ablation
    base_dir.mkdir(parents=True, exist_ok=True)

    git = git_info()
    cfg_hash, cfg_files = config_hash()
    experiment_id = str(uuid.uuid4())
    summary_runs: List[Dict[str, Any]] = []

    overall_started = datetime.now(timezone.utc)
    log.info("Experiment ID: %s", experiment_id)

    for n in range(args.start_run, args.start_run + args.runs):
        run_dir = base_dir / f"run_{n}"
        run_dir.mkdir(parents=True, exist_ok=True)
        log.info("─── run %d/%d en %s ───", n, args.start_run + args.runs - 1, run_dir)

        run_started = datetime.now(timezone.utc)
        metadata = {
            "experiment_id": experiment_id,
            "run_index": n,
            "framework": args.framework,
            "ablation": args.ablation,
            "auto_approve": args.auto_approve,
            "split": "evaluation",
            "eval_subset": subset_meta or None,
            "interaction_ids": ids,
            "batch_size": effective_batch_size,
            "max_total_cost_usd": args.max_total_cost,
            "started_at_utc": run_started.isoformat(timespec="seconds"),
            "model_name": load_model_name(),
            "prompt_version": git.get("latest_tag") or None,
            "git": git,
            "config_hash_sha256": cfg_hash,
            "config_files_hashed": cfg_files,
            "python_version": sys.version.split()[0],
        }

        t0 = time.time()
        try:
            result = run_in_batches(
                args.framework,
                ids,
                batch_size=effective_batch_size,
                auto_approve=args.auto_approve,
                log=log,
                max_total_cost_usd=args.max_total_cost,
            )
            elapsed = round(time.time() - t0, 3)
            metadata["completed_at_utc"] = _now_iso()
            metadata["wall_clock_seconds"] = elapsed
            metadata["status"] = (
                "aborted_global" if result.get("aborted") else "completed"
            )
            metadata["batch_count"] = result["metrics"].get("batch_count", 0)
            metadata["batches_aborted"] = result["metrics"].get("batches_aborted", 0)
        except Exception as e:  # noqa: BLE001
            elapsed = round(time.time() - t0, 3)
            log.exception("Excepción en run %d: %s", n, e)
            result = {
                "articles": [],
                "article_interaction_map": {},
                "traces": [],
                "metrics": {},
                "errors": [{"reason": f"crash: {type(e).__name__}: {e}", "ts": _now_iso()}],
                "aborted": True,
            }
            metadata["completed_at_utc"] = _now_iso()
            metadata["wall_clock_seconds"] = elapsed
            metadata["status"] = "crashed"
            metadata["crash_error"] = str(e)

        write_run_artifacts(run_dir, result)
        (run_dir / "run_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        m = result.get("metrics", {}) or {}
        log.info(
            "run %d: status=%s articulos=%d errores=%d tokens_in=%d tokens_out=%d cost=$%.4f tiempo=%.1fs",
            n,
            metadata["status"],
            m.get("articles_generated", 0),
            len(result.get("errors", [])),
            m.get("total_tokens_in", 0),
            m.get("total_tokens_out", 0),
            m.get("cost_usd", 0.0),
            elapsed,
        )
        summary_runs.append(
            {
                "run_index": n,
                "status": metadata["status"],
                "wall_clock_seconds": elapsed,
                "articles_generated": m.get("articles_generated", 0),
                "errors": len(result.get("errors", [])),
                "cost_usd": m.get("cost_usd", 0.0),
                "tokens_in": m.get("total_tokens_in", 0),
                "tokens_out": m.get("total_tokens_out", 0),
                "tool_calls": m.get("total_tool_calls", 0),
                "revision_cycles": m.get("revision_cycles", 0),
            }
        )

    overall_completed = datetime.now(timezone.utc)
    experiment_summary = {
        "experiment_id": experiment_id,
        "framework": args.framework,
        "ablation": args.ablation,
        "auto_approve": args.auto_approve,
        "split": "evaluation",
        "eval_subset": subset_meta or None,
        "n_runs": args.runs,
        "interaction_count": len(ids),
        "started_at_utc": overall_started.isoformat(timespec="seconds"),
        "completed_at_utc": overall_completed.isoformat(timespec="seconds"),
        "model_name": load_model_name(),
        "prompt_version": git.get("latest_tag") or None,
        "git": git,
        "config_hash_sha256": cfg_hash,
        "runs": summary_runs,
        "totals": {
            "articles": sum(r["articles_generated"] for r in summary_runs),
            "errors": sum(r["errors"] for r in summary_runs),
            "cost_usd": round(sum(r["cost_usd"] for r in summary_runs), 6),
            "tokens_in": sum(r["tokens_in"] for r in summary_runs),
            "tokens_out": sum(r["tokens_out"] for r in summary_runs),
            "tool_calls": sum(r["tool_calls"] for r in summary_runs),
        },
    }
    (base_dir / "experiment_summary.json").write_text(
        json.dumps(experiment_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- reporte final ----
    print()
    print("=" * 70)
    print(f" EXPERIMENTO — {args.framework}" + (f" / ablation={args.ablation}" if args.ablation else ""))
    print("=" * 70)
    print(f" Experiment ID: {experiment_id}")
    print(f" Repeticiones:  {args.runs}  ({len(ids)} interacciones por run)")
    print(f" Costo total:   ${experiment_summary['totals']['cost_usd']:.4f}")
    print(f" Artículos:     {experiment_summary['totals']['articles']}")
    print(f" Errores:       {experiment_summary['totals']['errors']}")
    print(f" Tool calls:    {experiment_summary['totals']['tool_calls']}")
    print(f" Carpeta:       {base_dir}")
    print()
    print(" Resumen por run:")
    print(f"   {'#':<3} {'estado':<10} {'tiempo':>10} {'artic':>6} {'err':>4} {'tok_in':>8} {'tok_out':>8} {'cost':>8}")
    for r in summary_runs:
        print(
            f"   {r['run_index']:<3} {r['status']:<10} {r['wall_clock_seconds']:>9.1f}s "
            f"{r['articles_generated']:>6} {r['errors']:>4} {r['tokens_in']:>8} "
            f"{r['tokens_out']:>8} ${r['cost_usd']:>7.4f}"
        )
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

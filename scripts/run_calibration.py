#!/usr/bin/env python
"""Ejecuta un framework contra el split de calibración (37 IDs), por lotes.

Cada lote es una invocación independiente al runner con su propio presupuesto
(timeout / tool_calls / cost) definido en `configs/experiments/budget.yaml`.
Los artículos, trazas, métricas y errores de todos los lotes se agregan en
los artefactos canónicos.

Uso:
    .venv/bin/python scripts/run_calibration.py --framework langgraph
    .venv/bin/python scripts/run_calibration.py --framework crewai --batch-size 3
    .venv/bin/python scripts/run_calibration.py --framework baseline_heuristic

Salida:
    runs/calibration/<framework>/
        generated_articles.jsonl
        article_interaction_map.json
        execution_traces.jsonl
        metrics.json
        errors.json
        batches.json
        run_metadata.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Corre un framework sobre el split de calibración (por lotes)."
    )
    parser.add_argument(
        "--framework",
        required=True,
        choices=FRAMEWORK_CHOICES,
        help="Framework o baseline a ejecutar.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Interacciones por invocación del runner (default 5).",
    )
    parser.add_argument(
        "--max-total-cost",
        type=float,
        default=10.0,
        help="Tope global de costo USD acumulado entre lotes (default $10).",
    )
    parser.add_argument(
        "--no-auto-approve",
        dest="auto_approve",
        action="store_false",
        help="Desactiva auto_approve (por defecto: True).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita el número de interacciones (útil para humo rápido).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Sobrescribe runs/calibration/<framework>/.",
    )
    args = parser.parse_args(argv)
    log = setup_logging("INFO")

    if args.batch_size < 1:
        log.error("--batch-size debe ser ≥ 1")
        return 2

    # ---- splits ----
    splits = load_splits()
    ids = list(splits.get("calibration") or [])
    if args.limit:
        ids = ids[: args.limit]
    log.info("Calibración: %d interaction_ids", len(ids))
    if not ids:
        log.error("No hay IDs de calibración en splits.yaml")
        return 2

    log.info(
        "Framework: %s | auto_approve=%s | batch_size=%d | tope_total=$%.2f",
        args.framework,
        args.auto_approve,
        args.batch_size,
        args.max_total_cost,
    )

    # ---- metadata ----
    started_at = datetime.now(timezone.utc)
    git = git_info()
    cfg_hash, cfg_files = config_hash()
    metadata = {
        "framework": args.framework,
        "auto_approve": args.auto_approve,
        "split": "calibration",
        "interaction_ids": ids,
        "batch_size": args.batch_size,
        "max_total_cost_usd": args.max_total_cost,
        "started_at_utc": started_at.isoformat(timespec="seconds"),
        "model_name": load_model_name(),
        "git": git,
        "config_hash_sha256": cfg_hash,
        "config_files_hashed": cfg_files,
        "python_version": sys.version.split()[0],
    }

    out_dir = args.out_dir or (PROJECT_ROOT / "runs" / "calibration" / args.framework)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- run en lotes ----
    t0 = time.time()
    try:
        result = run_in_batches(
            args.framework,
            ids,
            batch_size=args.batch_size,
            auto_approve=args.auto_approve,
            log=log,
            max_total_cost_usd=args.max_total_cost,
        )
    except Exception as e:  # noqa: BLE001
        elapsed = round(time.time() - t0, 3)
        log.exception("Excepción no controlada en run_in_batches: %s", e)
        metadata["completed_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        metadata["wall_clock_seconds"] = elapsed
        metadata["status"] = "crashed"
        metadata["crash_error"] = str(e)
        (out_dir / "run_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 3

    elapsed = round(time.time() - t0, 3)
    completed_at = datetime.now(timezone.utc)
    metadata["completed_at_utc"] = completed_at.isoformat(timespec="seconds")
    metadata["wall_clock_seconds"] = elapsed
    # status global: aborted si max_total_cost frenó la corrida; si no, "completed"
    # incluso cuando lotes individuales hayan abortado por su propio presupuesto.
    if result.get("aborted"):
        metadata["status"] = "aborted_global"
    else:
        metadata["status"] = "completed"
    metadata["batch_count"] = result["metrics"].get("batch_count", 0)
    metadata["batches_aborted"] = result["metrics"].get("batches_aborted", 0)

    # ---- persistencia ----
    write_run_artifacts(out_dir, result)
    (out_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- resumen en stdout ----
    m = result.get("metrics", {}) or {}
    print()
    print("=" * 70)
    print(f" CALIBRACIÓN — {args.framework}  (batched, size={args.batch_size})")
    print("=" * 70)
    print(f"  Estado:                {metadata['status']}")
    print(f"  Wall-clock total:      {elapsed:.2f} s")
    print(f"  Lotes:                 {m.get('batch_count', 0)} (de los cuales {m.get('batches_aborted', 0)} con aborto interno)")
    print(f"  Latencia/lote (mediana, máx): {m.get('latency_per_batch_median', 0):.1f}s / {m.get('latency_per_batch_max', 0):.1f}s")
    print(f"  Artículos generados:   {m.get('articles_generated', 0)}")
    print(f"  Errores totales:       {len(result.get('errors', []))}")
    print(f"  Tokens in/out:         {m.get('total_tokens_in', 0)} / {m.get('total_tokens_out', 0)}")
    print(f"  Cache read/write:      {m.get('cache_read_tokens', 0)} / {m.get('cache_creation_tokens', 0)}")
    print(f"  Tool calls:            {m.get('total_tool_calls', 0)}")
    print(f"  Revisiones acumuladas: {m.get('revision_cycles', 0)}")
    print(f"  Costo total estimado:  ${m.get('cost_usd', 0):.4f}")
    print(f"  Resultados en:         {out_dir}")
    print()
    return 0 if metadata["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

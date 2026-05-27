#!/usr/bin/env python
"""Ejecuta un framework contra el split de calibración (37 IDs).

Uso:
    .venv/bin/python scripts/run_calibration.py --framework langgraph
    .venv/bin/python scripts/run_calibration.py --framework crewai
    .venv/bin/python scripts/run_calibration.py --framework openai_agents
    .venv/bin/python scripts/run_calibration.py --framework baseline_heuristic
    .venv/bin/python scripts/run_calibration.py --framework baseline_prompt

Salida:
    runs/calibration/<framework>/
        generated_articles.jsonl
        article_interaction_map.json
        execution_traces.jsonl
        metrics.json
        errors.json
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
    dispatch_runner,
    git_info,
    load_model_name,
    load_splits,
    setup_logging,
    write_run_artifacts,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Corre un framework sobre el split de calibración."
    )
    parser.add_argument(
        "--framework",
        required=True,
        choices=FRAMEWORK_CHOICES,
        help="Framework o baseline a ejecutar.",
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

    # ---- splits ----
    splits = load_splits()
    ids = list(splits.get("calibration") or [])
    if args.limit:
        ids = ids[: args.limit]
    log.info("Calibración: %d interaction_ids", len(ids))
    if not ids:
        log.error("No hay IDs de calibración en splits.yaml")
        return 2

    # ---- runner dispatch ----
    runner = dispatch_runner(args.framework)
    log.info("Framework: %s | auto_approve=%s", args.framework, args.auto_approve)

    # ---- metadata ----
    started_at = datetime.now(timezone.utc)
    git = git_info()
    cfg_hash, cfg_files = config_hash()
    metadata = {
        "framework": args.framework,
        "auto_approve": args.auto_approve,
        "split": "calibration",
        "interaction_ids": ids,
        "started_at_utc": started_at.isoformat(timespec="seconds"),
        "model_name": load_model_name(),
        "git": git,
        "config_hash_sha256": cfg_hash,
        "config_files_hashed": cfg_files,
        "python_version": sys.version.split()[0],
    }

    out_dir = args.out_dir or (PROJECT_ROOT / "runs" / "calibration" / args.framework)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- run ----
    t0 = time.time()
    try:
        result = runner(ids, auto_approve=args.auto_approve)
    except Exception as e:  # noqa: BLE001
        elapsed = round(time.time() - t0, 3)
        log.exception("Excepción no controlada en el runner: %s", e)
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
    metadata["status"] = "aborted" if result.get("aborted") else "completed"

    # ---- persistencia ----
    write_run_artifacts(out_dir, result)
    (out_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- resumen en stdout ----
    m = result.get("metrics", {}) or {}
    print()
    print("=" * 60)
    print(f" CALIBRACIÓN — {args.framework}")
    print("=" * 60)
    print(f"  Estado:                {metadata['status']}")
    print(f"  Wall-clock:            {elapsed:.2f} s  (métrica interna: {m.get('total_time_seconds', '-')}s)")
    print(f"  Artículos generados:   {m.get('articles_generated', 0)}")
    print(f"  Errores:               {len(result.get('errors', []))}")
    print(f"  Tokens in/out:         {m.get('total_tokens_in', 0)} / {m.get('total_tokens_out', 0)}")
    print(f"  Tool calls:            {m.get('total_tool_calls', 0)}")
    print(f"  Revisiones acumuladas: {m.get('revision_cycles', 0)}")
    print(f"  Costo estimado:        ${m.get('cost_usd', 0):.4f}")
    print(f"  Resultados en:         {out_dir}")
    print()
    return 0 if metadata["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""Verifica integridad del dataset y reporta estadísticas descriptivas.

Uso:
    .venv/bin/python scripts/verify_data.py [--strict]

Validaciones:
- `data/processed/interactions.jsonl` tiene exactamente 183 registros.
- `data/splits/splits.yaml` suma 37 + 109 + 37 = 183.
- Todos los IDs de los splits existen en interactions.
- `data/processed/kb_articles.jsonl` está presente y es legible.

Estadísticas:
- Distribución por product_category, severity, expected_gap_type.
- Turnos promedio, mediana, P90.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Permite ejecutar como `python scripts/verify_data.py` desde la raíz.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._common import (  # noqa: E402
    PROJECT_ROOT,
    load_interactions,
    load_kb_articles,
    load_splits,
    setup_logging,
)


EXPECTED_TOTAL = 183
EXPECTED_CALIBRATION = 37
EXPECTED_EVALUATION = 109
EXPECTED_RESERVE = 37


def _percentile(values, q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verifica el dataset de WhatsApp Davivienda.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Termina con código de salida no-cero al primer fallo.",
    )
    args = parser.parse_args(argv)
    log = setup_logging("INFO")

    failures: list[str] = []
    warnings: list[str] = []

    # ---- interactions ----
    interactions_path = PROJECT_ROOT / "data" / "processed" / "interactions.jsonl"
    if not interactions_path.exists():
        log.error("Falta %s", interactions_path)
        return 2
    interactions = load_interactions()
    log.info("interactions.jsonl: %d registros", len(interactions))
    if len(interactions) != EXPECTED_TOTAL:
        failures.append(
            f"interactions.jsonl tiene {len(interactions)} registros, esperaba {EXPECTED_TOTAL}"
        )

    by_id = {i["interaction_id"]: i for i in interactions}
    duplicates = len(interactions) - len(by_id)
    if duplicates:
        failures.append(f"{duplicates} interaction_ids duplicados")

    # ---- splits ----
    try:
        splits = load_splits()
    except FileNotFoundError as e:
        log.error("Falta splits.yaml: %s", e)
        return 2

    cal = list(splits.get("calibration") or [])
    ev = list(splits.get("evaluation") or [])
    rs = list(splits.get("reserve") or [])
    log.info("splits: cal=%d, eval=%d, reserve=%d", len(cal), len(ev), len(rs))
    if len(cal) != EXPECTED_CALIBRATION:
        failures.append(f"calibration tiene {len(cal)} IDs, esperaba {EXPECTED_CALIBRATION}")
    if len(ev) != EXPECTED_EVALUATION:
        failures.append(f"evaluation tiene {len(ev)} IDs, esperaba {EXPECTED_EVALUATION}")
    if len(rs) != EXPECTED_RESERVE:
        failures.append(f"reserve tiene {len(rs)} IDs, esperaba {EXPECTED_RESERVE}")

    # Cobertura: cada ID de splits debe existir en interactions; sin overlap entre splits.
    union = cal + ev + rs
    if len(union) != len(set(union)):
        failures.append("hay overlap entre splits (un mismo ID en > 1 split)")
    missing = [i for i in union if i not in by_id]
    if missing:
        failures.append(f"{len(missing)} IDs de splits no existen en interactions (ej.: {missing[:5]})")
    not_in_splits = [iid for iid in by_id if iid not in set(union)]
    if not_in_splits:
        warnings.append(
            f"{len(not_in_splits)} interactions no están en ningún split (ej.: {not_in_splits[:5]})"
        )

    # ---- kb_articles ----
    kb_path = PROJECT_ROOT / "data" / "processed" / "kb_articles.jsonl"
    if not kb_path.exists():
        warnings.append(f"Falta {kb_path} (no es bloqueante)")
    else:
        kb = load_kb_articles()
        log.info("kb_articles.jsonl: %d registros", len(kb))

    # ---- estadísticas descriptivas ----
    cat = Counter()
    sev = Counter()
    gap = Counter()
    qtypes = Counter()
    turns_per_interaction = []
    for i in interactions:
        m = i.get("metadata") or {}
        cat[m.get("product_category") or "?"] += 1
        sev[m.get("severity") or "?"] += 1
        gap[m.get("expected_gap_type") or "?"] += 1
        qtypes[m.get("query_type") or "?"] += 1
        turns_per_interaction.append(len(i.get("turns") or []))

    avg_turns = sum(turns_per_interaction) / max(1, len(turns_per_interaction))
    med_turns = _percentile(turns_per_interaction, 0.5)
    p90_turns = _percentile(turns_per_interaction, 0.9)

    print()
    print("=" * 60)
    print(" DISTRIBUCIONES")
    print("=" * 60)
    print(f"\nproduct_category ({len(cat)} valores):")
    for k, v in cat.most_common():
        print(f"  {k:<25} {v:>4}  ({100*v/len(interactions):5.1f}%)")
    print(f"\nseverity ({len(sev)} valores):")
    for k, v in sev.most_common():
        print(f"  {k:<25} {v:>4}  ({100*v/len(interactions):5.1f}%)")
    print(f"\nexpected_gap_type ({len(gap)} valores):")
    for k, v in gap.most_common():
        print(f"  {k:<25} {v:>4}  ({100*v/len(interactions):5.1f}%)")
    print(f"\nquery_type ({len(qtypes)} valores):")
    for k, v in qtypes.most_common():
        print(f"  {k:<25} {v:>4}  ({100*v/len(interactions):5.1f}%)")
    print()
    print(f"turnos por interacción — promedio: {avg_turns:.2f} | mediana: {med_turns:.1f} | P90: {p90_turns:.1f}")
    print()

    # ---- resumen ----
    print("=" * 60)
    print(" RESUMEN DE VERIFICACIÓN")
    print("=" * 60)
    if not failures:
        print("✓ Todas las verificaciones duras pasaron.")
    else:
        print(f"✗ {len(failures)} fallo(s):")
        for f in failures:
            print(f"  - {f}")
    if warnings:
        print(f"\n⚠ {len(warnings)} advertencia(s):")
        for w in warnings:
            print(f"  - {w}")
    print()

    if failures and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

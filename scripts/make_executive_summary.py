#!/usr/bin/env python
"""Genera el resumen ejecutivo comparando el estudio principal (split evaluation)
con la validación de estabilidad (split reserve).

Lee los dos JSON producidos por compute_metrics.py y escribe:
    eval/results/main_table.md       — tabla principal (3 frameworks + 2 baselines)
    eval/results/reserve_table.md    — tabla de reserva (3 frameworks)
    eval/results/EXECUTIVE_SUMMARY.md — resumen ejecutivo: ¿se mantienen los patrones?

Uso:
    .venv/bin/python scripts/make_executive_summary.py \\
        --main eval/results/main_metrics.json \\
        --reserve eval/results/reserve_metrics.json \\
        --out-dir eval/results
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Frameworks de orquestación (los baselines solo están en el estudio principal).
FRAMEWORKS = ("langgraph", "crewai", "openai_agents")
BASELINES = ("baseline_heuristic", "baseline_prompt")

# Columnas: (clave_md, etiqueta, extractor, formato, "higher_is_better"|"lower"|None)
def _metrics_row(fw: Dict[str, Any]) -> Dict[str, Optional[float]]:
    c = fw.get("consolidation", {}) or {}
    q = fw.get("quality", {}) or {}
    e = fw.get("engineering", {}) or {}
    lat = e.get("latency_seconds", {}) or {}
    cost = e.get("cost_usd", {}) or {}
    return {
        "n_runs": fw.get("n_runs"),
        "arts": c.get("articles_avg"),
        "cov": c.get("interaction_coverage_pct_avg"),
        "kcs": (q.get("kcs_compliance_avg") or 0) * 100 if q.get("kcs_compliance_avg") is not None else None,
        "ev": (q.get("evidence_coverage_avg") or 0) * 100 if q.get("evidence_coverage_avg") is not None else None,
        "lat_med": lat.get("median"),
        "lat_p90": lat.get("p90"),
        "cost": cost.get("median"),
        "tools": e.get("tool_calls_avg"),
        "fail": e.get("failure_rate_pct"),
        "loc": e.get("loc"),
    }


def _f(v: Optional[float], fmt: str = "{:.1f}") -> str:
    if v is None:
        return "—"
    try:
        return fmt.format(v)
    except (ValueError, TypeError):
        return str(v)


COLS = [
    ("n_runs", "runs", "{:.0f}"),
    ("arts", "arts", "{:.1f}"),
    ("cov", "cov%", "{:.1f}"),
    ("kcs", "KCS%", "{:.0f}"),
    ("ev", "ev%", "{:.0f}"),
    ("lat_med", "lat_med", "{:.1f}"),
    ("lat_p90", "lat_p90", "{:.1f}"),
    ("cost", "cost$", "{:.3f}"),
    ("tools", "tools", "{:.0f}"),
    ("fail", "fail%", "{:.0f}"),
    ("loc", "LOC", "{:.0f}"),
]


def _md_table(report: Dict[str, Any], order: List[str]) -> str:
    fws = report.get("frameworks", {})
    head = "| framework | " + " | ".join(label for _, label, _ in COLS) + " |"
    sep = "|" + "---|" * (len(COLS) + 1)
    lines = [head, sep]
    for name in order:
        fw = fws.get(name)
        if not fw:
            continue
        row = _metrics_row(fw)
        cells = " | ".join(_f(row[k], fmt) for k, _, fmt in COLS)
        lines.append(f"| {name} | {cells} |")
    return "\n".join(lines)


# Métricas para el análisis de estabilidad: (clave, etiqueta, dirección)
ROBUST_METRICS = [
    ("kcs", "Cumplimiento KCS (KCS%)", "higher"),
    ("ev", "Cobertura de evidencia (ev%)", "higher"),
    ("cov", "Cobertura de interacciones (cov%)", "higher"),
    ("cost", "Costo mediano por run ($)", "lower"),
    ("tools", "Tool calls promedio", "lower"),
    ("fail", "Tasa de fallo (fail%)", "lower"),
    ("lat_med", "Latencia mediana (s)", "lower"),
]


# Umbral de estabilidad: un flip de ranking solo cuenta como cambio REAL si la
# diferencia entre los dos frameworks supera este % relativo en AMBOS splits.
# Flips entre frameworks separados por menos de esto se consideran empates/ruido.
ROBUST_THRESHOLD = 0.05  # 5% relativo


def _rank(values: Dict[str, Optional[float]], direction: str) -> List[str]:
    """Ordena frameworks de mejor a peor según la dirección. Ignora None."""
    present = [(k, v) for k, v in values.items() if v is not None]
    reverse = direction == "higher"
    present.sort(key=lambda kv: kv[1], reverse=reverse)
    return [k for k, _ in present]


def _rel_gap(a: float, b: float) -> float:
    """Diferencia relativa con signo: (a-b)/max(|a|,|b|). 0 si ambos ~0."""
    denom = max(abs(a), abs(b))
    if denom < 1e-9:
        return 0.0
    return (a - b) / denom


def _classify_metric(
    main_vals: Dict[str, float], res_vals: Dict[str, float]
) -> tuple:
    """Detecta inversiones de orden entre pares de frameworks y las clasifica
    como contradicción significativa (>5% en ambos splits) o empate (ruido).

    Devuelve (contradictions, ties) como listas de pares (A, B).
    """
    common = [
        f for f in FRAMEWORKS
        if f in main_vals and f in res_vals
        and main_vals[f] is not None and res_vals[f] is not None
    ]
    contradictions: List[tuple] = []
    ties: List[tuple] = []
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            a, b = common[i], common[j]
            m_sign = (main_vals[a] > main_vals[b]) - (main_vals[a] < main_vals[b])
            r_sign = (res_vals[a] > res_vals[b]) - (res_vals[a] < res_vals[b])
            if m_sign == 0 or r_sign == 0 or m_sign == r_sign:
                continue  # mismo orden (o empate exacto): sin inversión
            m_gap = abs(_rel_gap(main_vals[a], main_vals[b]))
            r_gap = abs(_rel_gap(res_vals[a], res_vals[b]))
            if m_gap > ROBUST_THRESHOLD and r_gap > ROBUST_THRESHOLD:
                contradictions.append((a, b))
            else:
                ties.append((a, b))
    return contradictions, ties


def _robustness_section(main: Dict[str, Any], reserve: Dict[str, Any]) -> str:
    mfws = main.get("frameworks", {})
    rfws = reserve.get("frameworks", {})
    mrows = {f: _metrics_row(mfws[f]) for f in FRAMEWORKS if f in mfws}
    rrows = {f: _metrics_row(rfws[f]) for f in FRAMEWORKS if f in rfws}

    out: List[str] = []
    out.append("## 3. ¿Se mantienen los patrones en la reserva?\n")
    out.append(
        "Comparación de los 3 frameworks de orquestación entre el estudio "
        "principal (50 interacciones × 3 runs) y la validación de estabilidad "
        "(37 interacciones × 1 run). Un cambio de ranking solo se considera "
        "**real** si la diferencia entre frameworks supera el "
        f"**{ROBUST_THRESHOLD*100:.0f}% relativo en ambos splits**; los flips "
        "entre valores casi empatados se marcan como ruido y NO penalizan la "
        "estabilidad.\n"
    )

    preserved = 0
    total = 0
    rank_lines = ["| Métrica | Ranking principal | Ranking reserva | Veredicto |",
                  "|---|---|---|---|"]
    for key, label, direction in ROBUST_METRICS:
        main_vals = {f: mrows[f][key] for f in mrows}
        res_vals = {f: rrows[f][key] for f in rrows}
        common = [f for f in FRAMEWORKS if f in main_vals and f in res_vals
                  and main_vals[f] is not None and res_vals[f] is not None]
        if len(common) < 2:
            rank_lines.append(f"| {label} | (datos insuf.) | (datos insuf.) | — |")
            continue
        mr = _rank({f: main_vals[f] for f in common}, direction)
        rr = _rank({f: res_vals[f] for f in common}, direction)
        contradictions, ties = _classify_metric(
            {f: main_vals[f] for f in common}, {f: res_vals[f] for f in common}
        )
        total += 1
        if not contradictions:
            preserved += 1
            if mr == rr:
                verdict = "✅ se mantiene"
            else:
                verdict = f"✅ estable (flip <{ROBUST_THRESHOLD*100:.0f}%: empate)"
        else:
            pairs = ", ".join(f"{a}≠{b}" for a, b in contradictions)
            verdict = f"⚠️ cambia ({pairs})"
        rank_lines.append(
            f"| {label} | {' > '.join(mr)} | {' > '.join(rr)} | {verdict} |"
        )
    out.append("\n".join(rank_lines))
    out.append("")

    # Tabla de deltas por framework y métrica clave de calidad
    out.append("### Deltas por framework (reserva − principal)\n")
    delta_keys = [("kcs", "KCS%"), ("ev", "ev%"),
                  ("cov", "cov%"), ("cost", "cost$"), ("tools", "tools")]
    dh = "| framework | " + " | ".join(lbl for _, lbl in delta_keys) + " |"
    out.append(dh)
    out.append("|" + "---|" * (len(delta_keys) + 1))
    for f in FRAMEWORKS:
        if f not in mrows or f not in rrows:
            continue
        cells = []
        for k, _ in delta_keys:
            mv, rv = mrows[f][k], rrows[f][k]
            if mv is None or rv is None:
                cells.append("—")
            else:
                d = rv - mv
                fmt = "{:+.3f}" if k == "cost" else "{:+.1f}"
                cells.append(fmt.format(d))
        out.append(f"| {f} | " + " | ".join(cells) + " |")
    out.append("")

    # Veredicto
    pct = (preserved / total * 100) if total else 0
    if pct >= 75:
        verdict = (f"**✅ Los patrones se mantienen.** {preserved}/{total} rankings "
                   f"de métricas se conservan ({pct:.0f}%). Los hallazgos del estudio "
                   "principal son estables frente al split de reserva.")
    elif pct >= 50:
        verdict = (f"**⚠️ Estabilidad parcial.** {preserved}/{total} rankings se conservan "
                   f"({pct:.0f}%). Revisar las métricas marcadas como 'cambia' antes de "
                   "generalizar las conclusiones.")
    else:
        verdict = (f"**❌ Patrones inestables.** Solo {preserved}/{total} rankings se "
                   f"conservan ({pct:.0f}%). Los resultados del estudio principal NO se "
                   "replican en la reserva — interpretar con cautela.")
    out.append("### Veredicto de estabilidad\n")
    out.append(verdict)
    out.append("")
    out.append(
        "> Nota metodológica: la reserva tiene 1 run por framework (vs 3 en el "
        "principal) y 37 vs 50 interacciones, por lo que su varianza es mayor. "
        "Un cambio de ranking en métricas con valores muy cercanos no implica "
        "necesariamente un patrón distinto."
    )
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--main", type=Path, required=True)
    p.add_argument("--reserve", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, default=Path("eval/results"))
    p.add_argument("--timestamp", type=str, default=None,
                   help="ISO timestamp para el encabezado (default: ahora UTC).")
    args = p.parse_args(argv)

    main_report = json.loads(args.main.read_text(encoding="utf-8"))
    reserve_report = json.loads(args.reserve.read_text(encoding="utf-8"))
    ts = args.timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    main_order = list(BASELINES) + list(FRAMEWORKS)
    main_tbl = _md_table(main_report, main_order)
    reserve_tbl = _md_table(reserve_report, list(FRAMEWORKS))

    (args.out_dir / "main_table.md").write_text(
        f"# Tabla principal — split evaluation (50 interacciones × 3 runs)\n\n{main_tbl}\n",
        encoding="utf-8",
    )
    (args.out_dir / "reserve_table.md").write_text(
        f"# Tabla de estabilidad — split reserve (37 interacciones × 1 run)\n\n{reserve_tbl}\n",
        encoding="utf-8",
    )

    doc = [
        "# Resumen ejecutivo — Comparación de frameworks de agentes",
        "",
        f"_Generado: {ts}_",
        "",
        "Comparación empírica de LangGraph, CrewAI y OpenAI Agents SDK para "
        "generación de artículos de KB (caso Davivienda). Modelo base idéntico "
        "(claude-sonnet-4-6); la única variable es el framework de orquestación.",
        "",
        "## 1. Estudio principal — split evaluation (50 interacciones × 3 runs)",
        "",
        main_tbl,
        "",
        "Leyenda: arts=artículos prom., cov%=cobertura interacciones, KCS%=cumplimiento "
        "plantilla, ev%=cobertura evidencia, "
        "lat=latencia (s), cost$=costo mediano, tools=tool calls prom., fail%=tasa de "
        "fallo, LOC=líneas de implementación.",
        "",
        "## 2. Validación de estabilidad — split reserve (37 interacciones × 1 run)",
        "",
        reserve_tbl,
        "",
        _robustness_section(main_report, reserve_report),
    ]
    (args.out_dir / "EXECUTIVE_SUMMARY.md").write_text("\n".join(doc) + "\n", encoding="utf-8")

    print(f"[summary] escrito EXECUTIVE_SUMMARY.md + main_table.md + reserve_table.md en {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Agrega los runs de runs/experiment/ y calcula métricas por framework.

Uso:
    .venv/bin/python scripts/compute_metrics.py
    .venv/bin/python scripts/compute_metrics.py --runs-dir runs/calibration

Categorías:
    Consolidación: nº artículos, ratio interacciones/artículos, solapamiento
                   temático (pares con cosine > 0.7), cobertura de interacciones.
    Calidad:       cumplimiento plantilla KCS, cobertura de evidencia,
                   similitud con artículos de referencia (si está kb_articles.jsonl).
    Ingeniería:    latencia (mediana, P90), costo (mediana, total),
                   tool calls (promedio), tasa de fallos, LOC por framework.

Salida:
    eval/results/automatic_metrics.json
    Tabla comparativa por framework en stdout.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._common import (  # noqa: E402
    PROJECT_ROOT,
    load_interactions,
    load_kb_articles,
    setup_logging,
)


# ---------------------------------------------------------------------------
# Lectura de runs
# ---------------------------------------------------------------------------


def _iter_run_dirs(runs_root: Path):
    """Yields (framework, ablation_or_none, run_dir) para cada run encontrado.

    Soporta dos layouts:
    - Plano:   runs/<x>/<framework>/{metrics.json, ...}                (calibración)
    - Anidado: runs/<x>/<framework>/[ablation/]run_<n>/{metrics.json}  (experimento)
    """
    if not runs_root.exists():
        return
    for framework_dir in sorted(runs_root.iterdir()):
        if not framework_dir.is_dir():
            continue
        framework = framework_dir.name

        # Layout plano: metrics.json directamente bajo framework_dir.
        if (framework_dir / "metrics.json").exists():
            yield framework, None, framework_dir
            continue

        # Layout anidado: run_* directos
        direct_runs = sorted(framework_dir.glob("run_*"))
        for run_dir in direct_runs:
            yield framework, None, run_dir

        # Subdirectorios de ablación con run_* dentro
        for sub in sorted(framework_dir.iterdir()):
            if not sub.is_dir() or sub.name.startswith("run_"):
                continue
            for run_dir in sorted(sub.glob("run_*")):
                yield framework, sub.name, run_dir


def _read_run(run_dir: Path) -> Optional[Dict[str, Any]]:
    metrics_p = run_dir / "metrics.json"
    if not metrics_p.exists():
        return None
    articles_p = run_dir / "generated_articles.jsonl"
    map_p = run_dir / "article_interaction_map.json"
    errors_p = run_dir / "errors.json"
    meta_p = run_dir / "run_metadata.json"

    articles: List[Dict[str, Any]] = []
    if articles_p.exists():
        for line in articles_p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                articles.append(json.loads(line))

    interaction_map = (
        json.loads(map_p.read_text(encoding="utf-8")) if map_p.exists() else {}
    )
    metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
    errors = json.loads(errors_p.read_text(encoding="utf-8")) if errors_p.exists() else []
    metadata = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}

    return {
        "run_dir": str(run_dir),
        "articles": articles,
        "interaction_map": interaction_map,
        "metrics": metrics,
        "errors": errors,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def _article_text(article_record: Dict[str, Any]) -> str:
    """Texto para similitud temática: title + problem + resolution + key_fragments."""
    art = article_record.get("article") or article_record
    parts: List[str] = []
    if art.get("title"):
        parts.append(art["title"])
    if art.get("problem"):
        parts.append(art["problem"])
    res = art.get("resolution")
    if isinstance(res, list):
        parts.extend(s for s in res if isinstance(s, str))
    elif isinstance(res, str):
        parts.append(res)
    ev = art.get("evidence_pack") or {}
    parts.extend(f for f in ev.get("key_fragments", []) or [] if isinstance(f, str))
    return " \n ".join(parts) or "(vacío)"


def _kcs_compliance(article_record: Dict[str, Any]) -> Dict[str, Any]:
    art = article_record.get("article") or article_record
    required_top = ["title", "environment", "problem", "resolution", "evidence_pack", "metadata"]
    env_required = ["product", "segment"]
    ev_required = ["interaction_ids", "key_fragments", "claim_evidence_map"]
    md_required = ["status", "author", "confidence", "created_at"]

    present = 0
    total = (
        len(required_top)
        + len(env_required)
        + len(ev_required)
        + len(md_required)
    )

    for k in required_top:
        if art.get(k) not in (None, "", []):
            present += 1
    env = art.get("environment") or {}
    for k in env_required:
        if env.get(k) not in (None, ""):
            present += 1
    ev = art.get("evidence_pack") or {}
    for k in ev_required:
        v = ev.get(k)
        if v not in (None, "", [], {}):
            present += 1
    md = art.get("metadata") or {}
    for k in md_required:
        if md.get(k) not in (None, ""):
            present += 1

    return {"present": present, "total": total, "ratio": present / total}


def _evidence_coverage(article_record: Dict[str, Any]) -> float:
    art = article_record.get("article") or article_record
    ev = art.get("evidence_pack") or {}
    cmap = ev.get("claim_evidence_map") or {}
    if not isinstance(cmap, dict) or not cmap:
        return 0.0
    with_evidence = sum(
        1 for v in cmap.values() if isinstance(v, list) and len(v) >= 1
    )
    return with_evidence / len(cmap)


def _consolidation(
    articles: List[Dict[str, Any]], input_ids: List[str]
) -> Dict[str, Any]:
    n_articles = len(articles)
    n_inputs = len(input_ids)
    ratio = n_inputs / n_articles if n_articles else None

    covered: set = set()
    for art in articles:
        ev = (art.get("article") or {}).get("evidence_pack") or {}
        for iid in ev.get("interaction_ids", []) or []:
            if isinstance(iid, str):
                covered.add(iid)
    coverage = len(covered & set(input_ids)) / max(1, n_inputs)

    topical_overlap_pairs = 0
    if n_articles >= 2:
        texts = [_article_text(a) for a in articles]
        try:
            vec = TfidfVectorizer(
                max_features=2048,
                ngram_range=(1, 2),
                lowercase=True,
                strip_accents="unicode",
            ).fit_transform(texts)
            sim = cosine_similarity(vec)
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    if sim[i, j] > 0.7:
                        topical_overlap_pairs += 1
        except ValueError:
            # vocabulario vacío
            pass

    return {
        "articles": n_articles,
        "input_interactions": n_inputs,
        "consolidation_ratio": ratio,
        "interaction_coverage_pct": coverage * 100,
        "topical_overlap_pairs_gt_0_7": topical_overlap_pairs,
    }


def _quality(
    articles: List[Dict[str, Any]],
    reference_articles: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    if not articles:
        return {
            "kcs_compliance_avg": 0.0,
            "kcs_fully_compliant_pct": 0.0,
            "evidence_coverage_avg": 0.0,
            "reference_similarity_avg": None,
            "reference_similarity_max_avg": None,
        }

    compliance = [_kcs_compliance(a) for a in articles]
    avg_compliance = sum(c["ratio"] for c in compliance) / len(compliance)
    fully = sum(1 for c in compliance if c["present"] == c["total"])
    evidence_cov = [_evidence_coverage(a) for a in articles]

    similarity_avg = None
    similarity_max_avg = None
    if reference_articles:
        gen_texts = [_article_text(a) for a in articles]
        ref_texts: List[str] = []
        for ref in reference_articles:
            res = ref.get("resolution")
            if isinstance(res, list):
                # Cada item puede ser str o dict (algunas KBs tienen
                # {"step": ..., "description": ...}).
                res_parts: List[str] = []
                for item in res:
                    if isinstance(item, str):
                        res_parts.append(item)
                    elif isinstance(item, dict):
                        res_parts.append(
                            " ".join(str(v) for v in item.values() if isinstance(v, (str, int, float)))
                        )
                res_str = " ".join(res_parts)
            elif isinstance(res, str):
                res_str = res
            else:
                res_str = ""
            ref_texts.append(
                " \n ".join(
                    filter(None, [ref.get("title"), ref.get("problem"), res_str])
                )
            )
        try:
            vec = TfidfVectorizer(
                max_features=4096,
                ngram_range=(1, 2),
                lowercase=True,
                strip_accents="unicode",
            ).fit(gen_texts + ref_texts)
            G = vec.transform(gen_texts)
            R = vec.transform(ref_texts)
            sim = cosine_similarity(G, R)
            similarity_max_avg = float(np.mean(sim.max(axis=1)))
            similarity_avg = float(np.mean(sim))
        except ValueError:
            pass

    return {
        "kcs_compliance_avg": avg_compliance,
        "kcs_fully_compliant_pct": (fully / len(articles)) * 100,
        "evidence_coverage_avg": sum(evidence_cov) / len(evidence_cov),
        "reference_similarity_avg": similarity_avg,
        "reference_similarity_max_avg": similarity_max_avg,
    }


def _percentile(values, q: float) -> Optional[float]:
    if not values:
        return None
    return float(np.percentile(values, q * 100))


def _framework_loc(framework: str) -> int:
    """Cuenta líneas de código del framework (excluye tests y __pycache__)."""
    if framework.startswith("baseline_"):
        if framework == "baseline_heuristic":
            files = [PROJECT_ROOT / "src" / "baselines" / "heuristic.py"]
        elif framework == "baseline_prompt":
            files = [PROJECT_ROOT / "src" / "baselines" / "single_prompt.py"]
        else:
            return 0
    else:
        root = PROJECT_ROOT / "src" / "frameworks" / framework
        if not root.exists():
            return 0
        files = [
            p
            for p in root.glob("*.py")
            if not p.name.startswith("test_") and p.name != "__init__.py"
        ]
    total = 0
    for f in files:
        total += sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
    return total


def _engineering(runs: List[Dict[str, Any]], framework: str) -> Dict[str, Any]:
    if not runs:
        return {"loc": _framework_loc(framework)}
    times = [r["metrics"].get("total_time_seconds") or 0 for r in runs]
    costs = [r["metrics"].get("cost_usd") or 0 for r in runs]
    tools = [r["metrics"].get("total_tool_calls") or 0 for r in runs]
    failures = sum(
        1 for r in runs if (r["metadata"].get("status") or "completed") != "completed"
    )
    return {
        "n_runs": len(runs),
        "latency_seconds": {
            "median": statistics.median(times),
            "p90": _percentile(times, 0.9),
            "min": min(times),
            "max": max(times),
        },
        "cost_usd": {
            "median": statistics.median(costs),
            "total": sum(costs),
        },
        "tool_calls_avg": statistics.mean(tools) if tools else 0,
        "failure_rate_pct": (failures / len(runs)) * 100,
        "loc": _framework_loc(framework),
    }


# ---------------------------------------------------------------------------
# Agregación por framework
# ---------------------------------------------------------------------------


def aggregate(
    runs_root: Path, reference_articles: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    by_framework: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]] = defaultdict(list)

    for framework, ablation, run_dir in _iter_run_dirs(runs_root):
        run = _read_run(run_dir)
        if run is None:
            continue
        by_framework[(framework, ablation)].append(run)

    output: Dict[str, Any] = {"runs_root": str(runs_root), "frameworks": {}}

    for (framework, ablation), runs in sorted(by_framework.items()):
        key = framework if not ablation else f"{framework}:{ablation}"

        per_run_consolidation = []
        per_run_quality = []
        for r in runs:
            input_ids = r["metadata"].get("interaction_ids") or list(
                r["interaction_map"].keys() if r["interaction_map"] else []
            )
            cons = _consolidation(r["articles"], input_ids)
            qual = _quality(r["articles"], reference_articles)
            per_run_consolidation.append(cons)
            per_run_quality.append(qual)

        # Promedios entre runs
        def _avg(key_path: str) -> Optional[float]:
            keys = key_path.split(".")

            def _dig(d):
                for k in keys:
                    d = d.get(k) if isinstance(d, dict) else None
                return d

            vals = [v for v in (_dig(c) for c in per_run_quality + per_run_consolidation) if isinstance(v, (int, float))]
            return float(sum(vals) / len(vals)) if vals else None

        # Agregaciones puntuales
        agg_consolidation = {
            "articles_avg": float(np.mean([c["articles"] for c in per_run_consolidation])) if per_run_consolidation else 0,
            "consolidation_ratio_avg": float(
                np.mean([c["consolidation_ratio"] for c in per_run_consolidation if c["consolidation_ratio"]])
            ) if any(c["consolidation_ratio"] for c in per_run_consolidation) else None,
            "interaction_coverage_pct_avg": float(np.mean([c["interaction_coverage_pct"] for c in per_run_consolidation])) if per_run_consolidation else 0,
            "topical_overlap_pairs_gt_0_7_avg": float(np.mean([c["topical_overlap_pairs_gt_0_7"] for c in per_run_consolidation])) if per_run_consolidation else 0,
        }
        agg_quality = {
            "kcs_compliance_avg": float(np.mean([q["kcs_compliance_avg"] for q in per_run_quality])) if per_run_quality else 0,
            "kcs_fully_compliant_pct_avg": float(np.mean([q["kcs_fully_compliant_pct"] for q in per_run_quality])) if per_run_quality else 0,
            "evidence_coverage_avg": float(np.mean([q["evidence_coverage_avg"] for q in per_run_quality])) if per_run_quality else 0,
            "reference_similarity_avg": (
                float(np.mean([q["reference_similarity_avg"] for q in per_run_quality if q["reference_similarity_avg"] is not None]))
                if any(q["reference_similarity_avg"] is not None for q in per_run_quality)
                else None
            ),
            "reference_similarity_max_avg": (
                float(np.mean([q["reference_similarity_max_avg"] for q in per_run_quality if q["reference_similarity_max_avg"] is not None]))
                if any(q["reference_similarity_max_avg"] is not None for q in per_run_quality)
                else None
            ),
        }
        engineering = _engineering(runs, framework)

        output["frameworks"][key] = {
            "framework": framework,
            "ablation": ablation,
            "n_runs": len(runs),
            "consolidation": agg_consolidation,
            "quality": agg_quality,
            "engineering": engineering,
            "per_run": [
                {
                    "run_dir": r["run_dir"],
                    "status": r["metadata"].get("status"),
                    "consolidation": per_run_consolidation[i],
                    "quality": per_run_quality[i],
                    "metrics": r["metrics"],
                }
                for i, r in enumerate(runs)
            ],
        }

    return output


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------


def _fmt(v, fmt="{:.2f}"):
    if v is None:
        return "-"
    if isinstance(v, float):
        return fmt.format(v)
    return str(v)


def _print_table(report: Dict[str, Any]) -> None:
    fws = report["frameworks"]
    if not fws:
        print("\n(no se encontraron runs para reportar)\n")
        return

    print()
    print("=" * 110)
    print(" MÉTRICAS POR FRAMEWORK")
    print("=" * 110)
    header = (
        f"{'framework':<28} {'runs':>4} {'arts':>5} {'cov%':>5} "
        f"{'KCS%':>5} {'ev%':>5} {'simK':>5} "
        f"{'lat_med':>8} {'lat_p90':>8} {'cost$':>7} {'tools':>6} {'fail%':>6} {'LOC':>5}"
    )
    print(header)
    print("-" * len(header))
    for key, fw in fws.items():
        c = fw["consolidation"]
        q = fw["quality"]
        e = fw["engineering"]
        print(
            f"{key:<28} {fw['n_runs']:>4} "
            f"{_fmt(c['articles_avg'], '{:.1f}'):>5} "
            f"{_fmt(c['interaction_coverage_pct_avg'], '{:.1f}'):>5} "
            f"{_fmt(q['kcs_compliance_avg']*100, '{:.0f}'):>5} "
            f"{_fmt(q['evidence_coverage_avg']*100, '{:.0f}'):>5} "
            f"{_fmt((q['reference_similarity_max_avg'] or 0)*100, '{:.0f}'):>5} "
            f"{_fmt(e['latency_seconds']['median'], '{:.1f}'):>8} "
            f"{_fmt(e['latency_seconds']['p90'], '{:.1f}'):>8} "
            f"{_fmt(e['cost_usd']['median'], '{:.3f}'):>7} "
            f"{_fmt(e['tool_calls_avg'], '{:.0f}'):>6} "
            f"{_fmt(e['failure_rate_pct'], '{:.0f}'):>6} "
            f"{e['loc']:>5}"
        )
    print()
    print(" Leyenda: arts=artículos promedio, cov%=cobertura interacciones, KCS%=cumplimiento plantilla,")
    print("          ev%=cobertura evidencia, simK%=mejor similitud TF-IDF vs KB referencia,")
    print("          lat_med/p90=latencia (s), cost$=costo mediano, tools=tool calls promedio, LOC=líneas.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Computa métricas comparativas sobre los runs."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=PROJECT_ROOT / "runs" / "experiment",
        help="Carpeta raíz con los runs (default: runs/experiment).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "eval" / "results" / "automatic_metrics.json",
        help="Ruta del JSON de salida.",
    )
    parser.add_argument(
        "--no-reference",
        action="store_true",
        help="No usar kb_articles.jsonl como referencia.",
    )
    args = parser.parse_args(argv)
    log = setup_logging("INFO")

    reference = None if args.no_reference else load_kb_articles()
    if reference is not None:
        log.info("Referencia: %d artículos en kb_articles.jsonl", len(reference))

    report = aggregate(args.runs_dir, reference)
    report["reference_articles_count"] = len(reference) if reference else 0
    report["input_corpus_total"] = len(load_interactions())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Resultados guardados en %s", args.out)

    _print_table(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

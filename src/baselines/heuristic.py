"""Baseline heurístico — TF-IDF + KMeans, sin LLM.

Pipeline:
1. Carga las interacciones (via get_interaction).
2. Construye una representación textual por interacción (mensajes del cliente +
   knowledge_extracted.main_topic + key_facts).
3. Vectoriza con TF-IDF, agrupa con KMeans (k = sqrt(n) acotado).
4. Por cada cluster: identifica el centroide y selecciona la interacción más
   cercana como "interacción representativa".
5. Rellena la plantilla KCS con extracción puramente mecánica:
   - title       ← main_topic del representante
   - environment ← product_category + segmento por defecto
   - problem     ← primer mensaje del cliente del representante
   - resolution  ← key_facts del cluster, deduplicados y numerados
   - evidence    ← todos los interaction_ids del cluster

Sin Claude, sin tools agénticas, sin verificación. Costo cero.
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.tools.tool_contract import get_interaction


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _interaction_text(interaction: Dict[str, Any]) -> str:
    parts: List[str] = []
    ke = interaction.get("knowledge_extracted") or {}
    if ke.get("main_topic"):
        parts.append(ke["main_topic"])
    for f in ke.get("key_facts", []) or []:
        parts.append(f)
    for t in interaction.get("turns", []) or []:
        if t.get("role") == "cliente":
            msg = (t.get("message") or "").strip()
            if msg:
                parts.append(msg)
    meta = interaction.get("metadata") or {}
    if meta.get("product_specific"):
        parts.append(meta["product_specific"])
    return " \n ".join(parts)


def _first_client_message(interaction: Dict[str, Any]) -> str:
    for t in interaction.get("turns", []) or []:
        if t.get("role") == "cliente":
            return (t.get("message") or "").strip()
    return ""


def _pick_k(n: int) -> int:
    if n <= 0:
        return 0
    if n <= 2:
        return n
    return max(1, min(n, int(round(math.sqrt(n)))))


def _dedup_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        x_clean = (x or "").strip()
        if not x_clean or x_clean in seen:
            continue
        seen.add(x_clean)
        out.append(x_clean)
    return out


def _build_resolution(cluster_interactions: List[Dict[str, Any]]) -> List[str]:
    """Concatena key_facts del cluster en pasos numerados, deduplicados."""
    facts: List[str] = []
    for inter in cluster_interactions:
        ke = inter.get("knowledge_extracted") or {}
        for f in ke.get("key_facts", []) or []:
            facts.append(f)
    facts = _dedup_preserve_order(facts)
    if not facts:
        facts = ["Consultar al asesor para conocer el procedimiento exacto."]
    return [f"{i}. {f}" for i, f in enumerate(facts, start=1)]


def _build_claim_map(
    cluster_interactions: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Para cada key_fact único, mapea a las interacciones que lo contienen."""
    claim_map: Dict[str, List[str]] = {}
    for inter in cluster_interactions:
        iid = inter["interaction_id"]
        ke = inter.get("knowledge_extracted") or {}
        for fact in ke.get("key_facts", []) or []:
            fact_clean = (fact or "").strip()
            if not fact_clean:
                continue
            claim_map.setdefault(fact_clean, [])
            if iid not in claim_map[fact_clean]:
                claim_map[fact_clean].append(iid)
    if not claim_map:
        # Salvaguarda: el validador exige al menos 1 entrada.
        claim_map["Información derivada de interacciones del corpus"] = [
            inter["interaction_id"] for inter in cluster_interactions
        ]
    return claim_map


def _build_article(
    cluster_interactions: List[Dict[str, Any]], representative: Dict[str, Any]
) -> Dict[str, Any]:
    rep_meta = representative.get("metadata") or {}
    rep_ke = representative.get("knowledge_extracted") or {}
    title = rep_ke.get("main_topic") or "Artículo derivado heurísticamente"
    # title ≤ 150 chars (regla del validador).
    title = title[:148]
    problem = _first_client_message(representative) or (
        "Consulta del cliente sobre " + (rep_meta.get("product_specific") or "Davivienda")
    )

    key_fragments = _dedup_preserve_order(rep_ke.get("key_facts", []) or []) or [
        "Sin fragmentos disponibles en la fuente."
    ]

    return {
        "title": title,
        "environment": {
            "product": rep_meta.get("product_specific")
            or rep_meta.get("product_category")
            or "Davivienda",
            "segment": "Banca Personal",
            "version": str(date.today().year),
        },
        "problem": problem,
        "cause": None,
        "resolution": _build_resolution(cluster_interactions),
        "evidence_pack": {
            "interaction_ids": [i["interaction_id"] for i in cluster_interactions],
            "key_fragments": key_fragments,
            "claim_evidence_map": _build_claim_map(cluster_interactions),
        },
        "metadata": {
            "status": "draft",
            "author": "baseline-heuristic",
            "confidence": "low",
            "created_at": date.today().isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_heuristic(
    interaction_ids: List[str], auto_approve: bool = True
) -> Dict[str, Any]:
    """Pipeline heurístico sin LLM. Retorna el mismo contrato que los frameworks."""
    started = time.time()
    traces: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    articles: List[Dict[str, Any]] = []
    article_interaction_map: Dict[str, List[str]] = {}

    # ---- carga ----
    interactions: List[Dict[str, Any]] = []
    for iid in interaction_ids:
        try:
            out = get_interaction(iid)
            interactions.append(out["interaction"])
        except Exception as e:  # noqa: BLE001
            errors.append(
                {
                    "phase": "ingest_batch",
                    "interaction_id": iid,
                    "error": str(e),
                    "ts": _now_iso(),
                }
            )
    traces.append(
        {
            "phase": "ingest_batch",
            "type": "phase_complete",
            "loaded": len(interactions),
            "requested": len(interaction_ids),
            "ts": _now_iso(),
        }
    )

    if not interactions:
        elapsed = round(time.time() - started, 3)
        return {
            "articles": [],
            "article_interaction_map": {},
            "traces": traces,
            "metrics": {
                "total_time_seconds": elapsed,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "total_tool_calls": 0,
                "cost_usd": 0.0,
                "revision_cycles": 0,
                "articles_generated": 0,
            },
            "errors": errors + [{"reason": "no_interactions_loaded", "ts": _now_iso()}],
            "aborted": True,
        }

    # ---- vectorización + clustering ----
    texts = [_interaction_text(i) for i in interactions]
    vectorizer = TfidfVectorizer(
        max_features=4096,
        ngram_range=(1, 2),
        lowercase=True,
        strip_accents="unicode",
    )
    matrix = vectorizer.fit_transform(texts)

    k = _pick_k(len(interactions))
    if k <= 1 or matrix.shape[0] <= 1:
        labels = np.zeros(len(interactions), dtype=int)
        centroids = matrix.mean(axis=0)
        n_clusters = 1
    else:
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = kmeans.fit_predict(matrix)
        centroids = kmeans.cluster_centers_
        n_clusters = k

    traces.append(
        {
            "phase": "cluster",
            "type": "phase_complete",
            "k": n_clusters,
            "labels": labels.tolist(),
            "ts": _now_iso(),
        }
    )

    # ---- construcción de artículos ----
    centroids_arr = np.asarray(centroids)
    if centroids_arr.ndim == 1:
        centroids_arr = centroids_arr.reshape(1, -1)

    for cluster_idx in range(n_clusters):
        member_indexes = np.where(labels == cluster_idx)[0]
        if len(member_indexes) == 0:
            continue
        cluster_members = [interactions[i] for i in member_indexes]

        # Centroide vs vectores de los miembros — el más cercano es el representante.
        member_vectors = matrix[member_indexes]
        sims = cosine_similarity(member_vectors, centroids_arr[cluster_idx].reshape(1, -1)).ravel()
        best_local = int(np.argmax(sims))
        representative = cluster_members[best_local]

        article = _build_article(cluster_members, representative)
        article_id = f"ART-{len(articles) + 1:03d}"
        unit_id = f"G-HEUR-{cluster_idx + 1:03d}"

        articles.append(
            {
                "article_id": article_id,
                "unit_id": unit_id,
                "topic": article["title"],
                "article": article,
            }
        )
        article_interaction_map[article_id] = [i["interaction_id"] for i in cluster_members]

        traces.append(
            {
                "phase": "build_article",
                "type": "article_finalized",
                "cluster_idx": cluster_idx,
                "article_id": article_id,
                "representative_id": representative["interaction_id"],
                "members": [i["interaction_id"] for i in cluster_members],
                "ts": _now_iso(),
            }
        )

    # ---- métricas ----
    elapsed = round(time.time() - started, 3)
    metrics = {
        "total_time_seconds": elapsed,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_tool_calls": 0,
        "cost_usd": 0.0,
        "revision_cycles": 0,
        "articles_generated": len(articles),
        # extra propio del baseline para análisis posterior
        "clusters_built": n_clusters,
    }

    return {
        "articles": articles,
        "article_interaction_map": article_interaction_map,
        "traces": traces,
        "metrics": metrics,
        "errors": errors,
        "aborted": False,
    }

"""Tool contract: 6 herramientas compartidas por los 3 frameworks de agentes.

Diseñadas como funciones Python puras con esquemas Pydantic para entrada/salida
y un TOOL_REGISTRY listo para function calling (Anthropic / OpenAI).
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator


# ---------------------------------------------------------------------------
# Configuración de rutas
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    env_dir = os.environ.get("CB_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return _PROJECT_ROOT / "data" / "processed"


def _interactions_path() -> Path:
    return _data_dir() / "interactions.jsonl"


# ---------------------------------------------------------------------------
# Constantes de validación
# ---------------------------------------------------------------------------

VALID_STATUS = ("draft", "review", "published")
VALID_CONFIDENCE = ("low", "medium", "high", "verified")
VALID_ARTICLE_TYPES = ("faq", "howto", "politica", "troubleshooting")

TITLE_MAX_LEN = 150
RESOLUTION_MIN_LEN = 50

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


# ---------------------------------------------------------------------------
# Detección de PII
# ---------------------------------------------------------------------------

_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_RE_CARD = re.compile(r"\b(?:\d[ \-]?){13,19}\b")
_RE_PHONE_CO = re.compile(r"(?<!\d)3\d{9}(?!\d)")
_RE_CEDULA = re.compile(r"(?<!\d)\d{8,12}(?!\d)")
_RE_INT_ID = re.compile(r"\bINT-\d{4}-\d{3}\b")


def _mask_digits(text: str) -> str:
    if len(text) <= 4:
        return "*" * len(text)
    return text[:2] + "*" * (len(text) - 4) + text[-2:]


def _mask_email(text: str) -> str:
    local, _, domain = text.partition("@")
    if not domain:
        return "***"
    head = local[:1] if local else ""
    return f"{head}***@{domain}"


def check_pii(text: str) -> Dict[str, Any]:
    """Detecta cédulas, emails, celulares colombianos y números de tarjeta.

    Excluye años (2024/2025) e IDs de interacción (INT-2024-XXX).
    Retorna findings con texto enmascarado y rango.
    """
    if not isinstance(text, str) or not text:
        return {"has_pii": False, "findings": []}

    # Posiciones a excluir: IDs INT-YYYY-NNN
    excluded_spans: List[Tuple[int, int]] = [m.span() for m in _RE_INT_ID.finditer(text)]

    def _is_excluded(span: Tuple[int, int]) -> bool:
        for s, e in excluded_spans:
            if span[0] >= s and span[1] <= e:
                return True
        return False

    findings: List[Dict[str, Any]] = []
    consumed: List[Tuple[int, int]] = []

    def _overlaps(span: Tuple[int, int]) -> bool:
        for s, e in consumed:
            if not (span[1] <= s or span[0] >= e):
                return True
        return False

    # 1. Emails
    for m in _RE_EMAIL.finditer(text):
        if _is_excluded(m.span()):
            continue
        findings.append(
            {
                "type": "email",
                "value_masked": _mask_email(m.group()),
                "span": [m.start(), m.end()],
            }
        )
        consumed.append(m.span())

    # 2. Tarjetas (mayor longitud primero — solo si contiene separadores o >= 13 digitos contiguos)
    for m in _RE_CARD.finditer(text):
        raw = m.group()
        digits_only = re.sub(r"\D", "", raw)
        if len(digits_only) < 13 or len(digits_only) > 19:
            continue
        if _is_excluded(m.span()) or _overlaps(m.span()):
            continue
        findings.append(
            {
                "type": "tarjeta",
                "value_masked": _mask_digits(digits_only),
                "span": [m.start(), m.end()],
            }
        )
        consumed.append(m.span())

    # 3. Celulares colombianos (10 dígitos comenzando en 3)
    for m in _RE_PHONE_CO.finditer(text):
        if _is_excluded(m.span()) or _overlaps(m.span()):
            continue
        findings.append(
            {
                "type": "celular",
                "value_masked": _mask_digits(m.group()),
                "span": [m.start(), m.end()],
            }
        )
        consumed.append(m.span())

    # 4. Cédulas (8-12 dígitos)
    for m in _RE_CEDULA.finditer(text):
        if _is_excluded(m.span()) or _overlaps(m.span()):
            continue
        digits = m.group()
        # Excluir años puros (2024, 2025) — solo cuando longitud es exactamente 4
        # (el regex ya exige >= 8 dígitos, así que sólo es defensa adicional)
        if len(digits) == 4 and digits in {"2024", "2025"}:
            continue
        findings.append(
            {
                "type": "cedula",
                "value_masked": _mask_digits(digits),
                "span": [m.start(), m.end()],
            }
        )
        consumed.append(m.span())

    findings.sort(key=lambda f: f["span"][0])
    return {"has_pii": len(findings) > 0, "findings": findings}


# ---------------------------------------------------------------------------
# InteractionStore: singleton con índice de embeddings
# ---------------------------------------------------------------------------


def _mask_name(name: Optional[str]) -> str:
    if not name:
        return "***"
    first = name.strip()[:1]
    return f"{first}***" if first else "***"


def _build_index_text(interaction: Dict[str, Any]) -> str:
    parts: List[str] = []
    meta = interaction.get("metadata", {}) or {}
    parts.append(meta.get("product_category", "") or "")
    parts.append(meta.get("product_specific", "") or "")
    parts.append(meta.get("query_type", "") or "")
    parts.append(meta.get("gap_topic", "") or "")
    ke = interaction.get("knowledge_extracted", {}) or {}
    parts.append(ke.get("main_topic", "") or "")
    for f in ke.get("key_facts", []) or []:
        parts.append(f)
    for t in interaction.get("turns", []) or []:
        msg = t.get("message", "")
        if msg:
            parts.append(msg)
    return " \n ".join(p for p in parts if p)


class InteractionStore:
    """Singleton que carga interacciones y mantiene el índice de embeddings."""

    _instance: Optional["InteractionStore"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._interactions: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._index_texts: List[str] = []
        self._embeddings = None  # numpy array, lazy
        self._model = None  # SentenceTransformer, lazy
        self._loaded_path: Optional[Path] = None

    @classmethod
    def instance(cls) -> "InteractionStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        cls._instance._ensure_loaded()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Resetea el singleton (útil en tests cuando CB_DATA_DIR cambia)."""
        with cls._lock:
            cls._instance = None

    def _ensure_loaded(self) -> None:
        path = _interactions_path()
        if self._loaded_path == path and self._interactions:
            return
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo de interacciones: {path}")
        interactions: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                interactions.append(json.loads(line))
        self._interactions = interactions
        self._by_id = {i["interaction_id"]: i for i in interactions}
        self._index_texts = [_build_index_text(i) for i in interactions]
        self._embeddings = None  # invalidar embeddings al recargar
        self._loaded_path = path

    def _embeddings_cache_path(self) -> Path:
        # Cache compartida en disco para que cada subproceso reutilice los
        # embeddings ya calculados (el singleton InteractionStore vive en
        # un único proceso; scripts/_common.py lanza cada lote en mp.spawn).
        import hashlib

        assert self._loaded_path is not None
        try:
            mtime = self._loaded_path.stat().st_mtime_ns
        except OSError:
            mtime = 0
        key = f"{self._loaded_path}|{mtime}|{EMBEDDING_MODEL_NAME}|{len(self._interactions)}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self._loaded_path.parent / f".embeddings_cache.{digest}.npy"

    def _ensure_embeddings(self):
        if self._embeddings is not None:
            return
        import numpy as np

        cache_path = self._embeddings_cache_path()
        if cache_path.exists():
            try:
                cached = np.load(cache_path)
                if cached.shape[0] == len(self._index_texts):
                    self._embeddings = cached
                    return
            except Exception:  # noqa: BLE001 — cache corrupta: recomputar
                pass

        self._ensure_model()
        self._embeddings = self._model.encode(
            self._index_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        try:
            # np.save añade ".npy" si la ruta no termina en .npy; usamos una
            # temp distinta para evitar `.npy.tmp.npy`.
            tmp_path = cache_path.with_name(cache_path.name + ".tmp")
            np.save(str(tmp_path), self._embeddings)  # np.save añade .npy
            actual_tmp = tmp_path.with_suffix(tmp_path.suffix + ".npy")
            os.replace(actual_tmp, cache_path)
        except Exception:  # noqa: BLE001 — el cache es best-effort
            pass

    def all(self) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return self._interactions

    def get(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_loaded()
        return self._by_id.get(interaction_id)

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # import diferido

        self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    def search(self, query: str, k: int) -> List[Tuple[Dict[str, Any], float]]:
        self._ensure_loaded()
        self._ensure_embeddings()
        # _ensure_embeddings puede haber cargado desde cache sin tocar el modelo;
        # para encodear la query siempre necesitamos el modelo.
        self._ensure_model()
        import numpy as np

        q_emb = self._model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        sims = self._embeddings @ q_emb
        k = max(1, min(k, len(self._interactions)))
        idx = np.argsort(-sims)[:k]
        return [(self._interactions[i], float(sims[i])) for i in idx]


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------


class SearchInteractionsInput(BaseModel):
    query: str = Field(..., min_length=1, description="Consulta semántica en español")
    k: int = Field(10, ge=1, le=100, description="Número máximo de resultados")


class SearchHit(BaseModel):
    interaction_id: str
    score: float
    product_category: Optional[str] = None
    query_type: Optional[str] = None
    severity: Optional[str] = None
    main_topic: Optional[str] = None
    snippet: Optional[str] = None


class SearchInteractionsOutput(BaseModel):
    query: str
    results: List[SearchHit]


class GetInteractionInput(BaseModel):
    interaction_id: str = Field(..., pattern=r"^INT-\d{4}-\d{3}$")


class GetInteractionOutput(BaseModel):
    interaction: Dict[str, Any]


class ExtractKnowledgeInput(BaseModel):
    interaction_ids: List[str] = Field(..., min_length=1)

    @field_validator("interaction_ids")
    @classmethod
    def _check_ids(cls, v: List[str]) -> List[str]:
        for i in v:
            if not re.match(r"^INT-\d{4}-\d{3}$", i):
                raise ValueError(f"interaction_id inválido: {i}")
        return v


class ExtractKnowledgeOutput(BaseModel):
    main_topic: str
    key_facts: List[str]
    article_type: str
    source_interactions: List[str]
    combined_client_questions: List[str]
    combined_resolution_steps: List[str]


class ArticleEnvironment(BaseModel):
    product: str = Field(..., min_length=1)
    segment: str = Field(..., min_length=1)
    version: Optional[str] = None


class EvidencePack(BaseModel):
    interaction_ids: List[str] = Field(..., min_length=1)
    key_fragments: List[str] = Field(..., min_length=1)
    claim_evidence_map: Dict[str, List[str]] = Field(..., min_length=1)


class ArticleMetadata(BaseModel):
    status: Literal["draft", "review", "published"]
    author: str = Field(..., min_length=1)
    confidence: Literal["low", "medium", "high", "verified"]
    created_at: str

    @field_validator("created_at")
    @classmethod
    def _check_date(cls, v: str) -> str:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                datetime.strptime(v, fmt)
                return v
            except ValueError:
                continue
        # fromisoformat acepta más variantes
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError as e:
            raise ValueError(f"created_at no es una fecha ISO válida: {v}") from e


class ArticleSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=TITLE_MAX_LEN)
    environment: ArticleEnvironment
    problem: str = Field(..., min_length=1)
    cause: Optional[str] = None
    resolution: Any  # Validado manualmente: str o List[str]
    evidence_pack: EvidencePack
    metadata: ArticleMetadata

    @field_validator("resolution")
    @classmethod
    def _check_resolution(cls, v: Any) -> Any:
        if isinstance(v, str):
            if len(v.strip()) < RESOLUTION_MIN_LEN:
                raise ValueError(
                    f"resolution debe tener al menos {RESOLUTION_MIN_LEN} caracteres"
                )
            return v
        if isinstance(v, list):
            if not all(isinstance(s, str) for s in v):
                raise ValueError("resolution debe ser str o List[str]")
            joined = " ".join(v).strip()
            if len(joined) < RESOLUTION_MIN_LEN:
                raise ValueError(
                    f"resolution debe tener al menos {RESOLUTION_MIN_LEN} caracteres en total"
                )
            return v
        raise ValueError("resolution debe ser str o List[str]")


class ValidateArticleInput(BaseModel):
    article_json: Dict[str, Any]


class ValidationIssue(BaseModel):
    field: str
    message: str


class ValidateArticleOutput(BaseModel):
    is_valid: bool
    errors: List[ValidationIssue]
    warnings: List[ValidationIssue]
    pii_findings: List[Dict[str, Any]]


class CheckPIIInput(BaseModel):
    text: str


class CheckPIIOutput(BaseModel):
    has_pii: bool
    findings: List[Dict[str, Any]]


class ListInteractionsFilters(BaseModel):
    product_category: Optional[str] = None
    query_type: Optional[str] = None
    severity: Optional[str] = None


class ListInteractionsInput(BaseModel):
    filters: Optional[ListInteractionsFilters] = None


class InteractionSummary(BaseModel):
    interaction_id: str
    product_category: Optional[str] = None
    query_type: Optional[str] = None
    severity: Optional[str] = None
    main_topic: Optional[str] = None


class ListInteractionsOutput(BaseModel):
    total: int
    interactions: List[InteractionSummary]


# ---------------------------------------------------------------------------
# Implementación de las herramientas
# ---------------------------------------------------------------------------


def _mask_interaction(interaction: Dict[str, Any]) -> Dict[str, Any]:
    masked = json.loads(json.dumps(interaction))  # deep copy
    profile = masked.get("customer_profile") or {}
    if "name" in profile:
        profile["name"] = _mask_name(profile.get("name"))
    masked["customer_profile"] = profile
    return masked


def _snippet(interaction: Dict[str, Any], max_len: int = 200) -> str:
    ke = interaction.get("knowledge_extracted") or {}
    text = ke.get("main_topic") or ""
    if not text:
        turns = interaction.get("turns") or []
        for t in turns:
            if t.get("role") == "cliente":
                text = t.get("message", "")
                break
    return text[:max_len]


def search_interactions(query: str, k: int = 10) -> Dict[str, Any]:
    """Búsqueda semántica multilingüe sobre las interacciones del corpus."""
    inp = SearchInteractionsInput(query=query, k=k)
    store = InteractionStore.instance()
    hits = store.search(inp.query, inp.k)
    results: List[SearchHit] = []
    for inter, score in hits:
        meta = inter.get("metadata", {}) or {}
        ke = inter.get("knowledge_extracted", {}) or {}
        results.append(
            SearchHit(
                interaction_id=inter["interaction_id"],
                score=round(score, 4),
                product_category=meta.get("product_category"),
                query_type=meta.get("query_type"),
                severity=meta.get("severity"),
                main_topic=ke.get("main_topic"),
                snippet=_snippet(inter),
            )
        )
    return SearchInteractionsOutput(query=inp.query, results=results).model_dump()


def get_interaction(interaction_id: str) -> Dict[str, Any]:
    """Retorna una interacción completa por ID, con el nombre del cliente enmascarado."""
    inp = GetInteractionInput(interaction_id=interaction_id)
    store = InteractionStore.instance()
    inter = store.get(inp.interaction_id)
    if inter is None:
        raise KeyError(f"No existe la interacción {inp.interaction_id}")
    return GetInteractionOutput(interaction=_mask_interaction(inter)).model_dump()


def extract_knowledge(interaction_ids: List[str]) -> Dict[str, Any]:
    """Extrae y combina los hechos documentables de las interacciones indicadas."""
    inp = ExtractKnowledgeInput(interaction_ids=interaction_ids)
    store = InteractionStore.instance()

    main_topics: List[str] = []
    key_facts: List[str] = []
    article_types: List[str] = []
    client_questions: List[str] = []
    resolution_steps: List[str] = []
    sources: List[str] = []
    missing: List[str] = []

    for iid in inp.interaction_ids:
        inter = store.get(iid)
        if inter is None:
            missing.append(iid)
            continue
        ke = inter.get("knowledge_extracted", {}) or {}
        if ke.get("main_topic"):
            main_topics.append(ke["main_topic"])
        for f in ke.get("key_facts", []) or []:
            if f not in key_facts:
                key_facts.append(f)
        if ke.get("article_type"):
            article_types.append(ke["article_type"])
        for turn in inter.get("turns", []) or []:
            msg = (turn.get("message") or "").strip()
            if not msg:
                continue
            if turn.get("role") == "cliente" and msg not in client_questions:
                client_questions.append(msg)
            elif turn.get("role") == "asesor" and msg not in resolution_steps:
                resolution_steps.append(msg)
        sources.append(iid)

    if missing:
        raise KeyError(f"Interacciones inexistentes: {missing}")

    if main_topics:
        topic_counts = Counter(main_topics)
        main_topic = topic_counts.most_common(1)[0][0]
    else:
        main_topic = ""

    if article_types:
        article_type = Counter(article_types).most_common(1)[0][0]
    else:
        article_type = "faq"

    return ExtractKnowledgeOutput(
        main_topic=main_topic,
        key_facts=key_facts,
        article_type=article_type,
        source_interactions=sources,
        combined_client_questions=client_questions,
        combined_resolution_steps=resolution_steps,
    ).model_dump()


def _collect_text_fields(article: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Devuelve pares (campo, texto) para chequear PII."""
    out: List[Tuple[str, str]] = []
    out.append(("title", article.get("title", "") or ""))
    out.append(("problem", article.get("problem", "") or ""))
    if article.get("cause"):
        out.append(("cause", str(article["cause"])))
    res = article.get("resolution")
    if isinstance(res, str):
        out.append(("resolution", res))
    elif isinstance(res, list):
        for i, step in enumerate(res):
            if isinstance(step, str):
                out.append((f"resolution[{i}]", step))
    ev = article.get("evidence_pack") or {}
    for i, frag in enumerate(ev.get("key_fragments", []) or []):
        if isinstance(frag, str):
            out.append((f"evidence_pack.key_fragments[{i}]", frag))
    return out


def validate_article(article_json: Dict[str, Any]) -> Dict[str, Any]:
    """Valida un artículo contra la plantilla KCS.

    Verifica estructura, longitudes, valores enumerados y ausencia de PII en
    los campos de texto. Retorna is_valid, errors, warnings y pii_findings.
    """
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []
    pii_findings: List[Dict[str, Any]] = []

    if not isinstance(article_json, dict):
        return ValidateArticleOutput(
            is_valid=False,
            errors=[ValidationIssue(field="<root>", message="article_json debe ser un objeto JSON")],
            warnings=[],
            pii_findings=[],
        ).model_dump()

    # Validación estructural con Pydantic
    try:
        ArticleSchema.model_validate(article_json)
    except ValidationError as ve:
        for err in ve.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(ValidationIssue(field=loc or "<root>", message=err["msg"]))

    # PII en cada campo de texto
    for field, text in _collect_text_fields(article_json):
        res = check_pii(text)
        for finding in res["findings"]:
            entry = dict(finding)
            entry["field"] = field
            pii_findings.append(entry)
            errors.append(
                ValidationIssue(
                    field=field,
                    message=f"PII detectada ({finding['type']}): {finding['value_masked']}",
                )
            )

    # Warnings adicionales
    title = (article_json.get("title") or "").strip()
    if title and len(title) < 10:
        warnings.append(
            ValidationIssue(field="title", message="El título parece muy corto (<10 chars)")
        )

    ev = article_json.get("evidence_pack") or {}
    iids = ev.get("interaction_ids") or []
    for iid in iids:
        if isinstance(iid, str) and not re.match(r"^INT-\d{4}-\d{3}$", iid):
            warnings.append(
                ValidationIssue(
                    field="evidence_pack.interaction_ids",
                    message=f"ID con formato inesperado: {iid}",
                )
            )

    return ValidateArticleOutput(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        pii_findings=pii_findings,
    ).model_dump()


def list_interactions(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Inventario de interacciones con filtros opcionales."""
    parsed = ListInteractionsInput(
        filters=ListInteractionsFilters(**(filters or {})) if filters else None
    )
    store = InteractionStore.instance()
    out: List[InteractionSummary] = []
    f = parsed.filters
    for inter in store.all():
        meta = inter.get("metadata", {}) or {}
        if f:
            if f.product_category and meta.get("product_category") != f.product_category:
                continue
            if f.query_type and meta.get("query_type") != f.query_type:
                continue
            if f.severity and meta.get("severity") != f.severity:
                continue
        ke = inter.get("knowledge_extracted", {}) or {}
        out.append(
            InteractionSummary(
                interaction_id=inter["interaction_id"],
                product_category=meta.get("product_category"),
                query_type=meta.get("query_type"),
                severity=meta.get("severity"),
                main_topic=ke.get("main_topic"),
            )
        )
    return ListInteractionsOutput(total=len(out), interactions=out).model_dump()


# ---------------------------------------------------------------------------
# TOOL_REGISTRY — JSON Schemas para function calling
# ---------------------------------------------------------------------------


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "search_interactions": {
        "function": search_interactions,
        "description": (
            "Búsqueda semántica multilingüe sobre el corpus de interacciones de "
            "WhatsApp. Retorna los k resultados más relevantes con su score de "
            "similitud y metadatos clave."
        ),
        "input_schema": SearchInteractionsInput,
        "output_schema": SearchInteractionsOutput,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta en lenguaje natural (español).",
                },
                "k": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "Número máximo de resultados a retornar.",
                },
            },
            "required": ["query"],
        },
    },
    "get_interaction": {
        "function": get_interaction,
        "description": (
            "Devuelve la interacción completa por ID, con el nombre del cliente "
            "enmascarado (primera letra + ***)."
        ),
        "input_schema": GetInteractionInput,
        "output_schema": GetInteractionOutput,
        "parameters": {
            "type": "object",
            "properties": {
                "interaction_id": {
                    "type": "string",
                    "pattern": r"^INT-\d{4}-\d{3}$",
                    "description": "Identificador con formato INT-YYYY-NNN.",
                },
            },
            "required": ["interaction_id"],
        },
    },
    "extract_knowledge": {
        "function": extract_knowledge,
        "description": (
            "Extrae y combina los hechos documentables (knowledge_extracted) de "
            "una o más interacciones para alimentar la redacción del artículo."
        ),
        "input_schema": ExtractKnowledgeInput,
        "output_schema": ExtractKnowledgeOutput,
        "parameters": {
            "type": "object",
            "properties": {
                "interaction_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": r"^INT-\d{4}-\d{3}$"},
                    "minItems": 1,
                    "description": "Lista de IDs de interacción a combinar.",
                }
            },
            "required": ["interaction_ids"],
        },
    },
    "validate_article": {
        "function": validate_article,
        "description": (
            "Valida un artículo contra la plantilla KCS: estructura, longitudes, "
            "valores enumerados y ausencia de PII."
        ),
        "input_schema": ValidateArticleInput,
        "output_schema": ValidateArticleOutput,
        "parameters": {
            "type": "object",
            "properties": {
                "article_json": {
                    "type": "object",
                    "description": "Artículo JSON a validar (plantilla KCS).",
                }
            },
            "required": ["article_json"],
        },
    },
    "check_pii": {
        "function": check_pii,
        "description": (
            "Detecta cédulas, emails, celulares colombianos y números de tarjeta "
            "en un fragmento de texto. Retorna findings enmascarados."
        ),
        "input_schema": CheckPIIInput,
        "output_schema": CheckPIIOutput,
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Texto a inspeccionar.",
                }
            },
            "required": ["text"],
        },
    },
    "list_interactions": {
        "function": list_interactions,
        "description": (
            "Lista resumida de interacciones con filtros opcionales por "
            "product_category, query_type y severity."
        ),
        "input_schema": ListInteractionsInput,
        "output_schema": ListInteractionsOutput,
        "parameters": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "product_category": {"type": "string"},
                        "query_type": {"type": "string"},
                        "severity": {"type": "string"},
                    },
                    "additionalProperties": False,
                }
            },
        },
    },
}


def get_tool(name: str) -> Callable[..., Dict[str, Any]]:
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Tool desconocida: {name}")
    return TOOL_REGISTRY[name]["function"]


__all__ = [
    "EMBEDDING_MODEL_NAME",
    "InteractionStore",
    "TOOL_REGISTRY",
    "check_pii",
    "extract_knowledge",
    "get_interaction",
    "get_tool",
    "list_interactions",
    "search_interactions",
    "validate_article",
    # schemas
    "ArticleEnvironment",
    "ArticleMetadata",
    "ArticleSchema",
    "CheckPIIInput",
    "CheckPIIOutput",
    "EvidencePack",
    "ExtractKnowledgeInput",
    "ExtractKnowledgeOutput",
    "GetInteractionInput",
    "GetInteractionOutput",
    "InteractionSummary",
    "ListInteractionsFilters",
    "ListInteractionsInput",
    "ListInteractionsOutput",
    "SearchHit",
    "SearchInteractionsInput",
    "SearchInteractionsOutput",
    "ValidateArticleInput",
    "ValidateArticleOutput",
    "ValidationIssue",
]

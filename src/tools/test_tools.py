"""Tests para el tool contract.

Cubre happy paths, errores y edge cases de las 6 herramientas.
Las pruebas que requieren embeddings descargarán el modelo si no está cacheado.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Asegura que el proyecto sea importable como paquete.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.tools.tool_contract import (  # noqa: E402
    TOOL_REGISTRY,
    InteractionStore,
    check_pii,
    extract_knowledge,
    get_interaction,
    get_tool,
    list_interactions,
    search_interactions,
    validate_article,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_store_loaded():
    # Garantiza que el singleton apunta al dataset por defecto.
    InteractionStore.reset()
    yield
    InteractionStore.reset()


def _valid_article():
    return {
        "title": "Cómo transferir a DaviPlata usando Bre-b",
        "environment": {
            "product": "App Davivienda",
            "segment": "Banca Personal",
            "version": "2024",
        },
        "problem": "El cliente no sabe cómo enviar dinero a DaviPlata usando Bre-b.",
        "cause": None,
        "resolution": [
            "1. Abrir la App Davivienda e iniciar sesión.",
            "2. Ir a Transferencias y luego a Bre-b.",
            "3. Seleccionar DaviPlata como destino, ingresar monto y confirmar.",
        ],
        "evidence_pack": {
            "interaction_ids": ["INT-2024-088"],
            "key_fragments": [
                "Para transferir a DaviPlata por Bre-b, debe activar la opción en la App."
            ],
            "claim_evidence_map": {
                "Se requiere Bre-b activado en la App": ["INT-2024-088"],
            },
        },
        "metadata": {
            "status": "draft",
            "author": "agent-langgraph",
            "confidence": "high",
            "created_at": "2024-02-15",
        },
    }


# ---------------------------------------------------------------------------
# check_pii
# ---------------------------------------------------------------------------


def test_check_pii_detects_email():
    res = check_pii("Mi correo es juan.perez@gmail.com, contáctenme")
    assert res["has_pii"] is True
    types = {f["type"] for f in res["findings"]}
    assert "email" in types
    email_finding = next(f for f in res["findings"] if f["type"] == "email")
    assert "@gmail.com" in email_finding["value_masked"]
    assert "juan.perez" not in email_finding["value_masked"]


def test_check_pii_detects_cedula():
    res = check_pii("Mi cédula es 1023456789 para validar la cuenta.")
    assert res["has_pii"] is True
    assert any(f["type"] == "celular" or f["type"] == "cedula" for f in res["findings"])


def test_check_pii_detects_celular_colombiano():
    res = check_pii("Llámeme al 3001234567 cuando pueda.")
    assert res["has_pii"] is True
    cel = [f for f in res["findings"] if f["type"] == "celular"]
    assert len(cel) == 1
    assert "3001234567" not in cel[0]["value_masked"]


def test_check_pii_detects_tarjeta():
    res = check_pii("Mi tarjeta es 4111 1111 1111 1111, válida hasta 2027.")
    assert res["has_pii"] is True
    assert any(f["type"] == "tarjeta" for f in res["findings"])


def test_check_pii_excluye_anios_e_int_ids():
    res = check_pii("En 2024 reportamos INT-2024-088 sin novedades en 2025.")
    assert res["has_pii"] is False
    assert res["findings"] == []


def test_check_pii_texto_limpio():
    res = check_pii("La App Davivienda permite consultar el saldo de la cuenta.")
    assert res["has_pii"] is False


def test_check_pii_texto_vacio_o_no_string():
    assert check_pii("") == {"has_pii": False, "findings": []}
    assert check_pii(None)["has_pii"] is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# get_interaction
# ---------------------------------------------------------------------------


def test_get_interaction_happy_path():
    out = get_interaction("INT-2024-088")
    inter = out["interaction"]
    assert inter["interaction_id"] == "INT-2024-088"
    assert "turns" in inter
    assert isinstance(inter["turns"], list) and len(inter["turns"]) > 0


def test_get_interaction_enmascara_nombre():
    out = get_interaction("INT-2024-088")
    name = out["interaction"]["customer_profile"]["name"]
    assert name.endswith("***")
    assert len(name) <= 4  # primera letra + ***
    assert "Luis" not in name


def test_get_interaction_no_existe():
    with pytest.raises(KeyError):
        get_interaction("INT-2024-999")


def test_get_interaction_id_invalido():
    with pytest.raises(ValidationError):
        get_interaction("foo-bar")


# ---------------------------------------------------------------------------
# list_interactions
# ---------------------------------------------------------------------------


def test_list_interactions_sin_filtros():
    out = list_interactions()
    assert out["total"] == 183
    assert len(out["interactions"]) == 183


def test_list_interactions_filtra_por_product_category():
    out = list_interactions({"product_category": "transferencias"})
    assert out["total"] > 0
    assert all(
        i["product_category"] == "transferencias" for i in out["interactions"]
    )


def test_list_interactions_filtra_por_query_type_y_severity():
    out = list_interactions({"query_type": "faq", "severity": "informativa"})
    for i in out["interactions"]:
        assert i["query_type"] == "faq"
        assert i["severity"] == "informativa"


def test_list_interactions_filtro_sin_coincidencias():
    out = list_interactions({"product_category": "inexistente"})
    assert out["total"] == 0
    assert out["interactions"] == []


# ---------------------------------------------------------------------------
# extract_knowledge
# ---------------------------------------------------------------------------


def test_extract_knowledge_una_interaccion():
    out = extract_knowledge(["INT-2024-088"])
    assert out["source_interactions"] == ["INT-2024-088"]
    assert out["main_topic"]  # no vacío
    assert out["article_type"] in {"faq", "howto", "politica", "troubleshooting"}
    assert len(out["key_facts"]) >= 1
    assert len(out["combined_client_questions"]) >= 1
    assert len(out["combined_resolution_steps"]) >= 1


def test_extract_knowledge_varias_interacciones():
    ids = ["INT-2024-001", "INT-2024-002", "INT-2024-003"]
    out = extract_knowledge(ids)
    assert out["source_interactions"] == ids
    # Sin duplicados en key_facts
    assert len(out["key_facts"]) == len(set(out["key_facts"]))


def test_extract_knowledge_id_inexistente():
    with pytest.raises(KeyError):
        extract_knowledge(["INT-2024-001", "INT-2024-999"])


def test_extract_knowledge_lista_vacia():
    with pytest.raises(ValidationError):
        extract_knowledge([])


# ---------------------------------------------------------------------------
# validate_article
# ---------------------------------------------------------------------------


def test_validate_article_valido():
    out = validate_article(_valid_article())
    assert out["is_valid"] is True
    assert out["errors"] == []
    assert out["pii_findings"] == []


def test_validate_article_titulo_demasiado_largo():
    art = _valid_article()
    art["title"] = "T" * 151
    out = validate_article(art)
    assert out["is_valid"] is False
    assert any("title" in e["field"] for e in out["errors"])


def test_validate_article_resolucion_corta():
    art = _valid_article()
    art["resolution"] = "Muy corto"
    out = validate_article(art)
    assert out["is_valid"] is False
    assert any("resolution" in e["field"] for e in out["errors"])


def test_validate_article_status_invalido():
    art = _valid_article()
    art["metadata"]["status"] = "approved"
    out = validate_article(art)
    assert out["is_valid"] is False
    assert any("metadata.status" in e["field"] for e in out["errors"])


def test_validate_article_pii_en_texto():
    art = _valid_article()
    art["problem"] = "El cliente Juan llamó al 3001234567 reportando un fallo."
    out = validate_article(art)
    assert out["is_valid"] is False
    assert len(out["pii_findings"]) >= 1
    assert any(f["type"] == "celular" for f in out["pii_findings"])


def test_validate_article_evidence_pack_obligatorio():
    art = _valid_article()
    del art["evidence_pack"]
    out = validate_article(art)
    assert out["is_valid"] is False
    assert any("evidence_pack" in e["field"] for e in out["errors"])


def test_validate_article_no_dict():
    out = validate_article("no soy un dict")  # type: ignore[arg-type]
    assert out["is_valid"] is False


# ---------------------------------------------------------------------------
# search_interactions (carga el modelo de embeddings — primer run descarga)
# ---------------------------------------------------------------------------


def test_search_interactions_happy_path():
    out = search_interactions("transferir dinero a DaviPlata por Bre-b", k=5)
    assert out["query"]
    assert 1 <= len(out["results"]) <= 5
    # Scores ordenados de mayor a menor
    scores = [r["score"] for r in out["results"]]
    assert scores == sorted(scores, reverse=True)
    # El top-1 debe tener id válido
    assert out["results"][0]["interaction_id"].startswith("INT-2024-")


def test_search_interactions_k_respetado():
    out = search_interactions("tarjeta de crédito bloqueada", k=3)
    assert len(out["results"]) == 3


def test_search_interactions_query_vacio():
    with pytest.raises(ValidationError):
        search_interactions("", k=5)


# ---------------------------------------------------------------------------
# TOOL_REGISTRY
# ---------------------------------------------------------------------------


def test_tool_registry_contiene_las_6_tools():
    expected = {
        "search_interactions",
        "get_interaction",
        "extract_knowledge",
        "validate_article",
        "check_pii",
        "list_interactions",
    }
    assert set(TOOL_REGISTRY.keys()) == expected
    for name, entry in TOOL_REGISTRY.items():
        assert callable(entry["function"])
        assert entry["description"]
        assert entry["parameters"]["type"] == "object"


def test_get_tool_devuelve_funcion():
    fn = get_tool("check_pii")
    assert callable(fn)
    with pytest.raises(KeyError):
        get_tool("does_not_exist")


# ---------------------------------------------------------------------------
# CB_DATA_DIR override
# ---------------------------------------------------------------------------


def test_cb_data_dir_override(tmp_path, monkeypatch):
    fake = tmp_path / "interactions.jsonl"
    fake.write_text(
        '{"interaction_id":"INT-2099-001","metadata":{"product_category":"test",'
        '"query_type":"faq","severity":"informativa"},'
        '"customer_profile":{"name":"Pepe"},'
        '"turns":[{"turn_number":1,"role":"cliente","message":"hola"}],'
        '"knowledge_extracted":{"main_topic":"Saludo","key_facts":["holaa"],"article_type":"faq"}}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CB_DATA_DIR", str(tmp_path))
    InteractionStore.reset()
    out = list_interactions()
    assert out["total"] == 1
    assert out["interactions"][0]["interaction_id"] == "INT-2099-001"
    # nombre enmascarado al hacer get
    got = get_interaction("INT-2099-001")
    assert got["interaction"]["customer_profile"]["name"] == "P***"

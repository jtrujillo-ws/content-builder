#!/usr/bin/env python
"""Ensambla docs/anexos_trabajo_grado.md a partir de las fuentes del repo.

Las secciones "copia literal" (prompts, budget.yaml, tablas, diagramas) se leen
de sus archivos para garantizar fidelidad; el resto (plantilla KCS, rúbrica,
tool contract, artículos, cronología, repositorio) se define aquí.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_human_eval import RUBRICA, SCORE_DIMS  # noqa: E402

OUT = ROOT / "docs" / "anexos_trabajo_grado.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").rstrip() + "\n"


def demote_h1(md: str, frm="# ", to="### ") -> str:
    # demota solo la primera línea de encabezado H1 (las tablas no tienen fences)
    return md.replace(frm, to, 1) if md.startswith(frm) else md


# ---------------------------------------------------------------------------
# Anexo A — Plantilla KCS
# ---------------------------------------------------------------------------
ANEXO_A = """## Anexo A — Plantilla KCS

La plantilla de artículo (Knowledge-Centered Service) no se define en un YAML
independiente: su contrato canónico es el `output_schema` del prompt del generador
(`configs/prompts/v1/system_generator.yaml`) y lo hace cumplir la herramienta
`validate_article`. Todo artículo debe tener los siete campos obligatorios.

| Campo | Tipo / regla |
|---|---|
| `title` | string, ≤ 150 caracteres, descriptivo (pregunta "¿Cómo…?" o tema) |
| `environment` | objeto: `product` (nombre real de Davivienda), `segment` ("Banca Personal"), `version` |
| `problem` | string, ≥ 1 carácter; el escenario/duda del cliente |
| `cause` | string \\| null. Troubleshooting → causa raíz con respaldo evidencial. Howto/faq → literal "No aplica — artículo informativo/procedimental" |
| `resolution` | lista de pasos numerados ("1. …", "2. …") o string ≥ 50 caracteres |
| `evidence_pack` | objeto: `interaction_ids` (≥ 1), `key_fragments` (≥ 1), `claim_evidence_map` (afirmación → [interaction_ids]) |
| `metadata` | objeto: `status` (draft\\|in_review\\|approved\\|rejected), `author`, `confidence` (low\\|medium\\|high\\|verified), `created_at` (YYYY-MM-DD) |

Esqueleto JSON:

```json
{
  "title": "≤ 150 caracteres",
  "environment": {"product": "...", "segment": "Banca Personal", "version": "2024"},
  "problem": "...",
  "cause": null,
  "resolution": ["1. ...", "2. ...", "..."],
  "evidence_pack": {
    "interaction_ids": ["INT-2024-010"],
    "key_fragments": ["fragmento literal o casi literal", "..."],
    "claim_evidence_map": {"afirmación verificable": ["INT-2024-010"]}
  },
  "metadata": {"status": "draft", "author": "agent-<framework>", "confidence": "medium", "created_at": "YYYY-MM-DD"}
}
```
"""


# ---------------------------------------------------------------------------
# Anexo B — Rúbrica de evaluación
# ---------------------------------------------------------------------------
def build_anexo_b() -> str:
    out = ["## Anexo B — Rúbrica de evaluación humana\n",
           "Cinco dimensiones en escala 1 (peor) a 5 (mejor). Definiciones de nivel "
           "y ejemplos ancla usados en la evaluación ciega "
           "(`scripts/build_human_eval.py`).\n"]
    for dim in SCORE_DIMS:
        r = RUBRICA[dim]
        out.append(f"### {dim.capitalize()}\n")
        out.append(f"_{r['_def']}_\n")
        out.append("| Nivel | Descripción |")
        out.append("|---|---|")
        for lvl in ["1", "2", "3", "4", "5"]:
            out.append(f"| {lvl} | {r[lvl]} |")
        out.append(f"\n**Ejemplos ancla:** {r['_ancla']}\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Anexo D — Tool Contract
# ---------------------------------------------------------------------------
ANEXO_D = """## Anexo D — Tool Contract

Seis herramientas compartidas (`TOOL_REGISTRY` en `src/tools/tool_contract.py`),
expuestas como funciones puras con esquema JSON para function calling. Los tres
frameworks usan exactamente el mismo contrato; el baseline de prompt único no usa
herramientas.

| Herramienta | Descripción | Entrada | Salida |
|---|---|---|---|
| `search_interactions` | Búsqueda semántica multilingüe sobre el corpus; retorna los k más relevantes con score y metadatos. | `query` (string, requerido), `k` (int 1–100, default 10) | lista de resultados {interaction_id, score, metadatos} |
| `get_interaction` | Devuelve la interacción completa por ID, con el nombre del cliente enmascarado. | `interaction_id` (string, patrón `INT-YYYY-NNN`) | `{interaction: {...}}` con `customer_profile.name` enmascarado |
| `extract_knowledge` | Extrae y combina los hechos documentables de una o más interacciones. | `interaction_ids` (array de IDs, ≥ 1) | `{main_topic, key_facts, combined_client_questions, combined_resolution_steps}` |
| `validate_article` | Valida un artículo contra la plantilla KCS: estructura, longitudes, enums y ausencia de PII. | `article_json` (objeto KCS) | `{is_valid, errors[], warnings[], pii_findings[]}` |
| `check_pii` | Detecta cédulas, emails, celulares colombianos y números de tarjeta. | `text` (string) | `{has_pii, findings: [{type, value_masked, span}]}` |
| `list_interactions` | Lista resumida con filtros opcionales por categoría, tipo y severidad. | `filters` (objeto opcional: product_category, query_type, severity) | `{interactions: [...resúmenes], count}` |
"""


# ---------------------------------------------------------------------------
# Anexo G — Tablas de resultados (Friedman + hipótesis desde el JSON)
# ---------------------------------------------------------------------------
FW_SHORT = {"langgraph": "LangGraph", "crewai": "CrewAI",
            "openai_agents": "OpenAI", "baseline_prompt": "Baseline"}


def build_anexo_g() -> str:
    st = json.loads((ROOT / "eval/analysis/statistical_tests.json").read_text(encoding="utf-8"))
    main_tbl = demote_h1(read("eval/results/main_table.md"))
    res_tbl = demote_h1(read("eval/results/reserve_table.md"))

    out = ["## Anexo G — Tablas completas de resultados\n"]
    out.append("### G.1 Estudio principal (split evaluación)\n")
    out.append(main_tbl)
    out.append("\n### G.2 Validación de estabilidad (split reserva)\n")
    out.append(res_tbl)

    out.append("\n### G.3 Pruebas de Friedman por dimensión humana\n")
    out.append("| Dimensión | χ² | p | Significativo | W de Kendall |")
    out.append("|---|---|---|---|---|")
    for d, v in st["friedman_by_dimension"].items():
        out.append(f"| {d} | {v['friedman_chi2']:.4f} | {v['p_value']:.4f} | "
                   f"{'Sí' if v['significant'] else 'No'} | {v['kendall_w']:.4f} |")

    out.append("\n### G.4 Contraste de hipótesis\n")
    h = st["hypotheses"]
    out.append("| Hipótesis | Veredicto | Dato decisivo |")
    out.append("|---|---|---|")
    fr = h["H1"]["failure_rates_pct"]
    out.append(f"| H1 | {h['H1']['verdict']} | Fallos: LangGraph {fr['langgraph']}%, "
               f"CrewAI {fr['crewai']}%, OpenAI {fr['openai_agents']}% |")
    cl = h["H2"]["by_dimension"]["claridad"]; ac = h["H2"]["by_dimension"]["aplicabilidad"]
    out.append(f"| H2 | {h['H2']['verdict']} | CrewAI mayor media; Friedman 3-fw n.s. "
               f"(claridad p={cl['p_value']:.4f}, aplicabilidad p={ac['p_value']:.4f}) |")
    cv = h["H3"]["inter_run_cv"]
    out.append(f"| H3 | {h['H3']['verdict']} | CV medio inter-run: CrewAI "
               f"{cv['crewai']['mean_cv_pct']}%, OpenAI {cv['openai_agents']['mean_cv_pct']}%, "
               f"LangGraph {cv['langgraph']['mean_cv_pct']}% |")
    out.append(f"| H4 | {h['H4']['verdict']} | Ablación `no_evidence` no ejecutada |")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Anexo H — Artículos ejemplo (INT-2024-010)
# ---------------------------------------------------------------------------
def build_anexo_h() -> str:
    out = ["## Anexo H — Artículos ejemplo (INT-2024-010)\n",
           "Artículo generado por cada generador para la misma interacción "
           "(`INT-2024-010`, certificación de Cuenta de Ahorro Nómina), del run 1 del "
           "estudio principal. Los cuatro cubren la interacción con un artículo "
           "individual (ART-001).\n"]
    for fw in ["langgraph", "crewai", "openai_agents", "baseline_prompt"]:
        rd = ROOT / "runs/experiment" / fw / "run_1"
        amap = json.loads((rd / "article_interaction_map.json").read_text(encoding="utf-8"))
        aid = next((k for k, v in amap.items()
                    if "INT-2024-010" in ([v] if isinstance(v, str) else v)), None)
        art = None
        for line in (rd / "generated_articles.jsonl").read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if d.get("article_id") == aid:
                art = d["article"]; break
        out.append(f"### {FW_SHORT[fw]}\n")
        out.append(f"**Título:** {art.get('title','')}\n")
        out.append(f"**Problema:** {art.get('problem','')}\n")
        out.append(f"**Causa:** {art.get('cause')}\n")
        res = art.get("resolution")
        out.append("**Resolución:**\n")
        if isinstance(res, list):
            for s in res:
                out.append(f"- {s}")
        else:
            out.append(str(res))
        md = art.get("metadata", {}) or {}
        out.append(f"\n**Confianza (metadata):** {md.get('confidence')}\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Anexo J — Repositorio
# ---------------------------------------------------------------------------
ANEXO_J = """## Anexo J — Repositorio

Código, datos procesados, resultados y documentación:
**https://github.com/jtrujillo-ws/content-builder**

Ejecución mínima (Python 3.11):

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Verificar dataset y correr un framework sobre el subset de 50 (3 runs)
.venv/bin/python scripts/verify_data.py --strict
.venv/bin/python scripts/run_experiment.py --framework crewai --runs 3 \\
    --batch-size 1 --eval-subset data/splits/eval_subset_50.yaml --max-total-cost 200

# Métricas y análisis
.venv/bin/python scripts/compute_metrics.py --runs-dir runs/experiment \\
    --out eval/results/main_metrics.json
.venv/bin/python scripts/analyze_human_eval.py
```

El detalle del pipeline completo está en `README.md` y `docs/proceso_experimental.md`.
"""


def main() -> int:
    prompts = read("docs/prompts_del_experimento.md")
    budget = read("configs/experiments/budget.yaml")
    diagrams = read("docs/anexos/diagramas_orquestacion.md")

    parts = [
        "# Anexos del trabajo de grado\n",
        "Comparación empírica de frameworks de agentes para generación de KB "
        "(Davivienda). Documento consolidado de anexos A–J. Las secciones de copia "
        "literal se reproducen de sus archivos fuente en el repositorio.\n",
        "---\n",
        ANEXO_A, "\n---\n",
        build_anexo_b(), "\n---\n",
        "## Anexo C — Prompts del experimento\n",
        "> Reproducción literal de `docs/prompts_del_experimento.md`.\n",
        prompts, "\n---\n",
        ANEXO_D, "\n---\n",
        "## Anexo E — Configuración experimental\n",
        "Contenido de `configs/experiments/budget.yaml` (modelo de control, "
        "presupuesto por lote, repeticiones, pricing):\n",
        "```yaml\n" + budget.rstrip() + "\n```\n", "\n---\n",
        "## Anexo F — Diagramas de orquestación\n",
        "> Reproducción literal de `docs/anexos/diagramas_orquestacion.md`.\n",
        diagrams, "\n---\n",
        build_anexo_g(), "\n---\n",
        build_anexo_h(), "\n---\n",
        ANEXO_J,
    ]
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"✅ escrito {OUT} ({len(OUT.read_text(encoding='utf-8').splitlines())} líneas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

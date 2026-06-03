# Content Builder

Comparación empírica de tres frameworks de agentes autónomos en Python
(**LangGraph**, **CrewAI**, **OpenAI Agents SDK**) para la generación de
artículos de base de conocimiento (KB) a partir de interacciones de servicio al
cliente. Caso de estudio: Davivienda Colombia, interacciones de WhatsApp Business.

La **única variable independiente** es el framework de orquestación; el modelo
LLM (`claude-sonnet-4-6`), el presupuesto, los prompts y los datos son idénticos
para los tres. Se incluyen además dos *baselines* de control (heurístico y de un
solo prompt).

> Diseño experimental (Opción B): los frameworks reciben interacciones como
> input y generan artículos KB desde cero. No hay KB preexistente que consultar;
> cada framework decide autónomamente si agrupa interacciones similares.

Para el detalle del proceso y los problemas resueltos, ver
[`docs/proceso_experimental.md`](docs/proceso_experimental.md).

---

## Estructura del repositorio

```
configs/          parámetros del experimento (budget.yaml), políticas y prompts
data/
  processed/      interactions.jsonl (183), kb_articles.jsonl (118, ground truth)
  splits/         splits.yaml (calibración 37 / evaluación 109 / reserva 37)
                  eval_subset_50.yaml (subset estratificado del estudio principal)
src/
  tools/          6 herramientas compartidas (search, get, extract, validate, pii, list)
  baselines/      baseline_heuristic, baseline_prompt
  frameworks/     langgraph/, crewai/, openai_agents/  (un runner por framework)
scripts/          orquestación (ver pipeline abajo)
eval/
  rubrics/        plantillas de evaluación humana (Excel)
  results/        métricas automáticas (gitignored salvo lo versionado explícito)
  analysis/       análisis estadístico combinado + figuras
runs/             artefactos de cada corrida (gitignored)
docs/             documentación del proceso
```

---

## Requisitos e instalación

- **Python 3.11** (CrewAI moderno requiere ≥ 3.10).
- Clave de API de Anthropic.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Crea un archivo `.env` en la raíz con tu clave (no se versiona):

```
ANTHROPIC_API_KEY=sk-ant-...
```

> Nota: `torch` (dependencia de los embeddings) es específico de plataforma; en
> otra máquina/CUDA puede requerir el índice de wheels de
> [PyTorch](https://pytorch.org).

---

## Pipeline de reproducción

Todos los comandos asumen el intérprete del venv (`.venv/bin/python`).

### 0. Verificar el dataset

```bash
.venv/bin/python scripts/verify_data.py --strict
```

### 1. (Opcional) Calibración sobre el split de calibración (37 IDs)

```bash
.venv/bin/python scripts/run_calibration.py --framework langgraph
```

### 2. Estudio principal — split de evaluación (subset de 50, 3 runs)

Ejecutar para cada framework y baseline. **Siempre pasar `--max-total-cost 200`**
(el default $20 trunca el run antes de completar las 50 interacciones):

```bash
for FW in langgraph crewai openai_agents baseline_prompt baseline_heuristic; do
  .venv/bin/python scripts/run_experiment.py \
    --framework "$FW" \
    --runs 3 \
    --batch-size 1 \
    --eval-subset data/splits/eval_subset_50.yaml \
    --max-total-cost 200
done
```

Salida: `runs/experiment/<framework>/run_<n>/` + `experiment_summary.json`.

### 3. Validación de estabilidad — split de reserva (37 IDs, 1 run)

```bash
for FW in langgraph crewai openai_agents; do
  .venv/bin/python scripts/run_experiment.py \
    --framework "$FW" \
    --runs 1 \
    --batch-size 1 \
    --split reserve \
    --out-subdir experiment_reserve \
    --max-total-cost 200
done
```

Salida: `runs/experiment_reserve/<framework>/`.

### 4. Métricas automáticas + resumen ejecutivo

```bash
.venv/bin/python scripts/compute_metrics.py \
  --runs-dir runs/experiment --out eval/results/main_metrics.json
.venv/bin/python scripts/compute_metrics.py \
  --runs-dir runs/experiment_reserve --out eval/results/reserve_metrics.json

.venv/bin/python scripts/make_executive_summary.py \
  --main eval/results/main_metrics.json \
  --reserve eval/results/reserve_metrics.json \
  --out-dir eval/results
```

Genera `eval/results/EXECUTIVE_SUMMARY.md`, `main_table.md`, `reserve_table.md`.

### 5. Evaluación humana (ciega)

Generar las plantillas Excel:

```bash
# Individual: 50 artículos (15/framework + 5 baseline), orden aleatorio
.venv/bin/python scripts/build_human_eval.py

# Comparativa: 16 interacciones × 4 generadores (versiones A/B/C/D ciegas)
.venv/bin/python scripts/build_human_eval_comparative.py
```

El evaluador puntúa cada artículo (1–5) en las 5 dimensiones (claridad,
exactitud, completitud, aplicabilidad, consistencia) directamente en el Excel.
La hoja `key` (mapeo versión→framework) y la `rubrica` vienen incluidas. Guardar
el archivo puntuado como `*_scored.xlsx`.

### 6. Análisis estadístico combinado (humano + automático)

```bash
.venv/bin/python scripts/analyze_human_eval.py
```

Lee `eval/rubrics/human_evaluation_comparative_scored.xlsx` +
`eval/results/main_metrics.json` y produce en `eval/analysis/`:

- `statistical_tests.json` — descriptivo, Friedman por dimensión, W de Kendall,
  post-hoc (Nemenyi + Wilcoxon/Bonferroni), correlaciones, veredictos H1–H4.
- `thesis_tables.md` — tablas en markdown listas para la tesis.
- `figures/` — box plots, radar comparativo, heatmap interacción × framework.

---

## Configuración de control (`configs/experiments/budget.yaml`)

| Parámetro | Valor |
|---|---|
| Modelo | `claude-sonnet-4-6` (temperature 0.3, max_tokens 4096, prompt caching) |
| Presupuesto por lote | timeout 900s (watchdog 930s), max_tool_calls 150, max_cost_usd 2.00 |
| Tope global por run | `--max-total-cost 200` (obligatorio al lanzar) |
| Batching | `--batch-size 1` (1 interacción = 1 invocación) |
| Repeticiones | 3 (principal), 1 (estabilidad) |

**Costo/tiempo aproximado** (referencia): cada framework ~\$27/run × 3 runs;
~3–5 h por run. Baselines: prompt ~\$0.9/run, heurístico \$0. El estudio
principal completo cuesta del orden de \$250.

---

## Tests

```bash
.venv/bin/python -m pytest src/ -q
```

(Las pruebas de cada framework corren sobre 2 interacciones de calibración y
requieren `ANTHROPIC_API_KEY`.)

---

## Notas y limitaciones

- `runs/` y `eval/results/` están en `.gitignore` (artefactos pesados); los
  entregables de resultados se versionan de forma explícita cuando corresponde.
- Los LLM son no deterministas: aun con semillas fijas, los resultados exactos no
  son reproducibles bit a bit; se reportan medias y variabilidad inter-run.
- **H4** (evidence pack → exactitud) requiere la ablación `no_evidence`, cuyo
  wiring en los runners está pendiente — no evaluada (limitación documentada).
- El subset de 50 y la selección de evaluación humana usan `seed=42` para
  reproducibilidad de la muestra.

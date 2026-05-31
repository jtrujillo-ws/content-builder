# Proceso experimental — Content Builder

Documento de **proceso** (no de análisis de resultados). Registra la cronología,
la configuración final aplicada y los problemas técnicos encontrados durante la
batería experimental, con sus soluciones.

Caso de estudio: generación de artículos de base de conocimiento (KB) a partir de
interacciones de WhatsApp Business de Davivienda, comparando tres frameworks de
agentes autónomos (LangGraph, CrewAI, OpenAI Agents SDK) bajo el mismo modelo LLM
de control.

---

## 1. Cronología

| Fecha (2026) | Hito |
|---|---|
| **05-26** | Implementación inicial: migración a Python 3.11, prototipos de CrewAI y OpenAI Agents SDK (adapter LiteLLM), baselines (heurístico y single-prompt), scripts de orquestación (`verify`, `calibrate`, `run`, `compute`). |
| **05-27** | Refactor del runner a **invocaciones por lotes** (batched) en calibración y experimento. |
| **05-28** | Endurecimiento del runner: `max_tool_calls` → 150, timeout duro por subproceso vía watchdog (`threading.Timer`), `timeout_seconds` → 900s. Upgrade del modelo a **claude-sonnet-4-6** y corrección del ID (sin sufijo de fecha). Fix del prefill de CrewAI contra sonnet 4.6 + caché de embeddings entre lotes. Subset estratificado de 50 IDs y flag `--eval-subset`. |
| **05-29** | **Corridas principales** (split evaluación, subset 50, 3 runs): CrewAI y LangGraph completan sin incidentes; baselines heurístico y prompt completan. Primer intento de OpenAI Agents **aborta** por tope de costo por defecto ($20) → 42-43 artículos en vez de 52-57 (no comparable). |
| **05-30** | Diagnóstico del aborto de OpenAI Agents (cap default $20, no $200). Relanzamiento con `--max-total-cost 200` dejando la máquina desatendida (`caffeinate`). |
| **05-31** | OpenAI Agents principal completa **50/50 × 3 runs**. Se encadena automáticamente la **validación de robustez** sobre el split de reserva (37 interacciones × 1 run) para los 3 frameworks. Cómputo de métricas automáticas (`compute_metrics.py`) sobre ambos directorios y generación del resumen ejecutivo. Generación de la **plantilla de evaluación humana** (50 artículos, ciega). |

---

## 2. Configuración final

Parámetros fijos para los 3 frameworks (la única variable independiente es el
framework de orquestación). Fuente: `configs/experiments/budget.yaml`.

### Modelo LLM (variable de control)
| Parámetro | Valor |
|---|---|
| Proveedor / modelo | Anthropic — `claude-sonnet-4-6` |
| Temperature | 0.3 |
| max_tokens | 4096 |
| top_p | 1.0 |
| Prompt caching | habilitado (cachea system prompts) |

### Presupuesto por lote (1 lote = 1 invocación del runner)
| Parámetro | Valor |
|---|---|
| `timeout_seconds` | 900s (15 min) de wall-clock + 30s de gracia = **930s** corte por watchdog |
| `max_tool_calls` | 150 (corte duro sobre el agregado de tool invocations) |
| `max_cost_usd` | 2.00 (corte duro por costo estimado del lote) |
| Acción al exceder | `abort_run`, persistiendo estado parcial |

### Tope global por run
- `--max-total-cost 200` — **obligatorio al lanzar** (el default $20 trunca el run; ver §3.4).

### Estrategia de batching y repeticiones
- `--batch-size 1`: cada interacción se procesa en una invocación independiente del runner.
- Repeticiones: **3 runs** por framework (estudio principal), **1 run** (validación de robustez).

### Datos y particiones
- 183 interacciones WhatsApp Davivienda (`data/processed/interactions.jsonl`).
- Splits (`data/splits/splits.yaml`): calibración 37 · evaluación 109 · reserva 37.
- **Subset principal**: 50 interacciones del split de evaluación
  (`data/splits/eval_subset_50.yaml`), muestreo estratificado por
  `product_category × severity × query_type`, reparto por mayor residuo, seed 42.
- **Validación de robustez**: las 37 interacciones del split de reserva (flag `--split reserve`).

### Frameworks evaluados
- LangGraph, CrewAI, OpenAI Agents SDK (adapter LiteLLM).
- Baselines de control: `baseline_heuristic` (sin LLM) y `baseline_prompt` (un solo prompt).

---

## 3. Problemas encontrados y soluciones

### 3.1 Migración Python 3.9 → 3.11
**Problema:** la versión moderna de CrewAI requiere Python ≥ 3.10, incompatible con
el entorno inicial en 3.9.
**Solución:** migración del entorno a **Python 3.11**. Se mantuvo la convención de
anotaciones `Optional[X]` / `List[X]` por consistencia con el código existente.

### 3.2 Error de *prefill* de CrewAI contra sonnet 4.6
**Problema:** al ejecutar CrewAI sobre `claude-sonnet-4-6`, la ruta de CrewAI/LiteLLM
producía un mensaje de *assistant prefill* incompatible con la validación estricta
de mensajes de sonnet 4.6, abortando la llamada.
**Solución:** subclase del componente de completado de Anthropic
(`AnthropicCompletion`) que ajusta el prefill para cumplir el contrato del modelo.
Se introdujo junto con la caché de embeddings entre lotes (commit `b602a76`).

### 3.3 Fuga/colapso de file descriptors en OpenAI Agents (`init_sys_streams`)
**Problema:** el runner por lotes aísla cada lote en un subproceso `mp.spawn`. Si un
file descriptor estándar (0/1/2) del proceso padre quedaba inválido, el hijo abortaba
en el arranque del intérprete con
`Fatal Python error: init_sys_streams: can't initialize sys standard streams`
(`OSError: [Errno 9] Bad file descriptor`), exitcode 1 sin escribir resultado. Como
los runs comparten el proceso padre, una vez roto el fd fallaban en cascada todos los
lotes y runs restantes. Observado solo con OpenAI Agents (276 ocurrencias el 05-29;
run 1 murió en el lote 13). CrewAI y LangGraph nunca lo dispararon.
**Solución:** `_ensure_std_fds()` reabre `/dev/null` sobre cualquier fd estándar roto
**antes de cada `spawn`** (auto-sana por lote), y `proc.close()` tras cada `join()`
libera el fd centinela. Verificado: 3 runs completos, 0 crashes
(`scripts/_common.py`).

### 3.4 OpenAI Agents abortado por tope de costo por defecto ($20)
**Problema:** el flag `--max-total-cost` tiene default **$20**, demasiado bajo para
las 50 interacciones. El primer intento de OpenAI Agents se lanzó sin override → los
3 runs abortaron con estado `aborted_global` tras ~42-43 artículos (cobertura ~78%),
no comparables con CrewAI/LangGraph (que usaron $200 y completaron).
**Solución:** **siempre** lanzar con `--max-total-cost 200`. Relanzamiento de OpenAI
Agents con el tope correcto → 50/50 × 3 runs completos. Costo real ~$24/run, muy por
debajo del tope.

### 3.5 Timeouts duros en interacciones complejas (comportamiento conocido)
**Observación:** algunas interacciones individuales (p. ej. `INT-2024-033`,
`INT-2024-034`) ocasionalmente exceden el `timeout_seconds` de 900s y el watchdog las
corta a 930s, dejando 1 error registrado en el run. Es no-determinístico y propio del
framework (OpenAI Agents razona de más en esos casos). No invalida el run: se reporta
como tasa de fallo del framework, no como bug del experimento.

---

## 4. Pipeline de ejecución

| Script | Rol |
|---|---|
| `scripts/run_experiment.py` | Corre N repeticiones de un framework sobre un split. Flags clave: `--framework`, `--runs`, `--batch-size`, `--split {evaluation,reserve,calibration}`, `--out-subdir`, `--eval-subset`, `--max-total-cost`. |
| `scripts/compute_metrics.py` | Agrega los runs de un directorio y calcula métricas automáticas por framework (consolidación, calidad KCS, similitud vs KB de referencia, ingeniería). |
| `scripts/make_executive_summary.py` | Genera el resumen ejecutivo comparando estudio principal vs reserva; clasifica cambios de ranking con umbral de 5% relativo. |
| `scripts/build_human_eval.py` | Construye la plantilla de evaluación humana ciega (Excel) con muestreo estratificado y hoja de rúbrica. |

Scripts auxiliares de orquestación desatendida (no versionados como parte del método,
de un solo uso): `_relaunch_openai_tonight.sh`, `_reserve_runs.sh`,
`_overnight_orchestrator.sh`.

---

## 5. Artefactos generados

- `runs/experiment/<framework>/run_<n>/` — artículos generados, mapa
  artículo→interacción, trazas de ejecución, métricas, errores, metadata por run.
- `runs/experiment_reserve/<framework>/run_1/` — ídem para la validación de robustez.
- `eval/results/` — métricas automáticas (`main_metrics.json`, `reserve_metrics.json`),
  tablas (`main_table.md`, `reserve_table.md`) y `EXECUTIVE_SUMMARY.md`.
- `eval/rubrics/human_evaluation.xlsx` — plantilla de evaluación humana (hojas
  `evaluacion` ciega, `key` con el mapeo, `rubrica`).

> Nota: `runs/` y `eval/results/` están en `.gitignore`; los entregables de
> resultados se versionan de forma explícita cuando corresponde.

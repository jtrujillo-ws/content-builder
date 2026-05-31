#!/bin/zsh
# ---------------------------------------------------------------------------
# Orquestador nocturno desatendido. Encadena automáticamente:
#
#   1. Espera a que termine el OpenAI Agents PRINCIPAL (run_experiment --runs 3
#      sobre runs/experiment/). Monitorea por patrón de proceso.
#   2. Lanza OpenAI Agents sobre el split de RESERVA (1 run, batch 1, cap $200)
#      → runs/experiment_reserve/openai_agents/. Espera a que termine.
#   3. Espera a que crewai+langgraph reserve (_reserve_runs.sh) terminen.
#   4. Con TODO terminado (principal + 3 reserves), corre compute_metrics sobre
#      AMBOS directorios y genera el resumen ejecutivo en eval/results/.
#
# Mantiene la Mac despierta durante toda su vida (caffeinate propio).
#
# Uso:
#   nohup zsh scripts/_overnight_orchestrator.sh \
#       > runs/experiment_reserve/_logs/orchestrator.log 2>&1 &
#   disown
# ---------------------------------------------------------------------------
set -u
cd /Users/julian.trujillo/Documents/trabajo-grado/content-builder

TS=$(date -u +%Y%m%dT%H%M%SZ)
LOGDIR="runs/experiment_reserve/_logs"
RESULTS="eval/results"
mkdir -p "$LOGDIR" "$RESULTS"

log(){ echo "[orch $(date -u +%H:%M:%SZ)] $*"; }

# caffeinate para toda la vida del orquestador (cubre el hueco cuando mueren
# los caffeinate del run principal y de _reserve_runs.sh).
caffeinate -dimsu &
CAF=$!
trap 'kill $CAF 2>/dev/null' EXIT

log "orquestador arrancado (${TS})."

# ---- 1) Esperar al OpenAI principal (--runs 3) ----
log "esperando a que termine OpenAI PRINCIPAL (run_experiment --runs 3)..."
while pgrep -f "run_experiment.py --framework openai_agents --runs 3" >/dev/null 2>&1; do
  sleep 60
done
log "OpenAI principal terminó."

# ---- 2) Lanzar OpenAI sobre reserva y esperar ----
OA_LOG="${LOGDIR}/openai_agents_reserve_${TS}.log"
log "lanzando OpenAI RESERVE → ${OA_LOG}"
.venv/bin/python scripts/run_experiment.py \
  --framework openai_agents \
  --runs 1 \
  --batch-size 1 \
  --split reserve \
  --out-subdir experiment_reserve \
  --max-total-cost 200 \
  > "$OA_LOG" 2>&1
log "OpenAI reserve terminó (exit=$?)."

# ---- 3) Esperar a crewai+langgraph reserve ----
log "esperando a crewai/langgraph reserve (_reserve_runs.sh)..."
while pgrep -f "scripts/_reserve_runs.sh" >/dev/null 2>&1; do
  sleep 60
done
log "todos los reserves terminaron."

# ---- 4) Métricas finales + resumen ejecutivo ----
log "computando métricas PRINCIPAL (runs/experiment)..."
.venv/bin/python scripts/compute_metrics.py \
  --runs-dir runs/experiment \
  --out "${RESULTS}/main_metrics.json" \
  > "${RESULTS}/main_table.txt" 2>&1
log "  → ${RESULTS}/main_metrics.json"

log "computando métricas RESERVA (runs/experiment_reserve)..."
.venv/bin/python scripts/compute_metrics.py \
  --runs-dir runs/experiment_reserve \
  --out "${RESULTS}/reserve_metrics.json" \
  > "${RESULTS}/reserve_table.txt" 2>&1
log "  → ${RESULTS}/reserve_metrics.json"

log "generando resumen ejecutivo..."
.venv/bin/python scripts/make_executive_summary.py \
  --main "${RESULTS}/main_metrics.json" \
  --reserve "${RESULTS}/reserve_metrics.json" \
  --out-dir "${RESULTS}" \
  --timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

log "DONE. Entregables en ${RESULTS}/:"
log "  - EXECUTIVE_SUMMARY.md  (resumen ejecutivo + robustez)"
log "  - main_table.md / reserve_table.md"
log "  - main_metrics.json / reserve_metrics.json (+ .txt)"

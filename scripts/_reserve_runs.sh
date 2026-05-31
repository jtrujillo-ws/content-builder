#!/bin/zsh
# ---------------------------------------------------------------------------
# Validación de robustez sobre el split de RESERVA (37 interacciones), 1 run
# por framework, batch-size 1, cap $200. Resultados separados del estudio
# principal en runs/experiment_reserve/ (NO toca runs/experiment/).
#
# CrewAI y LangGraph se corren EN SECUENCIA (no en paralelo) para no sumar un
# tercer framework concurrente mientras el OpenAI principal sigue corriendo
# en runs/experiment/ — así se evita rate-limit de la API.
#
# Uso:
#   nohup zsh scripts/_reserve_runs.sh > /tmp/reserve_runs.log 2>&1 &
#   disown
#
# OpenAI sobre reserve NO se lanza aquí (lo lanza el usuario tras el principal).
# ---------------------------------------------------------------------------
set -u
cd /Users/julian.trujillo/Documents/trabajo-grado/content-builder

TS=$(date -u +%Y%m%dT%H%M%SZ)
LOGDIR="runs/experiment_reserve/_logs"
mkdir -p "$LOGDIR"

echo "[reserve] arrancando validación de robustez (split reserve) ${TS}"

# Mantener la Mac despierta durante toda la batería de reserva (el caffeinate
# del run principal muere cuando OpenAI termina ~02:00, pero estos siguen).
caffeinate -dimsu &
CAF=$!

run_one() {
  local fw="$1"
  local log="${LOGDIR}/${fw}_reserve_${TS}.log"
  echo "[reserve] ── ${fw} (reserve) → ${log}"
  .venv/bin/python scripts/run_experiment.py \
    --framework "$fw" \
    --runs 1 \
    --batch-size 1 \
    --split reserve \
    --out-subdir experiment_reserve \
    --max-total-cost 200 \
    > "$log" 2>&1
  echo "[reserve] ── ${fw} terminó (exit=$?)"
}

run_one crewai
run_one langgraph

kill "$CAF" 2>/dev/null
echo "[reserve] DONE ${TS} — resultados en runs/experiment_reserve/{crewai,langgraph}/"

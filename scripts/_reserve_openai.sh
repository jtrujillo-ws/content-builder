#!/bin/zsh
# ---------------------------------------------------------------------------
# OpenAI Agents — validación de estabilidad sobre el split de RESERVA (37 inter.),
# 1 run, batch-size 1, cap $200. Salida en runs/experiment_reserve/openai_agents/.
#
# LANZAR SOLO cuando el run PRINCIPAL de openai (runs/experiment/) haya
# terminado (~02:00) — para no tener dos procesos openai pisándose la API.
#
# Uso:
#   nohup zsh scripts/_reserve_openai.sh > /tmp/reserve_openai.log 2>&1 &
#   disown
# ---------------------------------------------------------------------------
set -u
cd /Users/julian.trujillo/Documents/trabajo-grado/content-builder

TS=$(date -u +%Y%m%dT%H%M%SZ)
LOGDIR="runs/experiment_reserve/_logs"
mkdir -p "$LOGDIR"
LOG="${LOGDIR}/openai_agents_reserve_${TS}.log"

echo "[reserve-openai] arrancando ${TS} → ${LOG}"

caffeinate -dimsu &
CAF=$!

.venv/bin/python scripts/run_experiment.py \
  --framework openai_agents \
  --runs 1 \
  --batch-size 1 \
  --split reserve \
  --out-subdir experiment_reserve \
  --max-total-cost 200 \
  > "$LOG" 2>&1

kill "$CAF" 2>/dev/null
echo "[reserve-openai] DONE — resultados en runs/experiment_reserve/openai_agents/"

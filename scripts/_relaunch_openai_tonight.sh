#!/bin/zsh
# ---------------------------------------------------------------------------
# Relanzar OpenAI Agents (3 runs) con el tope de costo correcto ($200), igual
# que crewai/langgraph, para que los 3 runs completen las 50 interacciones y
# sean comparables. Al terminar, recomputa la tabla de métricas con TODOS los
# frameworks + baselines.
#
# Uso (lánzalo de noche):
#   nohup zsh scripts/_relaunch_openai_tonight.sh > /tmp/openai_tonight.log 2>&1 &
#   disown
#
# Seguro de re-ejecutar: sobrescribe runs/experiment/openai_agents/run_{1,2,3}.
# ---------------------------------------------------------------------------
set -u
cd /Users/julian.trujillo/Documents/trabajo-grado/content-builder

TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG="runs/experiment/_logs/openai_agents_relaunch_${TS}.log"
TABLE="runs/experiment/_logs/FINAL_metrics_table.txt"
JSON="runs/experiment/metrics_comparative.json"

echo "[tonight] arrancando openai_agents (cap \$200) ${TS}"

# 1) Mantener la Mac despierta mientras dure el run (sale solo al terminar).
caffeinate -dimsu &
CAF=$!

# 2) Run principal: 3 runs, batch-size 1, subset de 50, tope $200.
.venv/bin/python scripts/run_experiment.py \
  --framework openai_agents \
  --runs 3 \
  --batch-size 1 \
  --eval-subset data/splits/eval_subset_50.yaml \
  --max-total-cost 200 \
  > "$LOG" 2>&1

echo "[tonight] openai terminó — recomputando métricas..."

# 3) Liberar caffeinate.
kill "$CAF" 2>/dev/null

# 4) Recomputar la tabla comparativa (3 frameworks + 2 baselines).
rm -f "$TABLE"
.venv/bin/python scripts/compute_metrics.py --out "$JSON" > "$TABLE" 2>&1
echo "[tonight] DONE — tabla en $TABLE / json en $JSON" | tee -a "$TABLE"

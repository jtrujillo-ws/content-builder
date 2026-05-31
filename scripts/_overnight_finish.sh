#!/bin/zsh
# Autónomo: espera a que termine el run de openai_agents y luego computa
# métricas. Se lanza con nohup para sobrevivir al cierre de la sesión.
set -u
cd /Users/julian.trujillo/Documents/trabajo-grado/content-builder
LOG="$(cat /tmp/openai_relaunch_logpath.txt)"
OUT_TABLE="runs/experiment/_logs/FINAL_metrics_table.txt"
OUT_JSON="runs/experiment/metrics_comparative.json"

# 1) Esperar a que openai termine (marca final en log o proceso ausente).
while true; do
  if grep -q "EXPERIMENTO — openai_agents" "$LOG" 2>/dev/null; then break; fi
  if ! pgrep -f "scripts/run_experiment.py --framework openai_agents" >/dev/null; then break; fi
  sleep 30
done

echo "[finish] openai terminó $(date -u +%H:%M:%SZ) — computando métricas..." >> "$OUT_TABLE"
# 2) Computar métricas (incluye los 3 frameworks + 2 baselines).
.venv/bin/python scripts/compute_metrics.py --out "$OUT_JSON" >> "$OUT_TABLE" 2>&1
echo "[finish] DONE $(date -u +%H:%M:%SZ)" >> "$OUT_TABLE"

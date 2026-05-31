# Resumen ejecutivo — Comparación de frameworks de agentes

_Generado: 2026-05-31T12:00:45Z_

Comparación empírica de LangGraph, CrewAI y OpenAI Agents SDK para generación de artículos de KB (caso Davivienda). Modelo base idéntico (claude-sonnet-4-6); la única variable es el framework de orquestación.

## 1. Estudio principal — split evaluation (50 interacciones × 3 runs)

| framework | runs | arts | cov% | KCS% | ev% | simK | lat_med | lat_p90 | cost$ | tools | fail% | LOC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_heuristic | 3 | 50.0 | 100.0 | 100 | 100 | 37 | 116.7 | 119.9 | 0.000 | 0 | 0 | 282 |
| baseline_prompt | 3 | 50.0 | 100.0 | 100 | 100 | 43 | 826.6 | 827.2 | 0.917 | 0 | 0 | 340 |
| langgraph | 3 | 52.7 | 86.7 | 100 | 100 | 41 | 17398.0 | 17724.3 | 28.098 | 1964 | 0 | 831 |
| crewai | 3 | 52.3 | 98.7 | 100 | 96 | 42 | 15742.2 | 16507.1 | 27.060 | 687 | 0 | 932 |
| openai_agents | 3 | 57.0 | 99.3 | 100 | 100 | 40 | 14863.2 | 15382.1 | 27.169 | 1206 | 0 | 803 |

Leyenda: arts=artículos prom., cov%=cobertura interacciones, KCS%=cumplimiento plantilla, ev%=cobertura evidencia, simK=similitud TF-IDF vs KB referencia, lat=latencia (s), cost$=costo mediano, tools=tool calls prom., fail%=tasa de fallo, LOC=líneas de implementación.

## 2. Validación de robustez — split reserve (37 interacciones × 1 run)

| framework | runs | arts | cov% | KCS% | ev% | simK | lat_med | lat_p90 | cost$ | tools | fail% | LOC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| langgraph | 1 | 40.0 | 91.9 | 100 | 100 | 40 | 11624.6 | 11624.6 | 17.286 | 1207 | 0 | 831 |
| crewai | 1 | 37.0 | 100.0 | 100 | 98 | 38 | 10916.7 | 10916.7 | 18.833 | 491 | 0 | 932 |
| openai_agents | 1 | 42.0 | 97.3 | 100 | 100 | 39 | 11257.7 | 11257.7 | 21.342 | 956 | 0 | 803 |

## 3. ¿Se mantienen los patrones en la reserva?

Comparación de los 3 frameworks de orquestación entre el estudio principal (50 interacciones × 3 runs) y la validación de robustez (37 interacciones × 1 run). Un cambio de ranking solo se considera **real** si la diferencia entre frameworks supera el **5% relativo en ambos splits**; los flips entre valores casi empatados se marcan como ruido y NO penalizan la robustez.

| Métrica | Ranking principal | Ranking reserva | Veredicto |
|---|---|---|---|
| Cumplimiento KCS (KCS%) | langgraph > crewai > openai_agents | langgraph > crewai > openai_agents | ✅ se mantiene |
| Cobertura de evidencia (ev%) | langgraph > openai_agents > crewai | langgraph > openai_agents > crewai | ✅ se mantiene |
| Similitud vs KB referencia (simK) | crewai > langgraph > openai_agents | langgraph > openai_agents > crewai | ✅ estable (flip <5%: empate) |
| Cobertura de interacciones (cov%) | openai_agents > crewai > langgraph | crewai > openai_agents > langgraph | ✅ estable (flip <5%: empate) |
| Costo mediano por run ($) | crewai > openai_agents > langgraph | langgraph > crewai > openai_agents | ✅ estable (flip <5%: empate) |
| Tool calls promedio | crewai > openai_agents > langgraph | crewai > openai_agents > langgraph | ✅ se mantiene |
| Tasa de fallo (fail%) | langgraph > crewai > openai_agents | langgraph > crewai > openai_agents | ✅ se mantiene |
| Latencia mediana (s) | openai_agents > crewai > langgraph | crewai > openai_agents > langgraph | ✅ estable (flip <5%: empate) |

### Deltas por framework (reserva − principal)

| framework | KCS% | ev% | simK | cov% | cost$ | tools |
|---|---|---|---|---|---|---|
| langgraph | +0.0 | +0.0 | -0.9 | +5.2 | -10.812 | -756.7 |
| crewai | +0.0 | +1.3 | -4.1 | +1.3 | -8.226 | -196.3 |
| openai_agents | +0.0 | +0.2 | -1.3 | -2.0 | -5.827 | -250.0 |

### Veredicto de robustez

**✅ Los patrones se mantienen.** 8/8 rankings de métricas se conservan (100%). Los hallazgos del estudio principal son robustos frente al split de reserva.

> Nota metodológica: la reserva tiene 1 run por framework (vs 3 en el principal) y 37 vs 50 interacciones, por lo que su varianza es mayor. Un cambio de ranking en métricas con valores muy cercanos no implica necesariamente un patrón distinto.

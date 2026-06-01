# Tablas de tesis — Análisis combinado (humano + automático)

_n = 64 evaluaciones (16 interacciones × 4 generadores), evaluación humana comparativa ciega._

## 1. Estadística descriptiva — puntuación humana (media ± std, [mediana])

| framework | claridad | exactitud | completitud | aplicabilidad | consistencia | **global** |
|---|---|---|---|---|---|---|
| LangGraph | 4.12±0.33 [4] | 4.19±0.39 [4] | 4.25±0.43 [4] | 4.12±0.33 [4] | 4.06±0.24 [4] | **4.15±0.36** |
| CrewAI | 4.31±0.58 [4] | 4.38±0.60 [4] | 4.56±0.50 [5] | 4.31±0.58 [4] | 4.38±0.48 [4] | **4.39±0.56** |
| OpenAI | 4.19±0.39 [4] | 4.31±0.46 [4] | 4.44±0.50 [4] | 4.06±0.24 [4] | 4.12±0.33 [4] | **4.22±0.42** |
| Baseline | 4.12±0.33 [4] | 4.19±0.39 [4] | 4.12±0.33 [4] | 4.19±0.39 [4] | 4.12±0.33 [4] | **4.15±0.36** |

## 2. Pruebas de Friedman por dimensión (bloques = interacción)

| dimensión | χ² | p | sig. | W Kendall | interpretación | mejor (rango↓) |
|---|---|---|---|---|---|---|
| claridad | 2.40 | 0.4936 | — | 0.050 | acuerdo muy débil | CrewAI (2.25) |
| exactitud | 2.13 | 0.5454 | — | 0.044 | acuerdo muy débil | CrewAI (2.25) |
| completitud | 6.69 | 0.0824 | — | 0.139 | acuerdo débil | CrewAI (2.06) |
| aplicabilidad | 4.20 | 0.2407 | — | 0.087 | acuerdo muy débil | CrewAI (2.22) |
| consistencia | 6.10 | 0.1067 | — | 0.127 | acuerdo débil | CrewAI (2.09) |

_Ninguna dimensión alcanzó significancia en Friedman (p<0.05); sin post-hoc._

## 3. Tabla consolidada — calidad humana + eficiencia automática

| framework | humano global | KCS% | evid% | cobertura% | costo$ | tool_calls | LOC |
|---|---|---|---|---|---|---|---|
| LangGraph | 4.15 | 100.0 | 100.0 | 86.7 | 28.098 | 1963.7 | 831 |
| CrewAI | 4.39 | 100.0 | 96.4 | 98.7 | 27.06 | 687.3 | 932 |
| OpenAI | 4.22 | 100.0 | 99.8 | 99.3 | 27.169 | 1206 | 803 |
| Baseline | 4.15 | 100.0 | 100.0 | 100.0 | 0.917 | 0 | 340 |

## 4. Correlación humano ↔ automático (n=4 generadores)

| métrica auto | Spearman ρ | p | Pearson r | p | lectura |
|---|---|---|---|---|---|
| cost_usd | -0.105 | 0.895 | 0.440 | 0.560 | ↓ |
| tool_calls | -0.105 | 0.895 | -0.171 | 0.829 | ↓ |
| coverage_pct | -0.105 | 0.895 | 0.391 | 0.609 | ↓ |

> ⚠️ n=4 generadores: las correlaciones son exploratorias, sin potencia para significancia. Interpretar como tendencia, no como prueba.

## 5. Figuras

- `figures/boxplots_dimensions.png` — distribución por dimensión × framework
- `figures/radar_comparative.png` — 5 dim. humanas + 2 métricas de eficiencia (normalizado)
- `figures/heatmap_interaction_framework.png` — media por interacción × framework

## 6. Contraste de hipótesis H1–H4

### ❌ H1 — REFUTADA
*H1: LangGraph tendrá menor tasa de fallos que los otros frameworks.*

| framework | tasa de fallo (errores/lotes) |
|---|---|
| LangGraph | 22.67% |
| CrewAI | 1.33% |
| OpenAI | 2.0% |

LangGraph tiene la tasa de fallo MÁS ALTA (22.67%); la menor es CrewAI (1.33%).

### 🟡 H2 — PARCIALMENTE SOPORTADA
*H2: CrewAI tendrá mayor calidad percibida en claridad y aplicabilidad.*

| dimensión | medias (LG / CW / OA) | mejor 3-fw | Friedman p (3-fw) | sig. |
|---|---|---|---|---|
| claridad | 4.12 / 4.31 / 4.19 | CrewAI | 0.3679 | — |
| aplicabilidad | 4.12 / 4.31 / 4.06 | CrewAI | 0.1561 | — |

CrewAI obtiene la media más alta entre los 3 frameworks en ambas dimensiones, pero el Friedman restringido a los 3 frameworks NO alcanza significancia (las diferencias entre frameworks no son estadísticamente concluyentes).

### 🟡 H3 — EVALUADA (parcial)
*H3: Mejor instrumentación → mejor reproducibilidad (menor CV inter-run).*

| framework | CV costo | CV tool_calls | CV artículos | CV medio |
|---|---|---|---|---|
| LangGraph | 2.99% | 3.09% | 1.79% | **2.62%** |
| CrewAI | 0.82% | 0.49% | 0.9% | **0.74%** |
| OpenAI | 1.03% | 1.8% | 1.43% | **1.42%** |

CrewAI es el más reproducible (CV medio 0.74%). Nota: la 'instrumentación' no se midió como variable independiente; se reporta la reproducibilidad (CV) como evidencia observacional, no causal.

### ⚪ H4 — NO EVALUADA
*H4: La presencia de evidence pack mejora la exactitud.*

LIMITACIÓN: requiere la ablación `no_evidence` (generar artículos sin evidence pack y comparar exactitud), que NO se ejecutó en esta batería. El flag `--ablation no_evidence` existe pero sólo se registra en metadata; el wiring en los runners está pendiente. No se puede contrastar con los datos actuales.

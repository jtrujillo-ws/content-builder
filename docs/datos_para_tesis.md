# Datos cuantitativos para la tesis (secciones 8–10)

Contenido numérico extraído de `eval/results/`, `eval/analysis/` y
`runs/experiment/`. Las cifras son exactas (leídas de los archivos). Salvo
indicación, el estudio principal es sobre el **subset de 50 interacciones del
split de evaluación**, **3 runs por generador**; la validación de robustez es
sobre el **split de reserva (37 interacciones), 1 run**.

> **Nota sobre subpreguntas (SP1–SP5):** el texto exacto de las subpreguntas de
> investigación no está en el repositorio. En la §10 se proponen 5 subpreguntas
> **inferidas del diseño experimental** (marcadas como _inferida_); reemplázalas
> por el enunciado literal de tu documento manteniendo los datos asociados.

---

# SECCIÓN 8 — ANÁLISIS DE DATOS

## 8.1 Descripción del dataset final

183 interacciones de WhatsApp Business (Davivienda Colombia) y 118 artículos KB
de referencia (ground truth, no usados como input del agente).

**Por categoría de producto**

| product_category | n | % |
|---|---|---|
| cuentas | 34 | 18.58% |
| creditos | 32 | 17.49% |
| transferencias | 31 | 16.94% |
| otros | 30 | 16.39% |
| tarjetas | 29 | 15.85% |
| canales_digitales | 27 | 14.75% |
| **Total** | **183** | **100%** |

**Por severidad**

| severity | n | % |
|---|---|---|
| operativa | 89 | 48.63% |
| informativa | 63 | 34.43% |
| critica | 31 | 16.94% |

**Por tipo de consulta**

| query_type | n | % |
|---|---|---|
| politica | 51 | 27.87% |
| troubleshooting | 47 | 25.68% |
| howto | 44 | 24.04% |
| faq | 41 | 22.40% |

**Turnos por interacción**

| métrica | valor |
|---|---|
| media | 7.74 |
| mediana | 8 |
| mínimo | 7 |
| máximo | 10 |
| desv. estándar | 0.53 |

**Particiones** (`data/splits/splits.yaml`): calibración 37 · evaluación 109 ·
reserva 37. Subset del estudio principal: 50 interacciones del split de
evaluación, estratificado por `product_category × severity × query_type`
(seed 42).

## 8.2 Resultados de detección / generación por framework

Estudio principal (50 interacciones × 3 runs; promedios entre runs).

| Framework | artículos (prom.) | cobertura % | KCS % | evidencia % | simK |
|---|---|---|---|---|---|
| LangGraph | 52.67 | 86.67 | 100.00 | 100.00 | 41.02 |
| CrewAI | 52.33 | 98.67 | 100.00 | 96.42 | 41.98 |
| OpenAI Agents | 57.00 | 99.33 | 100.00 | 99.84 | 40.43 |
| Baseline (prompt) | 50.00 | 100.00 | 100.00 | 100.00 | 42.84 |
| Baseline (heurístico) | 50.00 | 100.00 | 100.00 | 100.00 | 36.61 |

- **artículos**: promedio de artículos generados por run (los frameworks
  consolidan/dividen, por eso difieren de 50).
- **cobertura %**: interacciones del input efectivamente cubiertas por algún artículo.
- **KCS %**: cumplimiento de la plantilla KCS (todos al 100%).
- **evidencia %**: cobertura de `evidence_pack` (afirmaciones con respaldo).
- **simK**: mejor similitud TF-IDF del artículo vs el KB de referencia (×100).

## 8.3 Métricas de ingeniería por framework

| Framework | latencia mediana (s/run) | lat. p90 (s) | costo mediano ($/run) | costo total ($/3 runs) | tool calls (prom.) | tasa de fallos % | LOC |
|---|---|---|---|---|---|---|---|
| LangGraph | 17397.96 | 17724.29 | 28.0977 | 85.1386 | 1963.67 | 0.00 | 831 |
| CrewAI | 15742.24 | 16507.12 | 27.0596 | 81.5794 | 687.33 | 0.00 | 932 |
| OpenAI Agents | 14863.23 | 15382.09 | 27.1687 | 81.9503 | 1206.00 | 0.00 | 803 |
| Baseline (prompt) | 826.65 | 827.17 | 0.9170 | 2.7436 | 0.00 | 0.00 | 340 |
| Baseline (heurístico) | 116.74 | 119.91 | 0.0000 | 0.0000 | 0.00 | 0.00 | 282 |

- **latencia**: wall-clock por run completo (50 interacciones), mediana de 3 runs.
  Equivalencias: LangGraph ≈ 4.83 h, CrewAI ≈ 4.37 h, OpenAI ≈ 4.13 h,
  baseline_prompt ≈ 13.8 min, heurístico ≈ 1.95 min.
- **tasa de fallos** aquí es a nivel de **run** (status ≠ completed) = 0% para
  todos. La tasa a nivel de **lote** (errores/lotes), relevante para H1, se
  reporta en §9.1.
- **LOC**: líneas de implementación del runner de cada framework.

## 8.4 Resultados de Friedman por dimensión humana

Evaluación humana comparativa ciega: 16 interacciones × 4 generadores
(LangGraph, CrewAI, OpenAI, Baseline-prompt) = 64 artículos. Diseño de bloques
repetidos (bloque = interacción). α = 0.05.

| Dimensión | χ² | p-valor | significativo | W de Kendall | interpretación W |
|---|---|---|---|---|---|
| claridad | 2.4000 | 0.493635 | No | 0.0500 | acuerdo muy débil |
| exactitud | 2.1325 | 0.545360 | No | 0.0444 | acuerdo muy débil |
| completitud | 6.6923 | 0.082379 | No | 0.1394 | acuerdo débil |
| accionabilidad | 4.2000 | 0.240662 | No | 0.0875 | acuerdo muy débil |
| consistencia | 6.1034 | 0.106684 | No | 0.1272 | acuerdo débil |

**Ninguna dimensión alcanza significancia (p < 0.05)** → no hay diferencias
estadísticamente concluyentes en calidad humana percibida entre los 4
generadores; no se aplica post-hoc.

**Rangos promedio de Friedman** (menor = mejor):

| Dimensión | LangGraph | CrewAI | OpenAI | Baseline |
|---|---|---|---|---|
| claridad | 2.625 | 2.250 | 2.500 | 2.625 |
| exactitud | 2.656 | 2.250 | 2.438 | 2.656 |
| completitud | 2.688 | 2.062 | 2.312 | 2.938 |
| accionabilidad | 2.594 | 2.219 | 2.719 | 2.469 |
| consistencia | 2.719 | 2.094 | 2.594 | 2.594 |

**Estadística descriptiva humana por dimensión** (media ± SD [mediana], escala 1–5):

| Framework | claridad | exactitud | completitud | accionabilidad | consistencia | global |
|---|---|---|---|---|---|---|
| LangGraph | 4.125±0.331 [4] | 4.188±0.390 [4] | 4.250±0.433 [4] | 4.125±0.331 [4] | 4.062±0.242 [4] | 4.150±0.357 |
| CrewAI | 4.312±0.583 [4] | 4.375±0.599 [4] | 4.562±0.496 [5] | 4.312±0.583 [4] | 4.375±0.484 [4] | 4.388±0.559 |
| OpenAI | 4.188±0.390 [4] | 4.312±0.464 [4] | 4.438±0.496 [4] | 4.062±0.242 [4] | 4.125±0.331 [4] | 4.225±0.418 |
| Baseline | 4.125±0.331 [4] | 4.188±0.390 [4] | 4.125±0.331 [4] | 4.188±0.390 [4] | 4.125±0.331 [4] | 4.150±0.357 |

## 8.5 Efectos de las ablaciones

**No se ejecutaron ablaciones.** El flag `--ablation {no_grouping, no_critic,
no_evidence, no_memory}` existe en `run_experiment.py` pero, salvo `no_grouping`
(que sólo fuerza `batch_size=1`), las ablaciones se registran en metadata y no
alteran el comportamiento del runner (wiring pendiente). Todos los
`experiment_summary.json` tienen `ablation: null`. En consecuencia, hipótesis que
dependen de una ablación —en particular H4 (evidence pack → exactitud)— no pueden
contrastarse con los datos actuales (ver §9.1 y §8 limitaciones).

---

# SECCIÓN 9 — DISCUSIÓN

## 9.1 Resultados por hipótesis (H1–H4)

| Hipótesis | Enunciado | Dato clave | Veredicto |
|---|---|---|---|
| **H1** | LangGraph tendrá menor tasa de fallos | tasa de fallos (errores/lotes): **LangGraph 22.67%**, CrewAI 1.33%, OpenAI 2.00% | ❌ **REFUTADA** (LangGraph es el más alto; el menor es CrewAI) |
| **H2** | CrewAI mayor calidad en claridad y accionabilidad | CrewAI tiene la media más alta entre los 3 frameworks en ambas, pero Friedman 3-fw no es significativo | 🟡 **PARCIALMENTE SOPORTADA** (dirección sí, significancia no) |
| **H3** | Mejor instrumentación → mejor reproducibilidad (CV inter-run) | CV medio (costo/tools/artículos): **CrewAI 0.74%**, OpenAI 1.42%, LangGraph 2.62% | 🟡 **EVALUADA (parcial)**: CrewAI el más reproducible |
| **H4** | Evidence pack → mejor exactitud | Requiere ablación `no_evidence` (no ejecutada) | ⚪ **NO EVALUADA** (limitación) |

**H1 — tasa de fallos (errores/lotes, 3 runs × 50 = 150 lotes)**

| Framework | errores totales | lotes | tasa de fallos % |
|---|---|---|---|
| LangGraph | 34 | 150 | 22.67% |
| CrewAI | 2 | 150 | 1.33% |
| OpenAI Agents | 3 | 150 | 2.00% |

**H2 — Friedman restringido a los 3 frameworks (sin baseline)**

| Dimensión | LangGraph | CrewAI | OpenAI | mejor | p-valor | W | sig. |
|---|---|---|---|---|---|---|---|
| claridad | 4.125 | 4.312 | 4.188 | CrewAI | 0.3679 | 0.0625 | No |
| accionabilidad | 4.125 | 4.312 | 4.062 | CrewAI | 0.1561 | 0.1161 | No |

**H3 — coeficiente de variación inter-run (3 runs)**

| Framework | CV costo % | CV tool_calls % | CV artículos % | CV medio % |
|---|---|---|---|---|
| LangGraph | 2.99 | 3.09 | 1.79 | 2.62 |
| CrewAI | 0.82 | 0.49 | 0.90 | 0.74 |
| OpenAI Agents | 1.03 | 1.80 | 1.43 | 1.42 |

> El CV medio excluye el conteo de `errors` (entero diminuto cuyo CV relativo es
> enorme y ruidoso); su variabilidad se cubre en H1.

## 9.2 Calidad humana vs eficiencia automática (lado a lado)

| Framework | calidad humana (global) | simK | cobertura % | evidencia % | costo mediano $ | tool calls | tasa fallos % | LOC |
|---|---|---|---|---|---|---|---|---|
| LangGraph | 4.150 | 41.02 | 86.67 | 100.00 | 28.0977 | 1963.67 | 22.67 | 831 |
| CrewAI | 4.388 | 41.98 | 98.67 | 96.42 | 27.0596 | 687.33 | 1.33 | 932 |
| OpenAI Agents | 4.225 | 40.43 | 99.33 | 99.84 | 27.1687 | 1206.00 | 2.00 | 803 |
| Baseline (prompt) | 4.150 | 42.84 | 100.00 | 100.00 | 0.9170 | 0.00 | n/a | 340 |

> Lectura: la calidad humana es estadísticamente indistinguible entre generadores
> (§8.4), mientras que la eficiencia difiere en órdenes de magnitud. El baseline de
> un solo prompt iguala la calidad percibida a ~1/30 del costo y sin tool calls.

**Correlación calidad humana ↔ métrica automática** (n = 4 generadores, exploratoria):

| Métrica auto | Spearman ρ | p | Pearson r | p |
|---|---|---|---|---|
| simK | −0.211 | 0.789 | 0.036 | 0.964 |
| costo $ | −0.105 | 0.895 | 0.440 | 0.560 |
| tool_calls | −0.105 | 0.895 | −0.171 | 0.829 |
| cobertura % | −0.105 | 0.895 | 0.391 | 0.609 |

> Con n = 4 no hay potencia estadística; ninguna correlación es significativa.
> Se reportan como tendencia, no como prueba.

## 9.3 Validación de robustez (reserva vs principal)

Split de reserva: 37 interacciones, 1 run por framework.

| Framework | escenario | artículos | cobertura % | KCS % | evidencia % | simK | costo $ | tool calls | fallos % |
|---|---|---|---|---|---|---|---|---|---|
| LangGraph | principal | 52.67 | 86.67 | 100 | 100.00 | 41.02 | 28.10 | 1963.67 | 0 |
| LangGraph | reserva | 40.00 | 91.89 | 100 | 100.00 | 40.10 | 17.29 | 1207.00 | 0 |
| CrewAI | principal | 52.33 | 98.67 | 100 | 96.42 | 41.98 | 27.06 | 687.33 | 0 |
| CrewAI | reserva | 37.00 | 100.00 | 100 | 97.70 | 37.89 | 18.83 | 491.00 | 0 |
| OpenAI | principal | 57.00 | 99.33 | 100 | 99.84 | 40.43 | 27.17 | 1206.00 | 0 |
| OpenAI | reserva | 42.00 | 97.30 | 100 | 100.00 | 39.16 | 21.34 | 956.00 | 0 |

**Estabilidad de patrones** (umbral 5% relativo, ver `EXECUTIVE_SUMMARY.md`): los
rankings se mantienen en las métricas con separación real (KCS, evidencia,
tool_calls, fallos); los cambios de orden en simK/costo/cobertura ocurren entre
valores casi empatados (dentro de ±5%) y se consideran ruido. Veredicto: **8/8
rankings robustos**.

## 9.4 Ranking por escenario organizacional

Cada escenario prioriza distintas columnas de §9.2. (Recordatorio: las
diferencias de calidad humana no son estadísticamente significativas; los
rankings de calidad se basan en medias puntuales.)

**Escenario A — Prototipado rápido** (prioriza costo, latencia, simplicidad/LOC, reproducibilidad)

| Puesto | Opción | Costo $/run | Latencia | LOC | CV medio | Justificación |
|---|---|---|---|---|---|---|
| 1 | Baseline (prompt) | 0.9170 | 13.8 min | 340 | — | Iguala calidad percibida a costo y complejidad mínimos |
| 2 | CrewAI | 27.06 | 4.37 h | 932 | 0.74% | El más reproducible y menos tool calls entre frameworks |
| 3 | OpenAI Agents | 27.17 | 4.13 h | 803 | 1.42% | Menor latencia; reproducibilidad intermedia |
| 4 | LangGraph | 28.10 | 4.83 h | 831 | 2.62% | Más caro, más lento, mayor variabilidad |

**Escenario B — Producción auditada** (prioriza trazabilidad/evidencia, baja tasa de fallos, cobertura, reproducibilidad)

| Puesto | Opción | evidencia % | fallos % | cobertura % | CV medio | Justificación |
|---|---|---|---|---|---|---|
| 1 | CrewAI | 96.42 | 1.33 | 98.67 | 0.74% | Menor tasa de fallos y máxima reproducibilidad |
| 2 | OpenAI Agents | 99.84 | 2.00 | 99.33 | 1.42% | Mejor evidencia y cobertura; fallos algo mayores |
| 3 | LangGraph | 100.00 | 22.67 | 86.67 | 2.62% | Evidencia perfecta pero fallos y cobertura penalizan |

> Empate funcional CrewAI/OpenAI: si la auditoría pondera más la **trazabilidad de
> evidencia y la cobertura**, OpenAI Agents lidera; si pondera más la **fiabilidad
> operativa (fallos) y la reproducibilidad**, CrewAI lidera.

**Escenario C — Calidad máxima** (prioriza calidad humana, completitud, simK)

| Puesto | Opción | calidad humana | completitud | simK | Justificación |
|---|---|---|---|---|---|
| 1 | CrewAI | 4.388 | 4.562 | 41.98 | Media humana y completitud más altas entre frameworks |
| 2 | OpenAI Agents | 4.225 | 4.438 | 40.43 | Segundo en calidad humana y completitud |
| 3 | LangGraph | 4.150 | 4.250 | 41.02 | Menor calidad humana global |

> Caveat estadístico: las diferencias de calidad humana **no son significativas**
> (§8.4). Para "calidad máxima" estricta, ningún framework supera al baseline de un
> solo prompt de forma concluyente.

---

# SECCIÓN 10 — CONCLUSIONES

## 10.1 Respuesta a las subpreguntas (SP1–SP5)

> Subpreguntas **inferidas del diseño experimental** — reemplazar por el enunciado
> literal de la tesis conservando los datos.

**SP1 (inferida) — ¿Difieren los frameworks en la calidad de los artículos generados?**
No de forma estadísticamente significativa. Friedman no significativo en las 5
dimensiones (p = 0.082–0.545; W = 0.044–0.139). KCS 100% y evidencia 96.4–100% en
todos. Medias humanas: CrewAI 4.388 > OpenAI 4.225 > LangGraph 4.150 = Baseline
4.150, pero las diferencias caen dentro del ruido.

**SP2 (inferida) — ¿Cuál es el costo de eficiencia de cada framework?**
Sustancial y muy dispar. Costo mediano por run: LangGraph $28.10, OpenAI $27.17,
CrewAI $27.06, frente a $0.92 del baseline-prompt. Tool calls: LangGraph 1963.67,
OpenAI 1206.00, CrewAI 687.33, baseline 0. Latencia por run: 4.1–4.8 h en
frameworks vs 13.8 min en baseline.

**SP3 (inferida) — ¿Difieren en fiabilidad / tasa de fallos?**
Sí, marcadamente. Tasa de fallos (errores/lotes): LangGraph 22.67% vs CrewAI
1.33% y OpenAI 2.00%. A nivel de run, los 3 completaron (0% abortos).

**SP4 (inferida) — ¿Son reproducibles los resultados (variabilidad inter-run)?**
Sí, con diferencias. CV medio inter-run sobre costo/tools/artículos: CrewAI 0.74%,
OpenAI 1.42%, LangGraph 2.62%. CrewAI es el más reproducible.

**SP5 (inferida) — ¿Se sostienen los patrones fuera de la muestra principal?**
Sí. En el split de reserva (37 int., 1 run) los rankings se mantienen en las
métricas con separación real (8/8 robustos con umbral 5%); los cambios ocurren
sólo entre valores casi empatados.

## 10.2 Tabla resumen de trade-offs por framework

| Framework | Calidad humana | Cobertura | Evidencia | Costo | Latencia | Tool calls | Fiabilidad (fallos) | Reproducibilidad | LOC |
|---|---|---|---|---|---|---|---|---|---|
| LangGraph | 4.150 (=) | 86.67 (–) | 100.00 (+) | 28.10 (–) | 4.83 h (–) | 1963.67 (–) | 22.67% (–) | 2.62% (–) | 831 |
| CrewAI | 4.388 (+) | 98.67 (+) | 96.42 (≈) | 27.06 (≈) | 4.37 h (≈) | 687.33 (+) | 1.33% (+) | 0.74% (+) | 932 (–) |
| OpenAI Agents | 4.225 (+) | 99.33 (+) | 99.84 (+) | 27.17 (≈) | 4.13 h (+) | 1206.00 (≈) | 2.00% (+) | 1.42% (≈) | 803 |
| Baseline (prompt) | 4.150 (=) | 100.00 (+) | 100.00 (+) | 0.92 (+) | 13.8 min (+) | 0 (+) | n/a | — | 340 (+) |

Leyenda: (+) ventaja, (≈) intermedio, (–) desventaja, (=) sin diferencia
significativa. La calidad humana no difiere significativamente entre generadores.

## 10.3 Checklist de selección de framework (basado en evidencia)

- [ ] **¿La calidad percibida es el factor decisivo?** → Los datos **no**
  distinguen a los frameworks del baseline de un solo prompt (Friedman n.s.).
  Si la calidad es lo único que importa, **empieza por el baseline-prompt**
  (costo $0.92, 0 tool calls) antes de adoptar un framework.
- [ ] **¿Necesitas agrupación/consolidación autónoma de interacciones?** → Sí lo
  hacen los frameworks (52–57 artículos sobre 50 inputs con alta cobertura); el
  baseline genera 1:1.
- [ ] **¿La fiabilidad operativa es crítica (mínimos fallos)?** → **CrewAI**
  (1.33%) u **OpenAI** (2.00%). **Evita LangGraph** (22.67%) sin endurecer su
  manejo de errores.
- [ ] **¿Necesitas reproducibilidad entre corridas?** → **CrewAI** (CV 0.74%) es
  el más estable; LangGraph el más variable (2.62%).
- [ ] **¿Presupuesto/latencia ajustados?** → Todos los frameworks cuestan ~$27/run
  y tardan ~4–5 h; si eso no cabe, **baseline-prompt** ($0.92, 14 min).
- [ ] **¿Máxima trazabilidad de evidencia y cobertura?** → **OpenAI Agents**
  (evidencia 99.84%, cobertura 99.33%).
- [ ] **¿Costo de mantenimiento (LOC)?** → baseline 340 < OpenAI 803 < LangGraph
  831 < CrewAI 932.

---

## Fuentes de los datos

| Dato | Archivo |
|---|---|
| Dataset descriptivo | `data/processed/interactions.jsonl`, `data/splits/splits.yaml` |
| Resultados/ingeniería (principal) | `eval/results/main_metrics.json` |
| Resultados (reserva) | `eval/results/reserve_metrics.json` |
| Friedman, descriptivo humano, hipótesis, correlaciones, CV | `eval/analysis/statistical_tests.json` |
| Tasa de fallos / inter-run | `runs/experiment/<framework>/experiment_summary.json` |
| Robustez (estabilidad de patrones) | `eval/results/EXECUTIVE_SUMMARY.md` |

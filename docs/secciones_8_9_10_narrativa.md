# Secciones 8, 9 y 10 — Redacción para integrar al documento

> Versión narrativa generada con Claude Code a partir de `docs/datos_para_tesis.md`,
> `eval/analysis/statistical_tests.json` (bloque `hypotheses`),
> `eval/results/EXECUTIVE_SUMMARY.md` y `docs/proceso_experimental.md`. Las cifras
> son las exactas de los archivos de resultados. Cuando un contraste no fue
> estadísticamente significativo, se indica de forma explícita.

---

# 8. Análisis de datos

## 8.1 Dataset final

El estudio se ejecutó sobre un corpus de 183 interacciones reales de WhatsApp
Business de Davivienda Colombia, acompañado de 118 artículos de base de
conocimiento que sirvieron como referencia (ground truth) y que **no** se
entregaron como insumo a los agentes. El corpus se particionó con semilla fija
(42) en tres conjuntos: calibración (37 interacciones), evaluación (109) y reserva
(37). El estudio principal se realizó sobre un subconjunto estratificado de 50
interacciones del split de evaluación, muestreado por la combinación
`product_category × severity × query_type` para preservar la composición del
corpus.

La distribución del corpus fue equilibrada entre las seis categorías de producto,
sin que ninguna dominara: cuentas (34; 18.58 %), créditos (32; 17.49 %),
transferencias (31; 16.94 %), otros (30; 16.39 %), tarjetas (29; 15.85 %) y
canales digitales (27; 14.75 %). Por severidad predominaron los casos operativos
(89; 48.63 %) sobre los informativos (63; 34.43 %) y los críticos (31; 16.94 %).
Por tipo de consulta, el corpus repartió de forma pareja entre política (51;
27.87 %), troubleshooting (47; 25.68 %), how-to (44; 24.04 %) y FAQ (41; 22.40 %).

Las conversaciones fueron cortas y homogéneas en extensión: promediaron 7.74 turnos
(mediana 8; rango 7–10; desviación estándar 0.53), lo que indica interacciones de
servicio acotadas y comparables entre sí.

| Dimensión | Categorías (n) |
|---|---|
| Producto | cuentas 34 · créditos 32 · transferencias 31 · otros 30 · tarjetas 29 · canales_digitales 27 |
| Severidad | operativa 89 · informativa 63 · crítica 31 |
| Tipo de consulta | política 51 · troubleshooting 47 · howto 44 · faq 41 |
| Turnos | media 7.74 · mediana 8 · sd 0.53 · rango [7, 10] |

## 8.2 Generación de artículos

Cada framework recibió las 50 interacciones y decidió de forma autónoma cómo
agruparlas y cuántos artículos producir. La tabla siguiente resume los promedios
de tres corridas por generador.

| Framework | Artículos (prom.) | Cobertura % | KCS % | Evidencia % |
|---|---|---|---|---|
| LangGraph | 52.67 | 86.67 | 100.00 | 100.00 |
| CrewAI | 52.33 | 98.67 | 100.00 | 96.42 |
| OpenAI Agents | 57.00 | 99.33 | 100.00 | 99.84 |
| Baseline (prompt) | 50.00 | 100.00 | 100.00 | 100.00 |
| Baseline (heurístico) | 50.00 | 100.00 | 100.00 | 100.00 |

Los tres frameworks consolidaron y dividieron interacciones, por lo que generaron
entre 52 y 57 artículos a partir de 50 entradas; los baselines produjeron uno por
interacción. Todos los generadores alcanzaron 100 % de cumplimiento de la plantilla
KCS. La cobertura de interacciones varió: OpenAI Agents (99.33 %) y CrewAI
(98.67 %) cubrieron casi todo el insumo, mientras que LangGraph quedó por debajo
(86.67 %). La cobertura de evidencia fue alta en todos (96.42–100 %).

## 8.3 Evaluación humana

Un evaluador puntuó, de forma ciega y comparativa, 16 interacciones presentadas en
cuatro versiones cada una (LangGraph, CrewAI, OpenAI y baseline de prompt), para un
total de 64 artículos, sobre cinco dimensiones en escala 1–5: claridad, exactitud,
completitud, aplicabilidad y consistencia. El orden A/B/C/D se aleatorizó por
interacción para preservar el cegado.

Por media global, CrewAI obtuvo la puntuación más alta (4.388), seguido de OpenAI
(4.225) y de LangGraph y el baseline, empatados (4.150). No obstante, **estas
diferencias no fueron estadísticamente significativas**. Se aplicó la prueba de
Friedman (diseño de bloques repetidos, con la interacción como bloque) a cada
dimensión, y en ninguna se rechazó la hipótesis nula (α = 0.05):

| Dimensión | χ² | p | Significativo | W de Kendall |
|---|---|---|---|---|
| Claridad | 2.400 | 0.4936 | No | 0.050 |
| Exactitud | 2.133 | 0.5454 | No | 0.044 |
| Completitud | 6.692 | 0.0824 | No | 0.139 |
| Aplicabilidad | 4.200 | 0.2407 | No | 0.088 |
| Consistencia | 6.103 | 0.1067 | No | 0.127 |

Los valores de W de Kendall (0.044–0.139) indican además un acuerdo entre bloques
muy débil a débil: el ordenamiento de los generadores no fue consistente entre
interacciones. Las dimensiones que más se aproximaron a la significancia fueron
completitud (p = 0.0824) y consistencia (p = 0.1067), ambas a favor de CrewAI
(completitud 4.562; consistencia 4.375), pero sin alcanzar el umbral. La
interpretación es directa: con la muestra evaluada, **la calidad percibida de los
cuatro generadores fue estadísticamente indistinguible**, incluido el baseline de
un solo prompt.

| Framework | Claridad | Exactitud | Completitud | Aplicabilidad | Consistencia | Global |
|---|---|---|---|---|---|---|
| LangGraph | 4.125 | 4.188 | 4.250 | 4.125 | 4.062 | 4.150 |
| CrewAI | 4.312 | 4.375 | 4.562 | 4.312 | 4.375 | 4.388 |
| OpenAI | 4.188 | 4.312 | 4.438 | 4.062 | 4.125 | 4.225 |
| Baseline | 4.125 | 4.188 | 4.125 | 4.188 | 4.125 | 4.150 |

## 8.4 Métricas de ingeniería

Donde los generadores sí divergieron de forma marcada fue en el costo de
producción. La tabla resume las métricas operacionales por corrida.

| Framework | Latencia (s/run) | Costo $/run | Tokens in/run | Tokens out/run | Tool calls | Tasa fallos % | LOC |
|---|---|---|---|---|---|---|---|
| LangGraph | 17 397.96 | 28.0977 | 2 384 562 | 1 108 248 | 1963.67 | 22.67 | 831 |
| CrewAI | 15 742.24 | 27.0596 | 4 483 801 | 916 115 | 687.33 | 1.33 | 932 |
| OpenAI Agents | 14 863.23 | 27.1687 | 4 314 953 | 958 126 | 1206.00 | 2.00 | 803 |
| Baseline (prompt) | 826.65 | 0.9170 | 80 336 | 44 901 | 0.00 | n/a | 340 |
| Baseline (heurístico) | 116.74 | 0.0000 | — | — | 0.00 | n/a | 282 |

Los tres frameworks costaron alrededor de 27 USD por corrida y tardaron entre 4.1 y
4.8 horas en procesar las 50 interacciones, frente a los 0.92 USD y ~14 minutos del
baseline de prompt, que igualó la calidad percibida. La tasa de fallos —medida como
errores sobre el total de lotes (150 = 3 corridas × 50 interacciones)— separó
nítidamente a los frameworks: CrewAI 1.33 % (2/150), OpenAI 2.00 % (3/150) y
LangGraph 22.67 % (34/150). A nivel de corrida completa, los tres terminaron sin
abortar (0 % de corridas fallidas). Los modos de fallo predominantes difirieron por
framework y se discuten en la Sección 9.

## 8.5 Validación de robustez

Para comprobar que los hallazgos no dependían de la muestra principal, se replicó
el experimento sobre el split de reserva (37 interacciones, una corrida por
framework). La tabla compara ambos escenarios.

| Framework | Escenario | Artículos | Cobertura % | Evidencia % | Costo $ | Tool calls | Fallos % |
|---|---|---|---|---|---|---|---|
| LangGraph | principal | 52.67 | 86.67 | 100.00 | 28.10 | 1963.67 | 22.67 |
| LangGraph | reserva | 40.00 | 91.89 | 100.00 | 17.29 | 1207.00 | 0.00 |
| CrewAI | principal | 52.33 | 98.67 | 96.42 | 27.06 | 687.33 | 1.33 |
| CrewAI | reserva | 37.00 | 100.00 | 97.70 | 18.83 | 491.00 | 0.00 |
| OpenAI | principal | 57.00 | 99.33 | 99.84 | 27.17 | 1206.00 | 2.00 |
| OpenAI | reserva | 42.00 | 97.30 | 100.00 | 21.34 | 956.00 | 0.00 |

Aplicando un criterio de cambio real solo cuando la diferencia entre frameworks
supera el 5 % relativo en ambos splits, los ordenamientos se mantuvieron en todas
las métricas con separación efectiva (cumplimiento KCS, evidencia, tool calls,
tasa de fallos): **7 de 7 rankings se conservaron**. Los cambios de orden en
costo y cobertura ocurrieron entre valores casi empatados (dentro de ±5 %) y se
interpretan como ruido. Cabe una salvedad metodológica: la reserva se ejecutó con
una sola corrida por framework (frente a tres en el principal), por lo que su
varianza es mayor y la comparación es indicativa, no concluyente. Aun así, ningún
patrón del estudio principal se invirtió en la reserva.

---

# 9. Discusión de resultados

## 9.1 Discusión por hipótesis

**H1 — "LangGraph tendrá menor tasa de fallos." Refutada.** El resultado fue el
opuesto al previsto: LangGraph registró la tasa de fallos más alta (22.67 %),
mientras que CrewAI (1.33 %) y OpenAI Agents (2.00 %) se mantuvieron un orden de
magnitud por debajo. La hipótesis no solo no se sostuvo, sino que se invirtió de
forma clara.

**H2 — "CrewAI tendrá mayor calidad percibida en claridad y aplicabilidad."
Parcialmente soportada.** CrewAI obtuvo, en efecto, la media más alta entre los
tres frameworks tanto en claridad (4.312) como en aplicabilidad (4.312). Sin
embargo, la prueba de Friedman restringida a los tres frameworks no fue
significativa en ninguna de las dos dimensiones (claridad p = 0.3679;
aplicabilidad p = 0.1561). La dirección coincidió con lo previsto, pero la
evidencia estadística fue insuficiente para confirmarla.

**H3 — "Mejor instrumentación implica mejor reproducibilidad." Evaluada
parcialmente.** Medida la reproducibilidad como el coeficiente de variación
inter-corrida sobre costo, tool calls y artículos, CrewAI fue el más estable
(CV medio 0.74 %), seguido de OpenAI (1.42 %) y LangGraph (2.62 %). El dato es
consistente con la hipótesis en la parte observable (CrewAI reprodujo sus
resultados con menor dispersión), pero la "instrumentación" no se manipuló como
variable independiente, de modo que la relación es observacional y no causal.

**H4 — "La evidencia obligatoria mejora la exactitud." No evaluada.** Contrastar
esta hipótesis requería la ablación `no_evidence` —generar sin evidencia
obligatoria y comparar exactitud—, que no se ejecutó en esta batería. El flag
existe en el orquestador pero su efecto sobre el comportamiento del runner no está
implementado, por lo que H4 queda como trabajo futuro (ver 9.5 y Sección 10).

| Hipótesis | Veredicto | Dato decisivo |
|---|---|---|
| H1 | Refutada | Fallos: LangGraph 22.67 % vs CrewAI 1.33 %, OpenAI 2.00 % |
| H2 | Parcialmente soportada | CrewAI mayor media, pero Friedman 3-fw no significativo (p = 0.37 / 0.16) |
| H3 | Evaluada (parcial) | CV inter-run: CrewAI 0.74 % < OpenAI 1.42 % < LangGraph 2.62 % |
| H4 | No evaluada | Ablación `no_evidence` no ejecutada |

## 9.2 Interpretación ingenieril

La diferencia más relevante entre frameworks no estuvo en la calidad del producto
—indistinguible— sino en cómo cada orquestación gestionó su lazo de verificación.
LangGraph ejecutó 145 ciclos de revisión en tres corridas y, aun así, acumuló 34
fallos cuyo modo dominante fue `max_revisions_or_unapproved` (12 casos): el crítico
y el generador entraron en ciclos de rechazo que agotaron el presupuesto de
revisiones sin converger en una aprobación, agravados por errores no manejados (7)
y cortes de presupuesto (5). OpenAI Agents, en el extremo opuesto, convergió con
apenas 26 ciclos de revisión y sus pocos fallos (3) fueron timeouts en
interacciones largas, no rechazos del verificador. CrewAI iteró más que ninguno
(166 ciclos) pero de forma estable: casi no falló (2 casos) y reprodujo sus
métricas con la menor dispersión.

El patrón sugiere que el cuello de botella de confiabilidad no fue el modelo
—idéntico para los tres— sino el **diseño del lazo crítico↔generador**. Una
orquestación que converge en pocas pasadas (OpenAI) o que itera de forma controlada
(CrewAI) resultó más fiable que una que reintenta agresivamente sin criterio de
parada robusto (LangGraph). Este es un resultado de ingeniería de orquestación, no
de capacidad del modelo.

## 9.3 Implicaciones de diseño

De los resultados se desprenden recomendaciones por módulo del pipeline:

- **Agrupación (analyzer).** La consolidación autónoma funcionó: los frameworks
  produjeron 52–57 artículos sobre 50 entradas con cobertura alta. Para casos de
  uso 1:1 sin necesidad de agrupar, el baseline de prompt fue suficiente.
- **Verificación (critic).** El lazo de verificación debe tener un criterio de
  parada explícito y un umbral de aprobación calibrado. El ajuste del crítico
  durante la calibración (umbral de exactitud 4→3 y definición estricta de
  *blocking issue*) redujo rechazos espurios; aun así, LangGraph mostró que un
  lazo mal acotado degrada la confiabilidad sin mejorar la calidad.
- **Evidencia (evidence_pack).** La trazabilidad afirmación→fuente
  (`claim_evidence_map`) se cumplió en 96.42–100 % de los casos y es un activo de
  auditoría barato de exigir; conviene mantenerla obligatoria.
- **Presupuesto.** El corte por costo y el watchdog de tiempo fueron necesarios:
  evitaron corridas descontroladas y aislaron los timeouts de OpenAI sin tumbar
  toda la batería.

## 9.4 Implicaciones de adopción

Como la calidad percibida no distinguió a los generadores, la elección debe guiarse
por las métricas operacionales y por el escenario organizacional:

- **Prototipado rápido.** El baseline de un solo prompt domina: igual calidad a
  ~1/30 del costo (0.92 USD vs ~27 USD por corrida), 14 minutos y 340 LOC. Adoptar
  un framework solo se justifica si se requiere agrupación autónoma.
- **Producción auditada.** CrewAI lidera por fiabilidad (1.33 % de fallos) y
  reproducibilidad (CV 0.74 %); OpenAI es la alternativa si se prioriza la
  trazabilidad de evidencia (99.84 %) y la cobertura (99.33 %). LangGraph queda
  desaconsejado sin endurecer su manejo de errores (22.67 % de fallos).
- **Calidad máxima.** CrewAI presentó las medias humanas más altas, pero **sin
  diferencia estadísticamente significativa**; no hay base para afirmar que algún
  framework supere al baseline en calidad.

## 9.5 Gobernanza y seguridad

El pipeline incorporó controles de gobernanza por diseño. Un agente de gobernanza
(Final Editor) actuó como último paso antes de la revisión humana: verificó que
cada afirmación verificable estuviera mapeada en el `evidence_pack`, revalidó la
plantilla KCS y ejecutó un barrido de información personal identificable (PII) sobre
cada campo de texto mediante la herramienta `check_pii`, conforme a
`configs/policies/pii_policy.yaml`. La política de estados
(`configs/policies/governance_policy.yaml`) reservó la transición a `approved` para
un revisor humano; el agente solo podía promover de `draft` a `in_review` cuando se
cumplían las precondiciones (validación correcta, cero hallazgos de PII y
evidence_pack completo).

Dos salvedades de seguridad son relevantes para la interpretación. Primera: la
batería se ejecutó en modo `--auto-approve`, es decir, sin un humano efectivamente
en el bucle; el control de gobernanza se instrumentó y midió, pero la aprobación
final humana se simuló. Segunda: la herramienta de detección de PII enmascara datos
sensibles en origen (por ejemplo, nombres de cliente), y el corpus no expuso PII en
los artículos generados, lo que es coherente con un diseño que nunca entrega datos
crudos al redactor. La obligatoriedad de la evidencia (H4), que reforzaría la
exactitud y la auditabilidad, no llegó a probarse y constituye la principal deuda de
gobernanza del estudio.

## 9.6 Comparación con trabajos relacionados

El hallazgo central —que tres frameworks de orquestación multiagente no
produjeron artículos de mayor calidad percibida que un único prompt bien diseñado,
a un costo entre 25 y 30 veces mayor— matiza la expectativa habitual de que la
orquestación multiagente mejora la calidad del resultado. En la tarea estudiada
(generación de artículos KCS a partir de interacciones acotadas, con un mismo
modelo base de control), el valor diferencial de los frameworks no se manifestó en
la calidad del texto sino en capacidades de proceso: agrupación autónoma,
trazabilidad de evidencia y fiabilidad operativa. Esta lectura es consistente con la
observación, recurrente en la literatura de sistemas multiagente, de que sus
beneficios tienden a concentrarse en tareas con descomposición compleja, mientras
que en tareas acotadas el sobrecosto de coordinación puede no compensar.

> Nota: la contrastación formal con la literatura (autores, métricas y cifras
> específicas) debe completarse desde el marco teórico de la tesis; aquí se
> posiciona el resultado de forma conceptual sin atribuir cifras a fuentes externas.

---

# 10. Conclusiones

## 10.1 Respuesta a la pregunta principal y a las subpreguntas

La pregunta principal —qué framework de orquestación de agentes es más adecuado
para generar artículos de base de conocimiento a partir de interacciones de
servicio al cliente, manteniendo el modelo como variable de control— admite una
respuesta matizada: **ningún framework produjo artículos de mayor calidad de forma
estadísticamente significativa, de modo que la decisión se traslada del eje de
calidad al de eficiencia y confiabilidad.** Bajo ese criterio, CrewAI ofreció el
mejor balance (máxima fiabilidad y reproducibilidad, calidad en el tope de la banda
no significativa), mientras que el baseline de un solo prompt resultó la opción más
eficiente cuando no se requiere agrupación autónoma.

- **SP1 — Calidad por rúbrica y dónde se concentran las diferencias.** Por media,
  CrewAI fue el mejor (global 4.388), pero ninguna dimensión alcanzó significancia
  en Friedman (p = 0.082–0.545). Las diferencias, no significativas, se concentraron
  en completitud (p = 0.0824) y consistencia (p = 0.1067), a favor de CrewAI.
- **SP2 — Menor tasa de fallos y modos predominantes.** CrewAI tuvo la menor tasa
  (1.33 %), seguido de OpenAI (2.00 %) y LangGraph (22.67 %). Modos predominantes:
  LangGraph, agotamiento del lazo de verificación (`max_revisions_or_unapproved`),
  errores no manejados y cortes de presupuesto; OpenAI, timeouts en interacciones
  largas; CrewAI, casi nulos.
- **SP3 — Menor intervención correctiva.** Sin humano en el bucle (auto-approve),
  se usaron proxies: por reproceso potencial (tasa de fallos), CrewAI y OpenAI
  demandarían la menor intervención; por convergencia del lazo, OpenAI necesitó
  muchas menos iteraciones de revisión (26 vs 145 de LangGraph y 166 de CrewAI). La
  intervención humana correctiva real no se instrumentó.
- **SP4 — Métricas operacionales y trade-offs.** Los frameworks costaron ~27 USD y
  4–5 h por corrida frente a 0.92 USD y ~14 min del baseline. No emergió un
  trade-off favorable a la mayor orquestación: más costo, tokens, tool calls e
  iteraciones **no** se tradujeron en más calidad medible.
- **SP5 — Efecto de las ablaciones.** No evaluable con los datos actuales: las
  ablaciones (sin verificador, sin memoria, sin evidencia obligatoria; el contraste
  con/sin RAG no aplica al diseño B sin KB previa) no se ejecutaron. Queda como
  trabajo futuro.

## 10.2 Contribuciones del trabajo

1. Un diseño experimental controlado que aísla el framework de orquestación como
   única variable independiente, con modelo, prompts, presupuesto y datos idénticos.
2. Evidencia empírica de que, en generación de KB sobre interacciones acotadas,
   la orquestación multiagente no aportó calidad percibida medible sobre un único
   prompt, a un costo sustancialmente mayor.
3. Una caracterización de los modos de fallo y de la reproducibilidad por
   framework, útil para decisiones de adopción.
4. Un pipeline reproducible (datos → corridas → métricas automáticas → evaluación
   humana → análisis estadístico) con validación de robustez en un split reservado.

## 10.3 Recomendaciones prácticas

- [ ] **¿La calidad es el único criterio?** Los datos no distinguen frameworks del
  baseline; **empezar por el baseline de prompt** antes de adoptar orquestación.
- [ ] **¿Se requiere agrupación/consolidación autónoma?** Sí la aportan los
  frameworks (52–57 artículos sobre 50 entradas, alta cobertura); el baseline es 1:1.
- [ ] **¿La fiabilidad es crítica?** Elegir CrewAI (1.33 %) u OpenAI (2.00 %);
  evitar LangGraph (22.67 %) sin endurecer su manejo de errores.
- [ ] **¿Importa la reproducibilidad?** CrewAI (CV 0.74 %) es el más estable.
- [ ] **¿Máxima trazabilidad de evidencia y cobertura?** OpenAI Agents (99.84 % /
  99.33 %).
- [ ] **¿Presupuesto/latencia ajustados?** Si ~27 USD y 4–5 h por corrida no caben,
  usar el baseline (0.92 USD, ~14 min).
- [ ] **¿Costo de mantenimiento?** Menor LOC: baseline 340 < OpenAI 803 < LangGraph
  831 < CrewAI 932.

## 10.4 Cierre

El experimento mostró que, para la tarea estudiada, la elección de framework de
orquestación no determinó la calidad del artículo —indistinguible entre las cuatro
alternativas— sino su costo de producción y su confiabilidad operativa. La
contribución práctica es invertir el criterio de selección habitual: en lugar de
adoptar el framework "más capaz", conviene partir de la línea base más simple y
escalar a una orquestación solo cuando se necesiten sus capacidades de proceso
—agrupación autónoma, trazabilidad y fiabilidad—, eligiendo entonces el framework
por su perfil operacional y no por una ventaja de calidad que, en esta evidencia, no
se observó. Las limitaciones principales —evaluación humana de un solo evaluador,
una sola corrida en reserva y la ausencia de las ablaciones (SP5/H4)— delimitan el
trabajo futuro inmediato.

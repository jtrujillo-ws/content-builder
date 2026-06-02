# ADR 0001 — Formato del artículo según el tipo de consulta

**Estado:** propuesta
**Pista:** aplicación real

## Contexto

La evaluación humana del trabajo de grado reveló que los cuatro generadores
producen artículos con formato how-to (listas de pasos) **incluso cuando la
pregunta requiere una respuesta directa o una comparación**. La causa es de
diseño: en la tesis se usó un **único prompt de generación para todos los
frameworks** para mantener la paridad experimental (que las diferencias de calidad
fueran atribuibles al framework, no al prompt).

En la tesis ese sesgo era aceptable porque se distribuía parejo entre frameworks y
no afectaba la comparación. Pero **degrada la validez externa**: los artículos no
son óptimos para FAQ, comparación ni política, y los puntajes de calidad podrían
ser más altos con un formato apropiado por tipo.

En la aplicación real **ya no hay paridad que respetar** —no estamos comparando
frameworks, queremos el mejor artículo posible—, así que la restricción desaparece.

## Decisión

Diferenciar el formato del cuerpo del artículo **por tipo de consulta**
(`article_type`: faq, howto, troubleshooting, politica, comparacion), no por
framework. La clasificación se hace por el contenido de la pregunta (usando la
etiqueta `query_type` solo como pista). El formato:

- **faq / politica** → respuesta directa (texto), con condiciones/excepciones en viñetas.
- **howto / troubleshooting** → pasos numerados (troubleshooting además con causa raíz + verificación).
- **comparacion** → tabla comparativa + "cuándo usar cada una".

Implementación en [`../01-prompts/system_generator.md`](../01-prompts/system_generator.md).

## Por qué no rompe lo aprendido en la tesis

Diferenciar por *tipo de consulta* es una función del **input**, no del framework.
La conclusión central de la tesis (los generadores son indistinguibles en calidad)
no cambia; lo que mejora es el formato absoluto y la cobertura de tipos de consulta.

## Alternativas consideradas

- **Mantener el prompt único how-to.** Descartada: arrastra el sesgo a producción.
- **Un prompt distinto por framework.** No aplica fuera de la tesis y, dentro, habría roto la paridad.
- **Plantilla rígida por tipo (hard-routing por `query_type`).** Riesgosa si la etiqueta viene ruidosa; se prefiere que el agente infiera el tipo.

## Consecuencias

- Cambia el `output_schema`: nuevo `article_type`, `resolution` adaptable, flags en `metadata`.
- Requiere una métrica de "adecuación de formato" para verificar la clasificación en operación.
- Pendiente: validar el prompt adaptativo en un set de calibración que cubra todos los tipos antes de generalizar.

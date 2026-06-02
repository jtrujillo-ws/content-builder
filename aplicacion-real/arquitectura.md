# Arquitectura del proceso real

> Esqueleto inicial. Se irá completando con la discusión.

Flujo end-to-end de la KB en operación (no el experimento). Pendiente de detallar
cada etapa.

## Etapas (borrador)

1. **Ingestión** — de dónde llegan las interacciones reales (¿WhatsApp Business
   en vivo? ¿exportes batch?), con qué frecuencia, y cómo se etiqueta `query_type`
   y `product_category` en producción (¿clasificador, reglas, manual?).
2. **Agrupación / detección de temas** — consolidar interacciones del mismo
   problema; deduplicar contra artículos ya publicados (aquí sí habría una KB
   preexistente que consultar, a diferencia de la tesis).
3. **Generación** — artículo adaptado por tipo de consulta (ver `01-prompts/`).
4. **Verificación** — validación KCS, evidencia, PII.
5. **Gobernanza y revisión humana** — aprobación; bloqueo para temas regulados
   (ver `riesgos-y-gobernanza.md`).
6. **Publicación y mantenimiento** — dónde vive la KB; reciclaje de contenido
   `volatile`; métricas de uso y de calidad continua.

## Preguntas abiertas

- ¿Qué framework de orquestación se adopta en producción? (la tesis sugiere que la
  calidad no los distingue, así que la decisión se basa en fiabilidad/costo/operación).
- ¿La KB preexistente se usa como contexto (RAG) para evitar duplicados y mejorar consistencia?
- ¿Cómo se mide calidad en operación sin un evaluador humano por artículo?

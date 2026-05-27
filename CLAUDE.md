# Content Builder — Contexto del proyecto

## Qué es
Comparación empírica de 3 frameworks de agentes autónomos en Python (LangGraph, CrewAI, OpenAI Agents SDK) para generación de contenido en bases de conocimiento empresariales. Caso de estudio: Davivienda Colombia, interacciones de WhatsApp Business.

## Diseño experimental (Opción B)
Los frameworks reciben interacciones de servicio al cliente como input y generan artículos de KB como output, desde cero. No hay KB preexistente que consultar. Cada framework decide autónomamente si agrupa interacciones similares o genera artículo por artículo.

## Modelo LLM base (variable de control)
Claude (Anthropic) — claude-sonnet-4-20250514. Mismo modelo para los 3 frameworks. La única variable que cambia es el framework de orquestación.

## Dataset
- data/processed/interactions.jsonl — 183 interacciones WhatsApp Davivienda
- data/processed/kb_articles.jsonl — 118 artículos de referencia (ground truth, NO input del agente)
- data/splits/splits.yaml — calibración 37, evaluación 109, reserva 37

## Tool contract (src/tools/)
6 herramientas compartidas como funciones Python puras:
1. search_interactions(query, k) — búsqueda semántica
2. get_interaction(interaction_id) — leer interacción completa
3. extract_knowledge(interaction_ids) — extraer hechos documentables
4. validate_article(article_json) — validar contra plantilla KCS
5. check_pii(text) — detectar datos personales
6. list_interactions(filters) — inventario con filtros

## Plantilla KCS (output obligatorio)
Todo artículo: title, environment, problem, cause, resolution, evidence_pack, metadata

## Restricciones técnicas
- Python 3.11 (migrado desde 3.9 porque crewai moderno requiere ≥ 3.10).
  Mantener convención `Optional[X]` / `List[X]` por consistencia.
- API key en .env (ANTHROPIC_API_KEY)
- Presupuesto: timeout 300s, máx 50 tool calls, máx $2 USD por ejecución
- Temperature: 0.3, max_tokens: 4096

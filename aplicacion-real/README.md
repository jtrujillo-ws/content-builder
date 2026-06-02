# Aplicación real

Pista de **ingeniería del proceso real** de base de conocimiento de Davivienda,
a partir de los hallazgos del trabajo de grado. Aquí se diseña cómo llevar el
prototipo experimental a una operación real: prompts de producción, arquitectura,
decisiones y gobernanza.

**Estado:** diseño activo (en construcción; se va ampliando con cada discusión).

---

## Relación con el trabajo de grado

El trabajo de grado (comparación empírica de LangGraph, CrewAI y OpenAI Agents)
está **en cierre**. Sus artefactos siguen viviendo fuera de esta carpeta y no se
tocan salvo correcciones puntuales. Esta carpeta es independiente: parte de los
resultados de la tesis pero optimiza para **operación y validez externa**, no para
la comparación controlada.

### Cómo diferenciamos las dos pistas

| | Trabajo de grado (tesis) | Aplicación real |
|---|---|---|
| **Ubicación** | `docs/`, `eval/`, `runs/`, `configs/prompts/v1/`, `scripts/` del experimento | **todo bajo `aplicacion-real/`** |
| **Estado** | en cierre / congelado | diseño activo |
| **Objetivo** | comparar frameworks con rigor (validez interna) | construir el proceso real de KB (validez externa, operación) |
| **Restricción clave** | mismo prompt para todos los frameworks (paridad) | el mejor prompt posible por tipo de consulta (sin paridad que respetar) |
| **Prefijo de commit** | **`tesis:`** | **`aplicacion-real:`** |

**Regla práctica:** si el cambio afecta *cómo se corrió o se reportó el
experimento* → es tesis. Si es sobre *cómo operaría el proceso real* → va aquí.

> Convención de trabajo: al inicio de cada intercambio se deja explícito sobre qué
> pista estamos (tesis o aplicación real) para evitar ambigüedad. Cuando la tesis
> se entregue, marcaremos ese estado con un tag de git (p. ej. `trabajo-grado-final`)
> para dejar una línea limpia; a partir de ahí, el default es aplicación real.

---

## Índice

- [`01-prompts/`](01-prompts/) — prompts de producción (versión mejorada respecto a `configs/prompts/v1/`).
- [`decisiones/`](decisiones/) — registro de decisiones de diseño (ADR), una por archivo, con contexto y trade-off.
- [`arquitectura.md`](arquitectura.md) — flujo end-to-end del proceso real (ingestión → generación → gobernanza → publicación).
- [`riesgos-y-gobernanza.md`](riesgos-y-gobernanza.md) — temas regulados, PII, contenido volátil, escalamiento humano.

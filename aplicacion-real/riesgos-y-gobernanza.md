# Riesgos y gobernanza

> Esqueleto inicial. Se irá completando con la discusión.

## Temas regulados (bloqueo de publicación)

Para créditos, seguros, inversiones y manejo de datos personales, el costo de un
error es regulatorio, no estético. Propuesta: `needs_human_review = true` debe
**bloquear** la publicación automática (no solo informar) y enrutar a un revisor.

- Pendiente: lista explícita de productos/temas que disparan bloqueo.
- Pendiente: disclaimer estándar por familia de producto.

## PII

`check_pii` enmascara en origen, pero quedan menciones inline (nombres en el cuerpo
del mensaje). Definir si la KB de producción exige un barrido adicional sobre el
texto final y qué hacer ante un hallazgo (rechazar vs reescribir).

## Contenido volátil

Tasas, plazos, horarios y campañas caducan. `metadata.volatile = true` debe
alimentar un ciclo de revisión programada para que la KB no quede desactualizada.

- Pendiente: política de caducidad/recordatorio por tipo de dato.

## No inventar / escalar

Si la evidencia no respalda una respuesta, el artículo debe declararlo
(`confidence: low`) y escalar a humano en vez de rellenar. Definir el umbral y el
flujo de escalamiento.

## Trazabilidad

Mantener `evidence_pack.claim_evidence_map` obligatorio: cada afirmación auditable
a su interacción fuente. Es barato de exigir y clave para auditoría regulatoria.

# Ejemplo — Baseline heurístico

Dos artículos generados por el **baseline heurístico** (`runs/experiment/baseline_heuristic/run_1`), uno de categoría *cuentas* y otro de *transferencias*, con todos los campos KCS. El baseline heurístico construye el artículo por reglas a partir de `knowledge_extracted` de la interacción, sin LLM ni tools; sirve como piso de comparación frente a los frameworks y el baseline de prompt único.

> El artículo de *cuentas* corresponde a `INT-2024-010`, la misma interacción del Anexo H, lo que permite comparar directamente la salida heurística con la de los tres frameworks.

---

## Cuentas — INT-2024-010  (`ART-001`)

**Título:** Cómo solicitar una certificación de Cuenta de Ahorro Nómina

**Environment:**

```json
{
  "product": "Cuenta de Ahorro Nómina",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, ¿cómo hago para solicitar una certificación de mi Cuenta de Ahorro Nómina para un trámite de visa? 🙏

**Causa:** None

**Resolución:**

- 1. La certificación se puede solicitar a través de la App Davivienda o en sucursales físicas.
- 2. El procedimiento en la app se realiza en el menú de 'Servicios' y luego 'Certificaciones'.
- 3. La certificación es gratuita y se envía al correo registrado del cliente.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-010"
  ],
  "key_fragments": [
    "La certificación se puede solicitar a través de la App Davivienda o en sucursales físicas.",
    "El procedimiento en la app se realiza en el menú de 'Servicios' y luego 'Certificaciones'.",
    "La certificación es gratuita y se envía al correo registrado del cliente."
  ],
  "claim_evidence_map": {
    "La certificación se puede solicitar a través de la App Davivienda o en sucursales físicas.": [
      "INT-2024-010"
    ],
    "El procedimiento en la app se realiza en el menú de 'Servicios' y luego 'Certificaciones'.": [
      "INT-2024-010"
    ],
    "La certificación es gratuita y se envía al correo registrado del cliente.": [
      "INT-2024-010"
    ]
  }
}
```

---

## Transferencias — INT-2024-074  (`ART-017`)

**Título:** Diferencias entre PSE y ACH y cuándo usar cada uno

**Environment:**

```json
{
  "product": "Transferencias internacionales",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, buenas tardes. Tengo una duda sobre cómo hacer transferencias internacionales con Davivienda. ¿Cuál es la diferencia entre PSE y ACH y cuándo debería usar cada uno? 🤔

**Causa:** None

**Resolución:**

- 1. PSE es usado para pagos en línea dentro de Colombia, no para transferencias internacionales.
- 2. ACH permite transferencias electrónicas nacionales e internacionales.
- 3. Para usar ACH en transferencias internacionales, se necesita el código SWIFT o IBAN del banco receptor.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-074"
  ],
  "key_fragments": [
    "PSE es usado para pagos en línea dentro de Colombia, no para transferencias internacionales.",
    "ACH permite transferencias electrónicas nacionales e internacionales.",
    "Para usar ACH en transferencias internacionales, se necesita el código SWIFT o IBAN del banco receptor."
  ],
  "claim_evidence_map": {
    "PSE es usado para pagos en línea dentro de Colombia, no para transferencias internacionales.": [
      "INT-2024-074"
    ],
    "ACH permite transferencias electrónicas nacionales e internacionales.": [
      "INT-2024-074"
    ],
    "Para usar ACH en transferencias internacionales, se necesita el código SWIFT o IBAN del banco receptor.": [
      "INT-2024-074"
    ]
  }
}
```

---

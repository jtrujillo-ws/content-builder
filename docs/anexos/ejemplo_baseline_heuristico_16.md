# Artículos del baseline heurístico — 16 interacciones de la evaluación humana

Los **16 artículos** generados por el baseline heurístico (`runs/experiment/baseline_heuristic/run_1`) para las mismas 16 interacciones evaluadas en la evaluación humana comparativa ciega. El orden coincide con el de la evaluación (hoja `key` del Excel) para facilitar la comparación lado a lado frente a LangGraph, CrewAI, OpenAI Agents y el baseline de prompt único.

---

## INT-2024-154

**Categoría de producto:** canales_digitales

**Título:** Proceso para abrir una cuenta DaviPlata para menores de edad.

**Environment:**

```json
{
  "product": "Vivi (asistente virtual IA)",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, me llamo Camilo. Quisiera saber si mi hijo de 15 años puede tener una cuenta DaviPlata con mi autorización. Gracias!

**Causa:** None

**Resolución:**

- 1. Los menores de edad pueden tener una cuenta DaviPlata a partir de los 14 años con autorización parental.
- 2. El proceso requiere la presencia del menor y su padre o tutor legal en una oficina de Davivienda.
- 3. Se necesita presentar documentos de identidad y un recibo de servicio público para verificar la dirección.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-154"
  ],
  "key_fragments": [
    "Los menores de edad pueden tener una cuenta DaviPlata a partir de los 14 años con autorización parental.",
    "El proceso requiere la presencia del menor y su padre o tutor legal en una oficina de Davivienda.",
    "Se necesita presentar documentos de identidad y un recibo de servicio público para verificar la dirección."
  ],
  "claim_evidence_map": {
    "Los menores de edad pueden tener una cuenta DaviPlata a partir de los 14 años con autorización parental.": [
      "INT-2024-154"
    ],
    "El proceso requiere la presencia del menor y su padre o tutor legal en una oficina de Davivienda.": [
      "INT-2024-154"
    ],
    "Se necesita presentar documentos de identidad y un recibo de servicio público para verificar la dirección.": [
      "INT-2024-154"
    ]
  }
}
```

---

## INT-2024-189

**Categoría de producto:** otros

**Título:** Obtención de extracto consolidado de productos Davivienda

**Environment:**

```json
{
  "product": "SOAT",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, ¿cómo puedo obtener un extracto consolidado de todos mis productos en Davivienda? Estoy interesado sobre todo en el SOAT.

**Causa:** None

**Resolución:**

- 1. El extracto consolidado se puede solicitar en la sucursal virtual o en una oficina.
- 2. Es necesario presentar la cédula de ciudadanía original en la oficina.
- 3. El extracto consolidado no tiene costo para el cliente.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-189"
  ],
  "key_fragments": [
    "El extracto consolidado se puede solicitar en la sucursal virtual o en una oficina.",
    "Es necesario presentar la cédula de ciudadanía original en la oficina.",
    "El extracto consolidado no tiene costo para el cliente."
  ],
  "claim_evidence_map": {
    "El extracto consolidado se puede solicitar en la sucursal virtual o en una oficina.": [
      "INT-2024-189"
    ],
    "Es necesario presentar la cédula de ciudadanía original en la oficina.": [
      "INT-2024-189"
    ],
    "El extracto consolidado no tiene costo para el cliente.": [
      "INT-2024-189"
    ]
  }
}
```

---

## INT-2024-024

**Categoría de producto:** cuentas

**Título:** Sobregiro en cuentas corrientes

**Environment:**

```json
{
  "product": "Cuenta Corriente con sobregiro",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, quiero saber las diferencias entre el sobregiro automático y el preaprobado de la cuenta corriente. ¿Cuáles son los requisitos? 🤔

**Causa:** None

**Resolución:**

- 1. El sobregiro automático se aplica sin necesidad de solicitud previa cuando no hay fondos suficientes.
- 2. El sobregiro preaprobado requiere una solicitud y aprobación del banco.
- 3. El sobregiro preaprobado necesita un buen historial crediticio y evaluación de cuenta.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-024"
  ],
  "key_fragments": [
    "El sobregiro automático se aplica sin necesidad de solicitud previa cuando no hay fondos suficientes.",
    "El sobregiro preaprobado requiere una solicitud y aprobación del banco.",
    "El sobregiro preaprobado necesita un buen historial crediticio y evaluación de cuenta."
  ],
  "claim_evidence_map": {
    "El sobregiro automático se aplica sin necesidad de solicitud previa cuando no hay fondos suficientes.": [
      "INT-2024-024"
    ],
    "El sobregiro preaprobado requiere una solicitud y aprobación del banco.": [
      "INT-2024-024"
    ],
    "El sobregiro preaprobado necesita un buen historial crediticio y evaluación de cuenta.": [
      "INT-2024-024"
    ]
  }
}
```

---

## INT-2024-197

**Categoría de producto:** otros

**Título:** Seguro de hogar

**Environment:**

```json
{
  "product": "Seguro de hogar",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola! Tengo una duda sobre el seguro de hogar que ofrecen en Davivienda. ¿Podrías explicarme las coberturas principales?

**Causa:** None

**Resolución:**

- 1. El seguro de hogar de Davivienda cubre daños por incendio, terremotos, y robo.
- 2. Incluye cobertura de responsabilidad civil para daños a terceros.
- 3. La inspección previa solo es necesaria en casos especiales o de alto valor.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-197"
  ],
  "key_fragments": [
    "El seguro de hogar de Davivienda cubre daños por incendio, terremotos, y robo.",
    "Incluye cobertura de responsabilidad civil para daños a terceros.",
    "La inspección previa solo es necesaria en casos especiales o de alto valor."
  ],
  "claim_evidence_map": {
    "El seguro de hogar de Davivienda cubre daños por incendio, terremotos, y robo.": [
      "INT-2024-197"
    ],
    "Incluye cobertura de responsabilidad civil para daños a terceros.": [
      "INT-2024-197"
    ],
    "La inspección previa solo es necesaria en casos especiales o de alto valor.": [
      "INT-2024-197"
    ]
  }
}
```

---

## INT-2024-062

**Categoría de producto:** tarjetas

**Título:** Recarga y límites de la eCard virtual de Davivienda

**Environment:**

```json
{
  "product": "Tarjeta de Crédito Visa Clásica",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, tengo una duda sobre mi tarjeta Visa Clásica. No entiendo bien cómo funciona la recarga de la eCard. ¿Me puedes ayudar? 😊

**Causa:** None

**Resolución:**

- 1. La eCard es una tarjeta virtual que se recarga desde la cuenta Davivienda.
- 2. La recarga mínima de la eCard es de $20,000.
- 3. El límite máximo de recarga mensual es de $7,000,000.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-062"
  ],
  "key_fragments": [
    "La eCard es una tarjeta virtual que se recarga desde la cuenta Davivienda.",
    "La recarga mínima de la eCard es de $20,000.",
    "El límite máximo de recarga mensual es de $7,000,000."
  ],
  "claim_evidence_map": {
    "La eCard es una tarjeta virtual que se recarga desde la cuenta Davivienda.": [
      "INT-2024-062"
    ],
    "La recarga mínima de la eCard es de $20,000.": [
      "INT-2024-062"
    ],
    "El límite máximo de recarga mensual es de $7,000,000.": [
      "INT-2024-062"
    ]
  }
}
```

---

## INT-2024-158

**Categoría de producto:** canales_digitales

**Título:** Compatibilidad de la app de Davivienda con sistemas operativos Android e iOS

**Environment:**

```json
{
  "product": "Portal web Davivienda.com",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, tengo una pregunta sobre la app de Davivienda. ¿Está disponible para Android 7.0? 🙈

**Causa:** None

**Resolución:**

- 1. La app de Davivienda es compatible con Android 7.0 y versiones posteriores.
- 2. La app de Davivienda está disponible para iOS 11.0 y versiones más recientes.
- 3. Los usuarios deben verificar la versión de su sistema operativo para asegurar la compatibilidad.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-158"
  ],
  "key_fragments": [
    "La app de Davivienda es compatible con Android 7.0 y versiones posteriores.",
    "La app de Davivienda está disponible para iOS 11.0 y versiones más recientes.",
    "Los usuarios deben verificar la versión de su sistema operativo para asegurar la compatibilidad."
  ],
  "claim_evidence_map": {
    "La app de Davivienda es compatible con Android 7.0 y versiones posteriores.": [
      "INT-2024-158"
    ],
    "La app de Davivienda está disponible para iOS 11.0 y versiones más recientes.": [
      "INT-2024-158"
    ],
    "Los usuarios deben verificar la versión de su sistema operativo para asegurar la compatibilidad.": [
      "INT-2024-158"
    ]
  }
}
```

---

## INT-2024-194

**Categoría de producto:** otros

**Título:** Uso de la App Davivienda para pagar SOAT

**Environment:**

```json
{
  "product": "Seguro de vida",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, ¿cómo están? Quisiera saber cómo puedo pagar el SOAT desde la App. Me han dicho que se puede, pero no estoy seguro cómo hacerlo 🤔

**Causa:** None

**Resolución:**

- 1. El SOAT se puede pagar desde la App de Davivienda sin costos adicionales.
- 2. El proceso involucra seleccionar 'Pagos' y luego 'SOAT' en la App.
- 3. El seguro de vida también puede gestionarse desde la misma App.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-194"
  ],
  "key_fragments": [
    "El SOAT se puede pagar desde la App de Davivienda sin costos adicionales.",
    "El proceso involucra seleccionar 'Pagos' y luego 'SOAT' en la App.",
    "El seguro de vida también puede gestionarse desde la misma App."
  ],
  "claim_evidence_map": {
    "El SOAT se puede pagar desde la App de Davivienda sin costos adicionales.": [
      "INT-2024-194"
    ],
    "El proceso involucra seleccionar 'Pagos' y luego 'SOAT' en la App.": [
      "INT-2024-194"
    ],
    "El seguro de vida también puede gestionarse desde la misma App.": [
      "INT-2024-194"
    ]
  }
}
```

---

## INT-2024-129

**Categoría de producto:** creditos

**Título:** Uso del simulador de crédito de vehículo en la App Davivienda

**Environment:**

```json
{
  "product": "Crédito de vehículo",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, quisiera saber cómo usar el simulador de crédito para un vehículo en la App de Davivienda. ¿Me podrías ayudar? 🚗

**Causa:** None

**Resolución:**

- 1. El simulador de crédito está disponible en la sección de 'Créditos' dentro de la App Davivienda.
- 2. Para usar el simulador, el cliente debe ingresar el valor del vehículo, el plazo del crédito y el porcentaje de la cuota inicial.
- 3. La App calculará las cuotas mensuales con base en la información proporcionada por el cliente.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-129"
  ],
  "key_fragments": [
    "El simulador de crédito está disponible en la sección de 'Créditos' dentro de la App Davivienda.",
    "Para usar el simulador, el cliente debe ingresar el valor del vehículo, el plazo del crédito y el porcentaje de la cuota inicial.",
    "La App calculará las cuotas mensuales con base en la información proporcionada por el cliente."
  ],
  "claim_evidence_map": {
    "El simulador de crédito está disponible en la sección de 'Créditos' dentro de la App Davivienda.": [
      "INT-2024-129"
    ],
    "Para usar el simulador, el cliente debe ingresar el valor del vehículo, el plazo del crédito y el porcentaje de la cuota inicial.": [
      "INT-2024-129"
    ],
    "La App calculará las cuotas mensuales con base en la información proporcionada por el cliente.": [
      "INT-2024-129"
    ]
  }
}
```

---

## INT-2024-106

**Categoría de producto:** creditos

**Título:** Subsidio de tasa de interés para vivienda VIS con Davivienda

**Environment:**

```json
{
  "product": "Crédito de libre inversión",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, quisiera saber cómo funciona lo del subsidio de tasa de interés para vivienda VIS con Davivienda. ¿Me puedes explicar? 🤔

**Causa:** None

**Resolución:**

- 1. El subsidio de tasa de interés aplica para créditos hipotecarios de vivienda de interés social.
- 2. Vivienda de interés social tiene un valor máximo determinado por el gobierno.
- 3. El crédito de libre inversión no está diseñado para la compra de vivienda.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-106"
  ],
  "key_fragments": [
    "El subsidio de tasa de interés aplica para créditos hipotecarios de vivienda de interés social.",
    "Vivienda de interés social tiene un valor máximo determinado por el gobierno.",
    "El crédito de libre inversión no está diseñado para la compra de vivienda."
  ],
  "claim_evidence_map": {
    "El subsidio de tasa de interés aplica para créditos hipotecarios de vivienda de interés social.": [
      "INT-2024-106"
    ],
    "Vivienda de interés social tiene un valor máximo determinado por el gobierno.": [
      "INT-2024-106"
    ],
    "El crédito de libre inversión no está diseñado para la compra de vivienda.": [
      "INT-2024-106"
    ]
  }
}
```

---

## INT-2024-107

**Categoría de producto:** creditos

**Título:** Proceso para solicitar un período de gracia en crédito rotativo por dificultad económica

**Environment:**

```json
{
  "product": "Crédito rotativo",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, buenos días. Tengo un crédito rotativo con ustedes y estoy pasando por una situación económica difícil. Hay alguna forma de pedir un periodo de gracia? Gracias.

**Causa:** None

**Resolución:**

- 1. El cliente puede solicitar un período de gracia en su crédito rotativo a través de la App Davivienda o Davivienda.com.
- 2. La solicitud debe incluir un formulario donde se especifique la situación económica del cliente.
- 3. El tiempo estimado para procesar la solicitud es de 5 días hábiles.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-107"
  ],
  "key_fragments": [
    "El cliente puede solicitar un período de gracia en su crédito rotativo a través de la App Davivienda o Davivienda.com.",
    "La solicitud debe incluir un formulario donde se especifique la situación económica del cliente.",
    "El tiempo estimado para procesar la solicitud es de 5 días hábiles."
  ],
  "claim_evidence_map": {
    "El cliente puede solicitar un período de gracia en su crédito rotativo a través de la App Davivienda o Davivienda.com.": [
      "INT-2024-107"
    ],
    "La solicitud debe incluir un formulario donde se especifique la situación económica del cliente.": [
      "INT-2024-107"
    ],
    "El tiempo estimado para procesar la solicitud es de 5 días hábiles.": [
      "INT-2024-107"
    ]
  }
}
```

---

## INT-2024-085

**Categoría de producto:** transferencias

**Título:** Uso de Bre-b para pago de servicios públicos y privados en la App Davivienda

**Environment:**

```json
{
  "product": "Pago de servicios públicos y privados",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, buen dia. Tengo una duda sobre como se actualiza la funcion de Bre-b para pagar servicios desde mi cuenta. ¿Me puedes ayudar?

**Causa:** None

**Resolución:**

- 1. El sistema Bre-b permite pagar servicios públicos y privados desde la App Davivienda.
- 2. El proceso se realiza ingresando a la sección 'Pagos' de la app.
- 3. Los pagos se acreditan el mismo día si se realiza la transacción correctamente.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-085"
  ],
  "key_fragments": [
    "El sistema Bre-b permite pagar servicios públicos y privados desde la App Davivienda.",
    "El proceso se realiza ingresando a la sección 'Pagos' de la app.",
    "Los pagos se acreditan el mismo día si se realiza la transacción correctamente."
  ],
  "claim_evidence_map": {
    "El sistema Bre-b permite pagar servicios públicos y privados desde la App Davivienda.": [
      "INT-2024-085"
    ],
    "El proceso se realiza ingresando a la sección 'Pagos' de la app.": [
      "INT-2024-085"
    ],
    "Los pagos se acreditan el mismo día si se realiza la transacción correctamente.": [
      "INT-2024-085"
    ]
  }
}
```

---

## INT-2024-052

**Categoría de producto:** tarjetas

**Título:** Actualización de beneficios de tarjetas de crédito

**Environment:**

```json
{
  "product": "Tarjeta de Crédito American Express",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, buenos días 😊. Quería preguntar algo sobre mi Tarjeta de Crédito American Express, ¿puedo?

**Causa:** None

**Resolución:**

- 1. No hay cambios anunciados para los beneficios de la Tarjeta de Crédito American Express.
- 2. Los cambios mencionados son específicos para la Mastercard Black.
- 3. Las actualizaciones se pueden verificar en el sitio web de Davivienda y App.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-052"
  ],
  "key_fragments": [
    "No hay cambios anunciados para los beneficios de la Tarjeta de Crédito American Express.",
    "Los cambios mencionados son específicos para la Mastercard Black.",
    "Las actualizaciones se pueden verificar en el sitio web de Davivienda y App."
  ],
  "claim_evidence_map": {
    "No hay cambios anunciados para los beneficios de la Tarjeta de Crédito American Express.": [
      "INT-2024-052"
    ],
    "Los cambios mencionados son específicos para la Mastercard Black.": [
      "INT-2024-052"
    ],
    "Las actualizaciones se pueden verificar en el sitio web de Davivienda y App.": [
      "INT-2024-052"
    ]
  }
}
```

---

## INT-2024-023

**Categoría de producto:** cuentas

**Título:** Procedimiento para configurar y manejar una cuenta de ahorro para menores

**Environment:**

```json
{
  "product": "Cuenta Vaca (ahorro grupal, hasta 10 participantes)",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola, tengo una duda sobre la Cuenta Vaca. ¿Puedo usarla para ahorrar para mi hermanito menor? 🤔

**Causa:** None

**Resolución:**

- 1. La Cuenta Vaca no es específica para menores, es para ahorro grupal.
- 2. Las cuentas para menores se gestionan desde la app por los acudientes.
- 3. Se requiere el registro civil del menor y la cédula del acudiente para abrir la cuenta.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-023"
  ],
  "key_fragments": [
    "La Cuenta Vaca no es específica para menores, es para ahorro grupal.",
    "Las cuentas para menores se gestionan desde la app por los acudientes.",
    "Se requiere el registro civil del menor y la cédula del acudiente para abrir la cuenta."
  ],
  "claim_evidence_map": {
    "La Cuenta Vaca no es específica para menores, es para ahorro grupal.": [
      "INT-2024-023"
    ],
    "Las cuentas para menores se gestionan desde la app por los acudientes.": [
      "INT-2024-023"
    ],
    "Se requiere el registro civil del menor y la cédula del acudiente para abrir la cuenta.": [
      "INT-2024-023"
    ]
  }
}
```

---

## INT-2024-153

**Categoría de producto:** canales_digitales

**Título:** Uso de la App Davivienda en tablets

**Environment:**

```json
{
  "product": "Portal web Davivienda.com",
  "segment": "Banca Personal",
  "version": "2026"
}
```

**Problema:** Hola! Quería saber si la App de Davivienda funciona bien en tablets o si es solo para celulares 🤔

**Causa:** None

**Resolución:**

- 1. La App Davivienda está optimizada principalmente para celulares.
- 2. Es posible descargar la App en tablets desde las tiendas de aplicaciones.
- 3. Puedes usar la misma cuenta en celulares y tablets.

**Evidence pack:**

```json
{
  "interaction_ids": [
    "INT-2024-153"
  ],
  "key_fragments": [
    "La App Davivienda está optimizada principalmente para celulares.",
    "Es posible descargar la App en tablets desde las tiendas de aplicaciones.",
    "Puedes usar la misma cuenta en celulares y tablets."
  ],
  "claim_evidence_map": {
    "La App Davivienda está optimizada principalmente para celulares.": [
      "INT-2024-153"
    ],
    "Es posible descargar la App en tablets desde las tiendas de aplicaciones.": [
      "INT-2024-153"
    ],
    "Puedes usar la misma cuenta en celulares y tablets.": [
      "INT-2024-153"
    ]
  }
}
```

---

## INT-2024-010

**Categoría de producto:** cuentas

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

## INT-2024-074

**Categoría de producto:** transferencias

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

# Qué rompería el pago de comisiones

Datos: `data/partner_enrollments.csv`, 28 inscripciones del partner. Dos problemas del dataset, por sí solos, pueden cambiar cuánto le pagamos a cada creador — no son defectos cosméticos del CSV, son plata mal calculada.

## 1. `creator_id` vacío — 5 de 28 inscripciones (17.9%)

Cuando el export del partner no trae quién originó el lead, no hay forma de saber a qué creador pagarle esa comisión. En la demo estas filas se marcan como `sin_atribuir` en vez de borrarlas — conservamos el dato (la inscripción sí existe, el dinero sí se debe a alguien), pero quedan visibles y separadas del resto para que alguien las revise.

Lo que **no** debe pasar en producción:

- Pagarle a un creador "por defecto" o al último que tocó el lead en el CRM — eso le da el crédito (y la plata) a quien no generó el lead.
- Ignorar la fila y no pagarle a nadie — si de verdad vino de un creador nuestro, esa es plata que la agencia le debe y le está dejando de pagar.

La única salida correcta es **bloquear esa comisión específica** hasta que alguien la reconcilie a mano contra el CRM del partner (por `enrollment_id` + fecha + monto). Por eso el dato se conserva marcado, nunca se descarta ni se adivina.

## 2. Teléfono que no coincide — 4 de 28 inscripciones (14.3%)

El teléfono que capturó el partner en la inscripción no es el mismo que el lead dio cuando escribió por primera vez. Ejemplos reales del dataset (`src/reporting.py::reporte_ruptura_comisiones`):

| enrollment_id | lead_id | teléfono del lead | teléfono en la inscripción |
|---|---|---|---|
| E001 | L021 | 3000000021 | 3001122 |
| E002 | L036 | 3000000036 | 30112 |
| E003 | L009 | 3000000009 | 3000000996 |
| E004 | L025 | 3000000025 | 3000000995 |

Sin ese cruce, no se puede confirmar que la inscripción corresponde al **mismo** lead que originó un creador nuestro. Tres explicaciones posibles, cada una con una consecuencia financiera distinta:

1. **Error de digitación del partner** al capturar el dato (lo más probable para los casos truncados como "30112" o "3001122") — el lead sí es nuestro, solo está mal escrito.
2. **El partner cruzó mal** la inscripción con un lead que no es el nuestro (alguien que llegó por otro canal, coincidencia de nombre).
3. **Caso límite:** alguien se atribuye una comisión de un lead que no generó.

Pagar la comisión sin distinguir cuál de los tres pasó significa que la agencia puede estar pagando por leads que no fueron suyos (caso 3), o negándole el pago a un creador legítimo por un typo del partner (caso 1). Los dos son errores financieros reales, no detalles técnicos de limpieza de datos.

## Qué hace el sistema hoy — y qué no hace a propósito

`reporte_ruptura_comisiones()` detecta y cuenta ambos casos sobre **cualquier** CSV que se suba en la pestaña C (no solo el dataset de ejemplo), y la interfaz los muestra con ejemplos concretos (`enrollment_id`, teléfono del lead vs. teléfono de la inscripción) para que alguien los revise antes de que se calcule cualquier pago.

El sistema no intenta "adivinar" ni auto-resolver ninguno de los dos casos — normalizar un teléfono truncado a la fuerza, o asumir que el creador más probable es el correcto, sería inventar un dato financiero sin evidencia. Esa decisión le corresponde a alguien con el contexto del partner (puede llamar y confirmar), no a un reporte automático.

# Qué rompería el pago de comisiones — para Dirección Financiera

Para: Dirección Financiera. De: Operaciones/Tecnología.
Base: `data/partner_enrollments.csv` (28 inscripciones del partner) reconciliadas
contra `data/leads.csv` (42 leads de chat) — ver la pestaña **C · Datos y
reporting** del panel, sección "Reconciliación de inscripciones", para los
mismos números en vivo sobre cualquier CSV que suban.

De 28 inscripciones, **1 es un duplicado** (mismo `enrollment_id` repetido, se
descarta quedándose con la fecha de conversión más antigua y válida) y de las
27 restantes, **12 no se pueden pagar tal cual llegaron** — 5 sin creador
asignado y 7 con problema de teléfono (3 con formato inválido, 4 que no
coinciden con el lead original, de las cuales 1 sí tiene un indicio que la
salva). Esto no es un detalle de limpieza de CSV: es plata mal atribuida si
se paga sin filtrar.

## a) Impacto financiero

**`creator_id` nulo — 5 de 27 inscripciones (18.5%).** Cuando el export del
partner no trae quién originó el lead, no hay a quién pagarle. Pagar "por
defecto" al último creador que tocó el lead en el CRM le da crédito (y plata)
a quien no lo generó; no pagar nada es dejar de pagarle a un creador que sí
cumplió. Hoy estas filas se marcan `sin_atribuir` y quedan **bloqueadas** —
ni se pagan ni se descartan — hasta reconciliarlas a mano.

**Teléfono que no coincide — 4 de 27 inscripciones (14.8%), más 3 con formato
inválido que tampoco se pueden cruzar.** Ejemplos reales del dataset:

| Inscripción | Lead | Teléfono del lead | Teléfono en la inscripción | Diagnóstico | Estado |
|---|---|---|---|---|---|
| E001 | L021 | +573000000021 | *(formato inválido: `30011XX22`)* | No se puede verificar | Bloqueada |
| E002 | L036 | +573000000036 | *(formato inválido: `30112`, incompleto)* | No se puede verificar | Bloqueada |
| E003 | L009 | +573000000009 | +573000000996 | Sin ninguna señal que corrobore que es el mismo lead | Bloqueada |
| E004 | L025 | +573000000025 | +573000000995 | Teléfono distinto, **pero el `creator_id` sí es `@manu.deudas`**, el mismo creador que originó a L025 | En Disputa (no Bloqueada) |

El caso E004 es la clave del riesgo financiero: si tratáramos todo mismatch
de teléfono igual, perderíamos la señal de que E004 probablemente **sí** es
el lead correcto con un typo del partner, y le negaríamos una comisión
legítima a `@manu.deudas`. Si tratáramos todo mismatch como pagable sin
revisar, pagaríamos E001/E002/E003 sin ninguna evidencia de que son nuestros
leads — margen perdido a favor del partner o de un creador equivocado.

**Resumen de exposición:** de 27 inscripciones limpias, el sistema de hoy
clasifica 15 como **Pagables de inmediato**, 1 **En Disputa** (señal parcial,
revisar antes de pagar) y 11 **Bloqueadas** (sin ninguna señal, no pagar sin
reconciliar a mano con el partner). Pagar las 12 sin filtrar es el escenario
de mayor riesgo: fuga de comisión hacia leads que no son nuestros. No pagar
ninguna de las 12 hasta resolverlas a mano es el escenario conservador —
cuesta tiempo de revisión, pero no cuesta margen.

## b) Protocolo técnico/operativo de solución

Lo que el sistema ya hace hoy:

- **Cola de Disputas en el CRM** (pestaña C del panel, "Cola de disputas —
  validación humana antes de pagar"): las 12 filas bloqueadas o en disputa
  quedan visibles, con su `match_type` y motivo, para que Finanzas u
  Operaciones las revise una por una antes de aprobar el pago. Ninguna se
  paga automático.

Lo que falta por implementar — recomendación, no construido aún porque los
datos de origen no existen en los CSV de esta prueba:

- **Fallback por `utm_source`:** cuando el teléfono no coincide y el creador
  tampoco corrobora (caso "Sin Coincidencia"), cruzar por el `utm_source` de
  la campaña del creador antes de bloquear del todo — hoy el dataset no trae
  ese campo, así que esta regla queda documentada para cuando el export del
  partner lo incluya.
- **Código de cupón por consejero:** pedirle a Consejería Clara que capture
  un código de cupón único por creador en la inscripción (no solo el
  teléfono) daría una segunda señal de atribución independiente del dato de
  contacto, que es justo el que más se corrompe en captura manual.
- **Cola de Disputas** como paso obligatorio antes de cualquier pago — esta
  parte sí está construida (ver arriba); lo que falta es decidir el SLA de
  revisión (ej. 48h) y quién la resuelve.

## c) Recordatorio de compliance

Ninguna corrección de estos datos debe usarse para prometerle al lead un
ahorro fijo o una tasa — eso no cambia por una reconciliación de comisiones,
sigue prohibido en cualquier mensaje saliente. Y al personal del partner
siempre se le llama **"Consejero"**, nunca "asesor" ni ningún otro término,
en cualquier documento, reporte o comunicación que salga de este análisis.

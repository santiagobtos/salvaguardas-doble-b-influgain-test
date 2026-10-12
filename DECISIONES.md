# Decisiones — qué no se construyó a propósito
- **Sin integración real de WhatsApp/Meta.** Regla dura del enunciado: no
  tocar WhatsApp Business real. Las "plantillas de WhatsApp" quedan como
  borradores en texto en SQLite, nunca se envían.

- **Sin motor de scoring de crédito ni tasas.** El enunciado prohíbe
  inventar tasas o puntajes. El sistema solo pre-califica por monto/tipo
  de deuda/interés expresado, nunca "aprueba" nada.

- **Sin una bandeja única con todos los borradores pendientes.** Sí hay
  revisión real (pestaña B: editar/Aprobar/Descartar por lead antes de
  que "salga"), pero es por lead, no una lista global de todo lo
  `pending_review`. No alcanzó a ser prioridad frente al resto del flujo.

- **Sin autenticación ni multiusuario.** Demo de un solo operador; cada
  acción queda como `"sistema"` en el `audit_trail` (el campo ya existe,
  falta la capa de login). Construir auth real no aporta nada a lo que
  esta prueba mide.

- **Reintentos de la cola de fallos son manuales**
  (`POST /crm/failed-queue/retry`), no un worker con scheduler. Se
  prefirió así para que la demo fuera reproducible en un solo comando sin
  depender de un proceso en segundo plano (ver `NOTA_ESCALA.md`).

- **Sin un LLM en vivo redactando los mensajes.** Fue el riesgo técnico
  más grande a evaluar: en compliance financiero duro (nunca prometer
  ahorro, nunca decir "asesor", nunca inventar tasas) un LLM sin
  guardrails puede alucinar y romper justo esas reglas, y 72h no alcanzan
  para probarlo a fondo. Las plantillas deterministas de
  `crm_automation` sí incorporan lo que el lead escribió de verdad (tipo
  de deuda, monto) sin ese riesgo.

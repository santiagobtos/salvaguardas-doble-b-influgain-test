# Decisiones — qué no se construyó a propósito

Esta prueba se puede expandir casi sin límite. Esto es lo que decidí dejar
fuera, y por qué:

- **Sin UI web para revisar borradores.** Los `drafts` quedan en SQLite con
  estado `pending_review` y se pueden listar vía `/crm/failed-queue` o
  consultando la base directamente. No construí una pantalla porque el
  punto de la prueba es el criterio del flujo (clasificar, pre-calificar,
  nunca auto-publicar), no una interfaz bonita.

- **Sin integración real de WhatsApp/Meta.** Las "plantillas de WhatsApp"
  son borradores en texto en la base de datos, no mensajes enviados. La
  regla dura de la prueba es justamente no tocar WhatsApp Business real.

- **Sin autenticación ni multiusuario.** Es una demo de un solo operador.
  En producción cada acción del CRM llevaría un `actor` real autenticado en
  vez del string `"sistema"` que uso en la demo (el campo ya existe en
  `audit_trail`, falta la capa de login).

- **Sin motor de scoring de crédito ni tasas.** A propósito — la prueba
  prohíbe inventar tasas o puntajes, y el sistema solo pre-califica por
  monto/tipo de deuda/interés expresado, nunca "aprueba" nada.

- **Reintentos de la cola de fallos son manuales en la demo
  (`POST /crm/failed-queue/retry`).** En producción sería un worker
  programado; no lo automaticé con un scheduler para mantener la demo
  reproducible en un solo comando (ver `NOTA_ESCALA.md`).

- **El reporting (Ejercicio C) usa los CSV fijos, no la base SQLite en
  vivo.** Es intencional: la prueba pide reporting sobre datos sucios como
  insumo separado, no sobre el estado transaccional del CRM corriendo en
  esta demo.

- **Sin un LLM en vivo redactando los mensajes.** Lo evalué y decidí no
  conectar una API de IA generativa (tipo Claude/OpenAI) para los borradores
  de WhatsApp. En un contexto de compliance financiero duro (nunca prometer
  ahorro, nunca decir "asesor", nunca inventar tasas) un LLM sin guardrails
  serios puede alucinar y violar justo esas reglas — un riesgo que no quería
  asumir en 72 horas sin poder probarlo a fondo. En su lugar, las plantillas
  de `crm_automation.WHATSAPP_TEMPLATES` son deterministas (nunca rompen
  compliance) y sí incorporan lo que el lead escribió de verdad — tipo de
  deuda y monto, extraídos vía `rules.yaml` — que es lo que la prueba mide
  explícitamente ("criterio de negocio, no si pegas bien un prompt"). En
  producción, el primer paso hacia un LLM real sería agregarlo detrás de un
  validador post-generación que rechace cualquier borrador con lenguaje
  prohibido antes de dejarlo en la cola humana.

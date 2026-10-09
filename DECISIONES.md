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

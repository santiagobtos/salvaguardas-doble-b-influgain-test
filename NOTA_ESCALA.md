# Nota de escala — de la demo a ~200 leads/hora

Esta demo corre en SQLite y procesa mensajes uno por uno de forma síncrona,
suficiente para unos pocos leads por minuto. A ~200 leads/hora (~3.3 por
minuto, con picos más altos por campañas) los cuellos de botella y cambios
necesarios serían:

1. **Ingesta asíncrona.** El webhook de entrada (`POST /webhook/lead`) debe
   responder rápido y encolar el procesamiento (ej. una cola tipo
   Redis/SQS/RabbitMQ) en vez de clasificar en la misma request. Hoy
   `procesar_mensaje_entrante` es síncrono; a escala se convierte en un
   worker que consume de la cola.

2. **Base de datos.** SQLite sirve para la demo pero no soporta escrituras
   concurrentes a ese volumen. Migrar `src/db.py` a Postgres (manteniendo las
   mismas tablas: `leads`, `decisions_log`, `drafts`, `audit_trail`,
   `failed_queue`) es el cambio mínimo — la capa de acceso ya está aislada en
   un solo módulo, así que el resto del código no cambia.

3. **Cola humana con límite de capacidad.** Los borradores (`drafts`) hoy se
   acumulan sin límite. A 200/hora hay que medir cuántos puede revisar un
   humano por hora y, si se supera, priorizar (por monto de deuda, por
   antigüedad) en vez de FIFO ciego, o añadir más revisores.

4. **Reglas con versión.** `rules.yaml` editado en caliente funciona para un
   equipo chico; a mayor escala conviene versionarlo (quién cambió qué
   umbral y cuándo) para poder auditar por qué un lead se clasificó de cierta
   forma en un momento dado. El `decisions_log` ya guarda la razón por
   decisión, que ayuda a reconstruir esto.

5. **Cola de fallos con alerta real.** Hoy `failed_queue` se reintenta
   manualmente (`reintentar_fallos`). A escala necesita un worker con backoff
   exponencial y una alerta (Slack/email) cuando algo pasa a
   `fallido_permanente`, para que no se pierda silenciosamente.

6. **Idempotencia.** Con más volumen aumenta la probabilidad de reintentos y
   duplicados desde el canal de origen. `upsert_lead` ya es idempotente por
   `lead_id`; falta aplicar la misma garantía en la cola de ingesta
   (deduplicar por `lead_id` + hash del mensaje antes de encolar).

Lo que **no** cambiaría: el criterio de negocio (reglas editables, nunca
auto-publicar, siempre lenguaje condicional) es independiente del volumen —
es la parte que el stack técnico debe seguir respetando sin importar cuántos
leads lleguen por hora.

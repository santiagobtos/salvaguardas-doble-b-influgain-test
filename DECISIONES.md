# Decisiones — qué no se construyó a propósito

Esta prueba la puedo seguir ampliando casi sin límite, así que acá dejo claro qué decidí no meter y por qué. Separo entre lo que el mismo enunciado no deja hacer, y lo que quedó por fuera simplemente por las 72 horas y por estar yo solo con esto.

## Por el alcance de la prueba

**WhatsApp o Meta real.** Esto ni se me ocurrió tocarlo, porque el enunciado es tajante en que no se puede meter mano a WhatsApp Business real. Entonces lo que armé son borradores de texto que se quedan guardados en SQLite, nunca llegan a salir de ahí.

**Un motor que invente tasas o puntajes de crédito.** Tampoco, porque la prueba lo prohíbe directamente. Lo único que hace el sistema es pre-calificar mirando el monto que mencionó el lead, el tipo de deuda y si mostró interés en hablar con un Consejero — en ningún momento le pone un número a nada ni "aprueba" algo.

**Que el reporting lea la base en vivo del CRM.** Esto lo dejé así a propósito: el enunciado pide que se reporte sobre "leads + CSV sucio" como algo aparte, no sobre lo que está pasando en ese momento en el CRM. Son dos cosas que decidí mantener separadas.

## Por las circunstancias (72h, solo yo)

**Una bandeja única con todos los borradores pendientes.** Esto sí me quedó debiendo. Lo que sí hay es revisión real por cada lead — en la pestaña B uno abre el lead, edita el borrador si quiere, y lo aprueba o lo descarta antes de que salga — pero no alcancé a armar una vista donde se vean de una todos los que están pendientes en un solo lugar. Con todo lo demás que había que sacar adelante, esto no quedó como prioridad.

**Autenticación o manejo de varios usuarios.** No lo armé porque esto es una demo pensada para un solo operador. Cada acción queda registrada como `"sistema"` en el audit trail — el campo para meter un actor real ya está ahí, solo falta la capa de login encima — y honestamente, meter autenticación de verdad no le suma nada a lo que esta prueba está midiendo.

**Que los reintentos de la cola de fallos fueran automáticos.** Los dejé manuales, con un botón que llama a `/crm/failed-queue/retry`, en vez de un worker corriendo solo con su propio scheduler. Lo hice así para que toda la demo se pudiera reproducir con un solo comando, sin depender de que algo esté corriendo aparte en segundo plano (el detalle completo está en `NOTA_ESCALA.md`).

**Meter un LLM en vivo para redactar los mensajes.** Esto lo pensé harto y al final decidí no hacerlo. Estamos hablando de compliance financiero bien estricto — nunca prometer un ahorro, nunca llamar "asesor" a nadie, nunca inventarse una tasa — y un LLM sin guardrails bien probados se puede mandar a alucinar justo ahí, en lo que más importa no romper. Y 72 horas no me alcanzaban para probar eso a fondo como para confiar en él. Por eso terminé usando las plantillas deterministas de `crm_automation`: nunca se salen de las reglas de compliance, y aun así sí usan lo que el lead escribió de verdad (tipo de deuda, monto).

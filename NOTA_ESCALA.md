# Nota de escala — de la demo a ~200 leads/hora

Esta demo corre en SQLite y procesa los mensajes uno por uno, de forma
síncrona. Para unos pocos leads por minuto eso sobra. El problema aparece
en ~200 leads/hora (unos 3-4 por minuto, con picos más fuertes en días de
campaña). Esto es lo que yo cambiaría, en orden de cuánto duele cada cosa:

1. **Ingesta asíncrona.** Ahora mismo `procesar_mensaje_entrante` corre
   dentro de la misma request del webhook — si entran varios leads
   seguidos, se van a pisar. Lo primero que haría es que `POST
   /webhook/lead` solo reciba y encole (Redis, SQS, lo que sea) y que la
   clasificación la haga un worker aparte.

2. **Base de datos.** SQLite no aguanta escrituras concurrentes a ese
   volumen pero la base de datos que tengo implementada en el momento tiene todo 
   con una disposición con la cual migrar a postgre sería cosa de sentarse un rato , planear 
   y lanzar la migración , el problema es que la implementación de base de datos se adapta
   al caso en el que se tenía que trabajar pero yendonos a una escala no es la herramienta más 
   óptima , el mismo diseño en otra herramienta mas robusta es la solución

3. **Cola humana con límite.** Los `drafts` hoy se acumulan sin un límite claro. A
   200/hora hace falta saber cuántos puede revisar un humano por hora de
   verdad, y si se pasa de ahí, priorizar por algo (monto de deuda,
   antigüedad) en vez de simplemente ir por orden de llegada. Se deben implementar diferentes métricas de priorización para poder que un humano siga pudiendo trabajar con un volumen de datos tan grande sin 
   sacrificar eficiencia ni la manera en que lo que creé es amigable con el operador

4. **Versionar las reglas.** Editar `rules.yaml` en caliente funciona bien
   para un equipo chico, pero a más escala se necesita saber quién cambió
   qué regla y cuándo, para poder explicar por qué un lead se clasificó
   de determinada forma en un momento dado. El `decisions_log` ya guarda
   la razón de cada decisión pero de manera genérica, la trazabilidad de una regla 
   debe ser más robusta cuando se habla de un servicio que está funcionando de manera real.
   Aquí pienso que podría implementar auditoría necesaria para que no se escape ningún cambio y no sea tan libre

5. **Alertar de verdad en la cola de fallos.** `failed_queue` hoy se
   reintenta a mano (`reintentar_fallos`). A ese volumen necesita un
   worker con backoff y una alerta real (Slack, correo) cuando algo cae
   en `fallido_permanente` para que no se pierda completamente y en ese caso 
   si haya un factor humano arreglando el problema con las herramientas de trazabilidad que se van a implementar

6. **filtrado en la cola de entrada.** Con más volumen también
   aumentan los reintentos y duplicados que manda el canal de origen.
   El manejo de errores se debe robustecer tanto para leads que entran por los diferentes canales
   como para la información que envía el partner , con un volumen de leads mas grande se debe 
   mejorar la disposición de los errores y se debe mejorar la manera en la que se solucionan para que un cuello
   de botella no sea la acumulación de los mismos

7. **La interfaz también sufre con más datos.** Más leads es más filas en
   cada tabla del panel, y Streamlit no soportaría una cantidad de volumen como la que 
   se plantea por lo cual migrar a otro tipo de herramienta de interfaz gráfica 
   se hace completamente necesaria y así mismo se necesita mejorar la disposición y el web designing para
   un volumen más grande y un proyecto más serio

8. **Informes de comisiones más estrictos.** Cuando los datos del partner
   sean reales (negociaciones cerradas de verdad, no simuladas), los
   filtros de verificación tienen que ser más duros para confirmar que lo
   que llega hace match con el lead correcto. Yo haría un módulo aparte
   solo para comisiones, bien estricto, porque un dato que falte (por
   ejemplo un cliente sin creador asignado) no debería hacer que se
   pierda la trazabilidad de la comisión de ese creador.


Lo que **no** cambiaría es el criterio de negocio: reglas editables, nunca
auto-publicar, siempre lenguaje condicional. Eso es independiente del
volumen . El stack ténico es sumamente escalable ya que las reglas de negocio no cambian por sí 
mismas sino que más bien se complementan con nuevas , por tanto el backend no debería ser remodelado
sino complementado

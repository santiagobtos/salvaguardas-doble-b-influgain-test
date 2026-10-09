# Nota de uso de IA

Usé Claude Code (Anthropic) como asistente de desarrollo para construir este
sistema, a partir de los requisitos de la prueba. Esto es lo que hice yo y lo
que vino de la herramienta:

- **Decisiones de negocio y de alcance** (qué agencia y partner ficticios
  inventar, qué reglas de compliance aplicar, qué datos generar, qué
  stack usar y por qué, qué dejar explícitamente fuera — ver
  `DECISIONES.md`) las tomé yo.
- **Arquitectura** (Python + FastAPI + SQLite + YAML, estructura de carpetas,
  separación entre los 4 ejercicios) se diseñó conmigo revisando y aprobando
  cada parte antes de escribir código, no se le pidió a la IA "hazme todo"
  sin supervisión.
- **Generación de código** (el motor de reglas, los endpoints, el reporting,
  el generador de datos ficticios, los tests) se escribió con ayuda de la
  IA, revisando cada archivo antes de aceptarlo.
- **Verificación**: corrí los tests y la demo yo mismo para confirmar que el
  comportamiento es el esperado antes de entregar (ver sección de
  verificación más abajo).

La IA no tuvo acceso a ningún sistema real de Influgain ni a credenciales:
todos los datos y el entorno son ficticios, como exige la prueba.

# Salvaguardas Doble B × Consejería Clara — Prueba técnica Influgain

Sistema de ejemplo que simula el flujo de una agencia de marketing de alivio
de deudas vía creadores: leads por chat → pre-calificación automática →
handoff a un partner ficticio ("Consejería Clara") → CRM con disposiciones →
reporting sobre datos sucios → mini sistema de contenido.

**Todo es ficticio.** No hay acceso a GoHighLevel, Meta, WhatsApp Business,
Supabase ni a Influgain. Los datos (leads, inscripciones, fuentes de
contenido) son generados, no reales.

## Setup (menos de 15 minutos)

```bash
# 1. Crear entorno e instalar dependencias
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 2. (Opcional) Regenerar los datos ficticios — ya vienen incluidos en /data
python scripts/generate_fake_data.py

# 3. Correr los tests
pytest

# 4. Correr la demo completa (Ejercicios A -> B -> C -> D en consola)
python cli.py demo

# 5. Levantar el panel operativo (interfaz principal para la demo/video)
streamlit run streamlit_app.py
# Panel: http://localhost:8501
```

Al abrir el panel se siembran automáticamente ~18 leads pasados por el
agente real (no son datos falseados en la UI), así la pestaña de CRM no
empieza vacía. Desde ahí puedes mandar un mensaje nuevo, aplicar
disposiciones directamente en la tabla, subir tu propio CSV de
inscripciones, y ver el efecto de cada acción en vivo. El botón **"Reiniciar
panel"** en la barra lateral resetea la operación en vivo (A y B) sin tocar
los datos fijos del Ejercicio C.

También existe una API HTTP equivalente (`uvicorn webhook_server:app
--reload`, documentada en `/docs`) por si se necesita integrar por webhook en
vez de interfaz — ver [`webhook_server.py`](webhook_server.py). El panel de
Streamlit es la interfaz pensada para la demo/video.

## Qué hace cada pieza

| Ejercicio | Código | Qué prueba | En el panel |
|---|---|---|---|
| A — Pre-calificación + handoff | `src/prequalification_agent.py` | Ingesta un mensaje, clasifica (`responder`/`ignorar`/`escalar_humano`), pre-califica y deja un **borrador** en cola humana. Nunca envía ni transfiere solo. | Pestaña "A · Pre-calificación": formulario + historial de decisiones |
| B — CRM | `src/crm_automation.py` | Aplica disposiciones, mueve etapa, genera borrador de WhatsApp, deja audit trail, maneja errores (teléfono faltante, lead inexistente, disposición inválida) con cola de fallos y reintento. | Pestaña "B · CRM": tabla editable de 18 leads con selector de disposición por fila, audit trail, cola de fallos y 3 botones para simular errores |
| C — Datos y reporting | `src/reporting.py` | Limpia un CSV sucio del partner (subido o el incluido), calcula funnel, leads estancados y qué rompería comisiones. | Pestaña "C · Datos y reporting": subir CSV, vista de datos sucios resaltados, botón de limpieza, métricas y explicación |
| D — Contenido | `src/content_system.py` | Genera 3 guiones priorizados a partir de `data/content_sources.json`, cada uno trazable a su fuente. | Pestaña "D · Contenido": tarjetas de guiones |

## Reglas de negocio editables sin tocar código

Todo el criterio de clasificación vive en [`rules/rules.yaml`](rules/rules.yaml)
y se recarga en cada request: palabras que fuerzan escalar a humano, palabras
que indican baja/ignorar, umbrales de monto de deuda, palabras para inferir
tipo de deuda, palabras de interés en el Consejero, y días para considerar un
lead "estancado". Cambiar un valor ahí cambia el comportamiento sin reiniciar
ni tocar `src/`.

## Lenguaje de compliance aplicado

- Nunca se usa la palabra "asesor" para el personal del partner — siempre
  "Consejero".
- El ahorro siempre se menciona en condicional ("podría", "en muchos casos"),
  nunca como promesa.
- No se inventan tasas de interés ni puntajes de crédito en ninguna plantilla.
- Mensajes ambiguos o de riesgo (demandas, embargos, amenazas, fraude) se
  escalan a un humano automáticamente, nunca los responde el agente solo.

## Datos ficticios incluidos

- `data/leads.csv`: 42 leads de chat simulados.
- `data/partner_enrollments.csv`: 28 filas (incluye duplicado intencional),
  con teléfonos que no coinciden, `creator_id` vacío y fechas inválidas a
  propósito, para ejercitar la limpieza de datos del Ejercicio C.
- `data/content_sources.json`: 10 fuentes de contenido ficticias.

## Otros documentos de entrega

- [`NOTA_ESCALA.md`](NOTA_ESCALA.md) — cómo escalaría esto a ~200 leads/hora.
- [`NOTA_IA.md`](NOTA_IA.md) — cómo se usó IA para construir este sistema.
- [`DECISIONES.md`](DECISIONES.md) — qué no se construyó a propósito.
- [`RUPTURA_COMISIONES.md`](RUPTURA_COMISIONES.md) — qué rompería el pago de comisiones (Ejercicio C).

# Salvaguardas Doble B × Consejería Clara — Prueba técnica Influgain

Sistema de ejemplo que simula el flujo de una agencia de marketing de alivio
de deudas vía creadores: leads por chat → pre-calificación automática →
handoff a un partner ficticio ("Consejería Clara") → CRM con disposiciones →
reporting sobre datos sucios → mini sistema de contenido.

**Todo es ficticio.** No hay acceso a GoHighLevel, Meta, WhatsApp Business,
Supabase ni a Influgain. Los datos (leads, inscripciones, fuentes de
contenido) son generados, no reales.

## Setup (menos de 15 minutos)

**Un solo clic (Windows):** doble clic en [`demo.bat`](demo.bat) — crea el
entorno si hace falta, instala dependencias, corre los tests, corre
`cli.py demo` en consola y al final abre el panel solo. Equivale a los
5 pasos de abajo, sin escribir ningún comando.

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
# En la pestaña "Leads que llegan" hay que darle una vez a
# "Cargar leads por defecto" para sembrar el CRM en vivo.
```

También existe una API HTTP equivalente (`uvicorn webhook_server:app
--reload`, documentada en `/docs`) por si se necesita integrar por webhook en
vez de interfaz — ver [`webhook_server.py`](webhook_server.py).

## Consola real (output de los pasos 3-5, sin editar)

```
$ pytest
........                                                                 [100%]
8 passed in 0.08s

$ python cli.py demo
======================================================================
EJERCICIO A — Agente de pre-calificación + handoff
======================================================================
- L901: decisión=responder | razón=Cuenta que tiene deuda de tarjeta de crédito por $3.500.000 y pregunta qué puede hacer — dentro de lo normal. | draft_id=1
- L902: decisión=escalar_humano | razón=Palabra de riesgo/ambigüedad detectada: 'demanda' | draft_id=None
- L903: decisión=ignorar | razón=Palabra de salida/no-interés detectada: 'no me interesa' | draft_id=None

======================================================================
EJERCICIO B — Automatización CRM (disposiciones)
======================================================================
- L901 -> Transferido: {'status': 'borrador_pendiente', 'motivo': 'borrador_sin_revisar', 'draft_id': 1}
- L902 -> Call Back: {'status': 'ok', 'stage': 'Agendado', 'draft_id': 2, 'intentos_webhook': 1}
- L999 -> Info Sent (lead inexistente, debe ir a cola de fallos): {'status': 'error', 'motivo': 'lead_no_encontrado'}
- Cola de fallos pendiente: [{'id': 1, 'tipo': 'lead_no_encontrado', 'error': "Lead 'L999' no existe en la base", 'status': 'pending_retry', ...}]
- Reintento de fallos: [{'id': 1, 'status': 'reintentado'}]

======================================================================
EJERCICIO C — Datos y reporting (sobre data/leads.csv + partner_enrollments.csv)
======================================================================
- Funnel general: {'leads_totales': 42, 'respondidos': 19, 'pre_calificados': 20, 'transferidos': 17, 'inscritos_activos': 4, 'tasa_respuesta_pct': 45.2, 'tasa_transferencia_pct': 85.0, 'tasa_inscripcion_pct': 23.5}
- Leads estancados: 3
- Inscripciones sin creator_id: 5
- Inscripciones con teléfono mismatch: 4

======================================================================
EJERCICIO D — Mini sistema de contenido (sobre leads reales de data/leads.csv)
======================================================================
- Riesgo legal, deudas de libranza/hipoteca y señales de desconfianza (15 leads, score 32): [Gancho] ¿Te llegó algo que suena a embargo o demanda, o simplemente n...
- Piden información pero no dan el siguiente paso (15 leads, score 30): [Gancho] ¿Escribiste pidiendo información y nadie te explicó cuál era ...
- Deuda de tarjeta/consumo y no saber por dónde empezar (12 leads, score 21): [Gancho] ¿Tienes tarjeta, crédito de consumo o varias deudas juntas y ...

======================================================================
FIN DEMO
======================================================================

$ streamlit run streamlit_app.py
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```



## Otros documentos de entrega

- [`NOTA_ESCALA.md`](NOTA_ESCALA.md) — cómo escalaría esto a ~200 leads/hora.
- [`NOTA_IA.md`](NOTA_IA.md) — cómo se usó IA para construir este sistema.
- [`DECISIONES.md`](DECISIONES.md) — qué no se construyó a propósito.
- [`RUPTURA_COMISIONES.md`](RUPTURA_COMISIONES.md) — qué rompería el pago de comisiones (Ejercicio C).

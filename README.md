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

# 5. Levantar la API para probar los webhooks interactivamente
uvicorn webhook_server:app --reload
# Abrir http://127.0.0.1:8000/docs
```

## Qué hace cada pieza

| Ejercicio | Código | Qué prueba |
|---|---|---|
| A — Pre-calificación + handoff | `src/prequalification_agent.py`, `POST /webhook/lead` | Ingesta un mensaje, clasifica (`responder`/`ignorar`/`escalar_humano`), pre-califica y deja un **borrador** en cola humana. Nunca envía ni transfiere solo. |
| B — CRM | `src/crm_automation.py`, `POST /crm/disposition` | Aplica disposiciones, mueve etapa, genera borrador de WhatsApp, deja audit trail, maneja errores (teléfono faltante, lead inexistente, disposición inválida) con cola de fallos y reintento. |
| C — Datos y reporting | `src/reporting.py`, `GET /reporting/*` | Limpia `data/leads.csv` + `data/partner_enrollments.csv` (con errores a propósito), calcula funnel, leads estancados y qué rompería comisiones. |
| D — Contenido | `src/content_system.py`, `GET /content/scripts` | Genera 3 guiones priorizados a partir de `data/content_sources.json`, cada uno trazable a su fuente. |

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

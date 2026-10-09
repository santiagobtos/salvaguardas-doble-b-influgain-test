"""Ejercicio A: agente de pre-calificación + handoff humano.

Ingesta un mensaje nuevo sin intervención humana, clasifica, y si corresponde
deja un BORRADOR de respuesta en cola humana. Nunca publica ni transfiere solo.
"""
from datetime import datetime, timezone

from src import db
from src.rules_engine import (
    clasificar_mensaje,
    extraer_monto_deuda,
    extraer_tipo_deuda,
    load_rules,
    tiene_interes_consejero,
)

# Lenguaje de compliance: nunca "asesor", ahorro siempre condicional,
# nunca se inventan tasas ni puntajes de crédito.
PLANTILLA_RESPUESTA = (
    "Hola, gracias por escribirnos a Salvaguardas Doble B. Con la información "
    "que nos compartiste, en muchos casos un Consejero de Consejería Clara podría "
    "ayudarte a revisar opciones para tu deuda de tipo '{tipo_deuda}'. Esto no es "
    "una promesa de ahorro ni de aprobación, depende de la revisión de tu caso. "
    "¿Quieres que te conectemos con un Consejero para una revisión sin costo?"
)


def procesar_mensaje_entrante(lead_id, creador, canal, mensaje, telefono):
    """Punto de entrada único del Ejercicio A. Ingesta -> clasifica -> actúa."""
    rules = load_rules()
    decision, razon = clasificar_mensaje(mensaje, rules)
    timestamp = datetime.now(timezone.utc).isoformat()

    db.upsert_lead(
        lead_id=lead_id,
        timestamp=timestamp,
        creador=creador,
        canal=canal,
        mensaje=mensaje,
        telefono=telefono,
        estado=decision,
    )

    draft_id = None

    if decision == "responder":
        monto = extraer_monto_deuda(mensaje)
        tipo_deuda = extraer_tipo_deuda(mensaje, rules)
        interes = tiene_interes_consejero(mensaje, rules)
        db.actualizar_prequalificacion(lead_id, monto, tipo_deuda, interes)

        contenido = PLANTILLA_RESPUESTA.format(tipo_deuda=tipo_deuda.replace("_", " "))
        draft_id = db.crear_draft(lead_id, timestamp, canal=canal, contenido=contenido)

    db.log_decision(timestamp, lead_id, decision, razon, draft_id)

    return {
        "lead_id": lead_id,
        "decision": decision,
        "razon": razon,
        "draft_id": draft_id,
        "timestamp": timestamp,
    }

"""Ejercicio A: agente de pre-calificación + handoff humano.

Ingesta un mensaje nuevo sin intervención humana, clasifica, y si corresponde
deja un BORRADOR de respuesta en cola humana. Nunca publica ni transfiere solo.
"""
import random
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
# nunca se inventan tasas ni puntajes de crédito. El borrador se arma
# combinando piezas al azar para que no suene a plantilla repetida.
_SALUDOS = [
    "Hola, gracias por escribirnos a Salvaguardas Doble B.",
    "¡Hola! Qué bueno que nos escribes a Salvaguardas Doble B.",
    "Hola, recibimos tu mensaje en Salvaguardas Doble B.",
    "Hola, gracias por tu confianza en contarnos esto.",
]
_CUERPOS = [
    "Con lo que nos compartiste, en muchos casos un Consejero de Consejería Clara podría ayudarte a revisar opciones para tu {tipo_frase}.",
    "Entendemos que no es fácil hablar de esto. Un Consejero de Consejería Clara suele poder revisar casos como el tuyo con {tipo_frase} y contarte qué opciones existen.",
    "Leímos tu caso con atención. Un Consejero de Consejería Clara podría orientarte sobre tu {tipo_frase} y qué caminos hay disponibles.",
    "Casos como el tuyo con {tipo_frase} los revisa un Consejero de Consejería Clara, que puede contarte con calma qué opciones aplican.",
]
_DISCLAIMERS = [
    "Esto no es una promesa de ahorro ni de aprobación, depende de la revisión de tu caso.",
    "Ojo: no podemos prometer un monto exacto de ahorro, todo depende de tu situación particular.",
    "Nada de esto es una garantía — cada caso se revisa de forma individual.",
]
_CIERRES = [
    "¿Quieres que te conectemos con un Consejero para una revisión sin costo?",
    "¿Te gustaría que un Consejero te contacte para revisar tu caso, sin costo?",
    "Si quieres, te conectamos con un Consejero para una primera revisión sin costo.",
]
_TIPO_DEUDA_FRASES = {
    "tarjeta_credito": "deuda de tarjeta de crédito",
    "libranza": "libranza",
    "libre_inversion": "crédito de libre inversión",
    "hipotecario": "deuda hipotecaria",
    "no_especificado": "deuda",
}

# La mayoría de leads dicen, en esencia, "tengo esta deuda, ayúdenme" — la
# razón se arma reflejando ESE caso puntual (tipo de deuda, si dio un monto,
# si pidió hablar con un Consejero) en vez de repetir siempre la misma
# frase, pero sin inventar nada que el mensaje no diga.
_RAZON_CON_MONTO = [
    "Pide ayuda con su {tipo_frase} y da un monto ({monto_frase}) — caso estándar, se puede responder.",
    "Cuenta que tiene {tipo_frase} por {monto_frase} y pregunta qué puede hacer — dentro de lo normal.",
    "Menciona {tipo_frase} de {monto_frase} y pide orientación, nada fuera de lo común.",
]
_RAZON_SIN_MONTO = [
    "Pide ayuda con su {tipo_frase}, sin dar un monto exacto — dentro de lo normal, se puede responder.",
    "Pregunta por el programa en relación a {tipo_frase}, mensaje estándar sin datos de riesgo.",
    "Cuenta que tiene {tipo_frase} y quiere saber más — caso típico, no hay nada que escalar.",
]
_RAZON_INTERES_EXTRA = " Además pide hablar con un Consejero."


def _construir_razon_responder(tipo_deuda, monto, interes_consejero):
    tipo_frase = _TIPO_DEUDA_FRASES.get(tipo_deuda, "una deuda")
    if monto:
        monto_frase = f"${monto:,}".replace(",", ".")
        razon = random.choice(_RAZON_CON_MONTO).format(tipo_frase=tipo_frase, monto_frase=monto_frase)
    else:
        razon = random.choice(_RAZON_SIN_MONTO).format(tipo_frase=tipo_frase)
    if interes_consejero:
        razon += _RAZON_INTERES_EXTRA
    return razon


def generar_draft_respuesta(tipo_deuda):
    tipo_frase = _TIPO_DEUDA_FRASES.get(tipo_deuda, "deuda")
    return " ".join([
        random.choice(_SALUDOS),
        random.choice(_CUERPOS).format(tipo_frase=tipo_frase),
        random.choice(_DISCLAIMERS),
        random.choice(_CIERRES),
    ])


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
        razon = _construir_razon_responder(tipo_deuda, monto, interes)

        contenido = generar_draft_respuesta(tipo_deuda)
        draft_id = db.crear_draft(lead_id, timestamp, canal=canal, contenido=contenido)

    db.log_decision(timestamp, lead_id, decision, razon, draft_id)

    return {
        "lead_id": lead_id,
        "decision": decision,
        "razon": razon,
        "draft_id": draft_id,
        "timestamp": timestamp,
    }

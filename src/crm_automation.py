"""Ejercicio B: automatización tipo CRM sobre disposiciones de un lead.

Disposiciones soportadas: No Answer | Info Sent | Transferido | Call Back |
No le interesa. Cada una mueve la etapa del lead, genera un borrador de
WhatsApp compliant, y deja audit trail. Los errores van a una cola de
fallos (dead-letter queue) con reintento, nunca se pierden en silencio.
"""
import json
import random
from datetime import datetime, timezone

from src import db

STAGE_MAP = {
    "No Answer": "Reintento",
    "Info Sent": "Información Enviada",
    "Transferido": "Transferido al Partner",
    "Call Back": "Agendado",
    "No le interesa": "Descartado",
}

# Etapa aparte de "Agendado": ahí el lead pidió que lo llamen después, acá
# es el sistema el que necesita un dato del lead para poder avanzar. Son
# dos situaciones de negocio distintas y conviene que se vean distintas.
ETAPA_PENDIENTE_TELEFONO = "Pendiente de Teléfono"

_MENSAJES_PEDIR_TELEFONO = [
    "Hola, para conectarte con un Consejero de Consejería Clara necesitamos un número de contacto válido. ¿Nos lo compartes?",
    "Hola, nos falta tu número de teléfono para poder transferir tu caso a un Consejero. ¿Nos lo compartes cuando puedas?",
    "Hola, antes de conectarte con un Consejero necesitamos un teléfono de contacto. ¿Puedes compartirlo por aquí?",
]


class WebhookCRMError(Exception):
    """Simula una falla de red/API al notificar al CRM externo del partner
    (timeout, 5xx, etc.) — no es un error real, es para poder probar la
    resiliencia del sistema a demanda desde la interfaz."""

_TIPO_DEUDA_FRASES = {
    "tarjeta_credito": "tu tarjeta de crédito",
    "libranza": "tu libranza",
    "libre_inversion": "tu crédito de libre inversión",
    "hipotecario": "tu situación hipotecaria",
    "no_especificado": "tu caso",
}

# Lenguaje compliant: nunca "asesor", nunca promesas de ahorro. Varias
# variantes por disposición, elegidas al azar, para que no suene a
# plantilla repetida cada vez que se aplica la misma disposición.
WHATSAPP_TEMPLATES = {
    "No Answer": [
        "Hola, intentamos contactarte desde Salvaguardas Doble B y no fue posible. ¿Hay un mejor horario para llamarte?",
        "Hola, te buscamos hace un momento y no logramos comunicarnos. ¿Cuándo te queda bien que te volvamos a llamar?",
        "Hola, quisimos llamarte desde Salvaguardas Doble B pero no contestaste. Avísanos un horario y te intentamos de nuevo.",
    ],
    "Info Sent": [
        "Hola, te compartimos la información de Consejería Clara sobre {tipo_frase}. Cualquier duda, escríbenos por este medio.",
        "Hola, ya te enviamos los detalles del programa de Consejería Clara para {tipo_frase}. Quedamos atentos a tus preguntas.",
        "Hola, aquí tienes la información que pediste sobre Consejería Clara. Revisa con calma y nos cuentas.",
    ],
    "Transferido": [
        "Hola, un Consejero de Consejería Clara se pondrá en contacto contigo para revisar {tipo_frase}.",
        "Hola, ya transferimos tu caso a un Consejero de Consejería Clara. Te contactará pronto para hablar de {tipo_frase}.",
        "Hola, un Consejero de Consejería Clara va a revisar {tipo_frase} contigo en los próximos días.",
    ],
    "Call Back": [
        "Hola, quedamos en volver a contactarte. Te escribiremos pronto desde Salvaguardas Doble B.",
        "Hola, anotamos que quieres que te contactemos más adelante. Te vamos a escribir en estos días.",
        "Hola, entendido — te contactamos de nuevo pronto desde Salvaguardas Doble B.",
    ],
    "No le interesa": [
        "Entendido, gracias por tu tiempo. Si cambias de opinión, aquí estaremos.",
        "Gracias por avisarnos. No te volveremos a escribir, pero si algo cambia, aquí estamos.",
        "Perfecto, respetamos tu decisión. Si más adelante te interesa, puedes volver a escribirnos.",
    ],
}


def generar_mensaje_whatsapp(disposicion, lead=None):
    tipo_frase = _TIPO_DEUDA_FRASES.get((lead or {}).get("tipo_deuda"), "tu caso")
    plantilla = random.choice(WHATSAPP_TEMPLATES[disposicion])
    return plantilla.format(tipo_frase=tipo_frase) if "{tipo_frase}" in plantilla else plantilla


def _now():
    return datetime.now(timezone.utc).isoformat()


def _notificar_webhook_crm(lead_id, disposicion, forzar_fallo=False):
    """Simula la llamada HTTP al CRM del partner que registra la disposición.
    Con forzar_fallo=True se comporta como un timeout/5xx real, para poder
    probar la resiliencia del sistema a demanda desde la interfaz."""
    if forzar_fallo:
        raise WebhookCRMError(f"Timeout simulado notificando '{disposicion}' para {lead_id}")
    return True


def _notificar_con_reintentos(lead_id, disposicion, forzar_fallo=False, max_reintentos=2):
    """Reintentos automáticos (in-process) ante una falla del webhook, antes
    de darse por vencido y desviar a la cola de fallos. Devuelve
    (ok, intentos_totales, ultimo_error)."""
    intentos = 0
    ultimo_error = None
    while intentos <= max_reintentos:
        intentos += 1
        try:
            _notificar_webhook_crm(lead_id, disposicion, forzar_fallo=forzar_fallo)
            return True, intentos, None
        except WebhookCRMError as e:
            ultimo_error = str(e)
    return False, intentos, ultimo_error


def aplicar_disposicion(lead_id, disposicion, actor="sistema", forzar_fallo_webhook=False):
    timestamp = _now()

    if disposicion not in STAGE_MAP:
        db.encolar_fallo(
            timestamp,
            "disposicion_invalida",
            {"lead_id": lead_id, "disposicion": disposicion},
            f"Disposición desconocida: '{disposicion}'",
        )
        return {"status": "error", "motivo": "disposicion_invalida"}

    lead = db.get_lead(lead_id)
    if lead is None:
        db.encolar_fallo(
            timestamp,
            "lead_no_encontrado",
            {"lead_id": lead_id, "disposicion": disposicion},
            f"Lead '{lead_id}' no existe en la base",
        )
        return {"status": "error", "motivo": "lead_no_encontrado"}

    if disposicion == "Transferido" and not lead.get("telefono"):
        estado_anterior = lead["stage"]
        db.actualizar_stage(lead_id, ETAPA_PENDIENTE_TELEFONO)

        contenido = random.choice(_MENSAJES_PEDIR_TELEFONO)
        draft_id = db.crear_draft(lead_id, timestamp, canal="whatsapp", contenido=contenido)

        db.registrar_audit(
            timestamp, lead_id, actor, "transferencia_sin_telefono",
            estado_anterior, ETAPA_PENDIENTE_TELEFONO,
            f"Teléfono faltante: no se pudo transferir, se dejó borrador pidiendo el dato (draft_id={draft_id})",
        )
        db.log_decision(
            timestamp, lead_id, "escalar_humano",
            "Transferencia sin teléfono válido — se le pidió el dato al lead", draft_id,
        )
        return {"status": "pendiente_dato", "stage": ETAPA_PENDIENTE_TELEFONO, "draft_id": draft_id, "motivo": "telefono_faltante"}

    ok, intentos, ultimo_error = _notificar_con_reintentos(lead_id, disposicion, forzar_fallo=forzar_fallo_webhook)
    if not ok:
        db.encolar_fallo(
            timestamp,
            "webhook_caido",
            {"lead_id": lead_id, "disposicion": disposicion, "actor": actor, "intentos": intentos},
            f"Webhook del CRM externo no respondió tras {intentos} intentos automáticos: {ultimo_error}",
        )
        return {"status": "error", "motivo": "webhook_caido", "intentos_webhook": intentos}

    estado_anterior = lead["stage"]
    nuevo_stage = STAGE_MAP[disposicion]
    db.actualizar_stage(lead_id, nuevo_stage)

    contenido = generar_mensaje_whatsapp(disposicion, lead)
    draft_id = db.crear_draft(lead_id, timestamp, canal="whatsapp", contenido=contenido)

    db.registrar_audit(
        timestamp, lead_id, actor, f"disposicion:{disposicion}",
        estado_anterior, nuevo_stage, f"draft_id={draft_id}, intentos_webhook={intentos}",
    )

    return {"status": "ok", "stage": nuevo_stage, "draft_id": draft_id, "intentos_webhook": intentos}


def reintentar_fallos(max_retries=3):
    """Reintento manual desde la cola de fallos (botón 'Reintentar
    manualmente'). Para 'webhook_caido' vuelve a intentar la disposición
    original de verdad (ya no forzando el fallo, simulando que el CRM
    volvió a responder); para los demás tipos, que no tienen una acción de
    reintento sensata (ej. una disposición inválida sigue siendo inválida),
    solo se cuenta el intento. Tras max_retries sin éxito, se marca
    fallido_permanente."""
    resultados = []
    for fallo in db.listar_fallos_pendientes():
        if fallo["retry_count"] >= max_retries:
            db.marcar_fallo_estado(fallo["id"], "fallido_permanente")
            resultados.append({"id": fallo["id"], "status": "fallido_permanente"})
            continue

        db.incrementar_retry(fallo["id"])
        payload = json.loads(fallo["payload_json"]) if fallo["payload_json"] else {}

        if fallo["tipo"] == "webhook_caido" and payload.get("lead_id") and payload.get("disposicion"):
            r = aplicar_disposicion(payload["lead_id"], payload["disposicion"], actor="reintento_manual")
            if r.get("status") == "ok":
                db.marcar_fallo_estado(fallo["id"], "resuelto")
                resultados.append({"id": fallo["id"], "status": "resuelto", "lead_id": payload["lead_id"]})
                continue

        resultados.append({"id": fallo["id"], "status": "reintentado"})
    return resultados

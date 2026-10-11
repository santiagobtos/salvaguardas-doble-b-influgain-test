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

# Transferido: sin teléfono no hay forma de que el Consejero contacte al
# lead. Call Back: literalmente no se puede "devolver una llamada" sin un
# número al que llamar. Las demás disposiciones no lo necesitan para
# ejecutarse (son mensajes de WhatsApp, no llamadas).
_DISPOSICIONES_REQUIEREN_TELEFONO = {"Transferido", "Call Back"}

_MENSAJES_PEDIR_TELEFONO = [
    "Hola, para seguir con tu caso necesitamos un número de contacto válido. ¿Nos lo compartes?",
    "Hola, nos falta tu número de teléfono para poder avanzar con tu caso. ¿Nos lo compartes cuando puedas?",
    "Hola, antes de seguir necesitamos un teléfono de contacto. ¿Puedes compartirlo por aquí?",
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
# plantilla repetida — y todas referencian el tipo de deuda (y el monto,
# cuando lo dieron) que ya extrajo el agente de pre-calificación de las
# propias palabras del lead, según rules.yaml, para que el mensaje suene
# a que de verdad se leyó su caso y no a una plantilla genérica.
WHATSAPP_TEMPLATES = {
    "No Answer": [
        "Hola, intentamos contactarte desde Salvaguardas Doble B por lo de {tipo_frase}{monto_clause} y no fue posible. ¿Hay un mejor horario para llamarte?",
        "Hola, te buscamos hace un momento para hablar de {tipo_frase}{monto_clause} y no logramos comunicarnos. ¿Cuándo te queda bien que te volvamos a llamar?",
        "Hola, quisimos llamarte desde Salvaguardas Doble B por {tipo_frase}{monto_clause} pero no contestaste. Avísanos un horario y te intentamos de nuevo.",
    ],
    "Info Sent": [
        "Hola, te compartimos la información de Consejería Clara sobre {tipo_frase}{monto_clause}. Cualquier duda, escríbenos por este medio.",
        "Hola, ya te enviamos los detalles del programa de Consejería Clara para {tipo_frase}{monto_clause}. Quedamos atentos a tus preguntas.",
        "Hola, aquí tienes la información que pediste sobre {tipo_frase}{monto_clause}. Revisa con calma y nos cuentas.",
    ],
    "Transferido": [
        "Hola, un Consejero de Consejería Clara se pondrá en contacto contigo para revisar {tipo_frase}{monto_clause}.",
        "Hola, ya transferimos tu caso a un Consejero de Consejería Clara. Te contactará pronto para hablar de {tipo_frase}{monto_clause}.",
        "Hola, un Consejero de Consejería Clara va a revisar {tipo_frase}{monto_clause} contigo en los próximos días.",
    ],
    "Call Back": [
        "Hola, quedamos en volver a contactarte por lo de {tipo_frase}{monto_clause}. Te escribiremos pronto desde Salvaguardas Doble B.",
        "Hola, anotamos que quieres que te contactemos más adelante para seguir hablando de {tipo_frase}{monto_clause}. Te vamos a escribir en estos días.",
        "Hola, entendido — te contactamos de nuevo pronto para lo de {tipo_frase}{monto_clause}.",
    ],
    "No le interesa": [
        "Entendido, no seguimos con lo de {tipo_frase}{monto_clause}. Gracias por tu tiempo — si cambias de opinión, aquí estaremos.",
        "Gracias por avisarnos. No te volveremos a escribir por lo de {tipo_frase}{monto_clause}, pero si algo cambia, aquí estamos.",
        "Perfecto, respetamos tu decisión sobre {tipo_frase}{monto_clause}. Si más adelante te interesa, puedes volver a escribirnos.",
    ],
}


def _frase_monto(lead):
    monto = (lead or {}).get("monto_deuda")
    if not monto:
        return ""
    monto_fmt = f"${monto:,}".replace(",", ".")
    return f" (nos comentaste un monto cercano a {monto_fmt})"


def generar_mensaje_whatsapp(disposicion, lead=None):
    lead = lead or {}
    tipo_frase = _TIPO_DEUDA_FRASES.get(lead.get("tipo_deuda"), "tu caso")
    monto_clause = _frase_monto(lead)
    plantilla = random.choice(WHATSAPP_TEMPLATES[disposicion])
    return plantilla.format(tipo_frase=tipo_frase, monto_clause=monto_clause)


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

    # Regla dura: "nunca publica ni transfiere solo". Si hay un borrador sin
    # revisar (pending_review) para este lead, no se deja aplicar ninguna
    # disposición hasta que un humano lo apruebe o lo descarte — así nunca
    # se acumulan mensajes sin revisar ni se avanza un lead "a ciegas".
    borrador_pendiente = next(
        (d for d in db.listar_drafts() if d["lead_id"] == lead_id and d["status"] == "pending_review"),
        None,
    )
    if borrador_pendiente:
        return {
            "status": "borrador_pendiente",
            "motivo": "borrador_sin_revisar",
            "draft_id": borrador_pendiente["draft_id"],
        }

    if disposicion in _DISPOSICIONES_REQUIEREN_TELEFONO and not lead.get("telefono"):
        estado_anterior = lead["stage"]
        db.actualizar_stage(lead_id, ETAPA_PENDIENTE_TELEFONO)
        db.set_disposicion_pendiente(lead_id, disposicion)

        contenido = random.choice(_MENSAJES_PEDIR_TELEFONO)
        draft_id = db.crear_draft(lead_id, timestamp, canal="whatsapp", contenido=contenido, tipo="pedir_telefono")

        db.registrar_audit(
            timestamp, lead_id, actor, "disposicion_requiere_telefono",
            estado_anterior, ETAPA_PENDIENTE_TELEFONO,
            f"Teléfono faltante: no se pudo aplicar '{disposicion}', se dejó borrador pidiendo el dato (draft_id={draft_id})",
        )
        db.log_decision(
            timestamp, lead_id, "escalar_humano",
            f"'{disposicion}' sin teléfono válido — se le pidió el dato al lead", draft_id,
        )
        return {
            "status": "pendiente_dato", "stage": ETAPA_PENDIENTE_TELEFONO, "draft_id": draft_id,
            "motivo": "telefono_faltante", "disposicion_pendiente": disposicion,
        }

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
    if lead.get("disposicion_pendiente"):
        db.set_disposicion_pendiente(lead_id, None)

    contenido = generar_mensaje_whatsapp(disposicion, lead)
    draft_id = db.crear_draft(lead_id, timestamp, canal="whatsapp", contenido=contenido, tipo="disposicion")

    db.registrar_audit(
        timestamp, lead_id, actor, f"disposicion:{disposicion}",
        estado_anterior, nuevo_stage, f"draft_id={draft_id}, intentos_webhook={intentos}",
    )

    return {"status": "ok", "stage": nuevo_stage, "draft_id": draft_id, "intentos_webhook": intentos}


def corregir_disposicion_invalida(fallo_id, lead_id, nueva_disposicion, actor="humano"):
    """Para un fallo de tipo 'disposicion_invalida': reintentar a ciegas no
    sirve de nada porque el valor inválido original sigue siendo inválido
    para siempre — hace falta que un humano lo corrija aquí. Si la
    disposición corregida sí se puede aplicar, el fallo se marca resuelto
    en vez de seguir sumando reintentos inútiles."""
    r = aplicar_disposicion(lead_id, nueva_disposicion, actor=actor)
    if r["status"] in ("ok", "pendiente_dato", "escalado"):
        db.marcar_fallo_estado(fallo_id, "resuelto")
    return r


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

"""Ejercicio B: automatización tipo CRM sobre disposiciones de un lead.

Disposiciones soportadas: No Answer | Info Sent | Transferido | Call Back |
No le interesa. Cada una mueve la etapa del lead, genera un borrador de
WhatsApp compliant, y deja audit trail. Los errores van a una cola de
fallos con reintento, nunca se pierden en silencio.
"""
import random
from datetime import datetime, timezone

from src import db

STAGE_MAP = {
    "No Answer": "Sin Respuesta",
    "Info Sent": "Info Enviada",
    "Transferido": "Transferido a Consejero",
    "Call Back": "Reintentar Contacto",
    "No le interesa": "Cerrado - Sin Interés",
}

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


def aplicar_disposicion(lead_id, disposicion, actor="sistema"):
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
        db.registrar_audit(
            timestamp, lead_id, actor, "intento_transferencia_sin_telefono",
            lead["stage"], lead["stage"], "Teléfono faltante: se escala a revisión manual",
        )
        db.log_decision(timestamp, lead_id, "escalar_humano", "Transferencia sin teléfono válido", None)
        return {"status": "escalado", "motivo": "telefono_faltante"}

    estado_anterior = lead["stage"]
    nuevo_stage = STAGE_MAP[disposicion]
    db.actualizar_stage(lead_id, nuevo_stage)

    contenido = generar_mensaje_whatsapp(disposicion, lead)
    draft_id = db.crear_draft(lead_id, timestamp, canal="whatsapp", contenido=contenido)

    db.registrar_audit(
        timestamp, lead_id, actor, f"disposicion:{disposicion}",
        estado_anterior, nuevo_stage, f"draft_id={draft_id}",
    )

    return {"status": "ok", "stage": nuevo_stage, "draft_id": draft_id}


def simular_fallo_webhook(payload, error_msg="Webhook caído (simulado)"):
    """Para la demo: simula que el webhook del CRM externo no respondió."""
    db.encolar_fallo(_now(), "webhook_caido", payload, error_msg)


def reintentar_fallos(max_retries=3):
    """Reintenta los fallos pendientes. Tras max_retries pasan a fallido_permanente."""
    resultados = []
    for fallo in db.listar_fallos_pendientes():
        if fallo["retry_count"] >= max_retries:
            db.marcar_fallo_estado(fallo["id"], "fallido_permanente")
            resultados.append({"id": fallo["id"], "status": "fallido_permanente"})
            continue
        db.incrementar_retry(fallo["id"])
        resultados.append({"id": fallo["id"], "status": "reintentado"})
    return resultados

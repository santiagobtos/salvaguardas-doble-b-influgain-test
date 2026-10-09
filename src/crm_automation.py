"""Ejercicio B: automatización tipo CRM sobre disposiciones de un lead.

Disposiciones soportadas: No Answer | Info Sent | Transferido | Call Back |
No le interesa. Cada una mueve la etapa del lead, genera un borrador de
WhatsApp compliant, y deja audit trail. Los errores van a una cola de
fallos con reintento, nunca se pierden en silencio.
"""
from datetime import datetime, timezone

from src import db

STAGE_MAP = {
    "No Answer": "Sin Respuesta",
    "Info Sent": "Info Enviada",
    "Transferido": "Transferido a Consejero",
    "Call Back": "Reintentar Contacto",
    "No le interesa": "Cerrado - Sin Interés",
}

# Lenguaje compliant: nunca "asesor", nunca promesas de ahorro.
WHATSAPP_TEMPLATES = {
    "No Answer": "Hola, intentamos contactarte desde Salvaguardas Doble B y no fue posible. ¿Hay un mejor horario para llamarte?",
    "Info Sent": "Hola, te compartimos la información de Consejería Clara. Cualquier duda, escríbenos por este medio.",
    "Transferido": "Hola, un Consejero de Consejería Clara se pondrá en contacto contigo para revisar tu caso.",
    "Call Back": "Hola, quedamos en volver a contactarte. Te escribiremos pronto desde Salvaguardas Doble B.",
    "No le interesa": "Entendido, gracias por tu tiempo. Si cambias de opinión, aquí estaremos.",
}


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

    contenido = WHATSAPP_TEMPLATES[disposicion]
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

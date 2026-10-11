"""API HTTP + dashboard de la demo. Todo local, sin servicios externos.

Correr: uvicorn webhook_server:app --reload
Dashboard visual: http://127.0.0.1:8000/
Docs interactivas de la API: http://127.0.0.1:8000/docs
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src import crm_automation, db, reporting
from src.content_system import generar_guiones
from src.prequalification_agent import procesar_mensaje_entrante

app = FastAPI(title="Salvaguardas Doble B — demo técnica Influgain")
db.init_db()

DASHBOARD_HTML = Path(__file__).resolve().parent / "static" / "dashboard.html"

# Leads de ejemplo para poblar el dashboard con un solo clic ("Cargar demo").
# Pasan por el agente real (Ejercicio A), no son datos falseados en la UI.
SEED_LEADS = [
    ("D001", "@carla.finanzas", "CTWA", "Hola, tengo una deuda de tarjeta de credito de 4200000, quiero hablar con un consejero", "3001112201"),
    ("D002", "@juanfi_libre", "organico", "Me llego una demanda por mi tarjeta, que hago", "3001112202"),
    ("D003", "@manu.deudas", "CTWA", "No me interesa, quitame de esta lista", "3001112203"),
    ("D004", "@laura_consejos", "organico", "Debo libranza por 9000000, quiero informacion del programa", "3001112204"),
    ("D005", "@pedro.ahorra", "CTWA", "Buenas, debo como 15000000 en varias deudas, me pueden ayudar?", "3001112205"),
    ("D006", "@carla.finanzas", "organico", "Hola quiero mas informacion sobre el programa", "3001112206"),
]
SEED_DISPOSICIONES = [("D001", "Transferido"), ("D004", "Info Sent"), ("D005", "Call Back")]


class LeadIn(BaseModel):
    lead_id: str
    creador: str
    canal: str
    mensaje: str
    telefono: Optional[str] = None


class DisposicionIn(BaseModel):
    lead_id: str
    disposicion: str
    actor: str = "sistema"


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML.read_text(encoding="utf-8")


@app.get("/api/status")
def api_status():
    return {"status": "ok", "docs": "/docs"}


@app.post("/webhook/lead")
def webhook_lead(lead: LeadIn):
    """Ejercicio A: ingesta y clasifica un mensaje nuevo."""
    return procesar_mensaje_entrante(
        lead_id=lead.lead_id, creador=lead.creador, canal=lead.canal,
        mensaje=lead.mensaje, telefono=lead.telefono,
    )


@app.get("/crm/leads")
def crm_leads():
    return db.listar_leads()


@app.get("/crm/drafts")
def crm_drafts(status: Optional[str] = None):
    return db.listar_drafts(status)


@app.post("/crm/disposition")
def crm_disposition(disp: DisposicionIn):
    """Ejercicio B: aplica una disposición de CRM."""
    return crm_automation.aplicar_disposicion(disp.lead_id, disp.disposicion, disp.actor)


@app.get("/crm/failed-queue")
def crm_failed_queue():
    return db.listar_fallos_pendientes()


@app.post("/crm/failed-queue/retry")
def crm_retry_failed(max_retries: int = 3):
    return crm_automation.reintentar_fallos(max_retries)


@app.post("/demo/seed")
def demo_seed():
    """Resetea la base y carga leads de ejemplo para que el dashboard no empiece vacío."""
    db.reset_db()
    for lead_id, creador, canal, mensaje, telefono in SEED_LEADS:
        procesar_mensaje_entrante(lead_id, creador, canal, mensaje, telefono)
    for lead_id, disposicion in SEED_DISPOSICIONES:
        crm_automation.aplicar_disposicion(lead_id, disposicion)
    crm_automation.aplicar_disposicion("D999", "Info Sent")  # fuerza un fallo de ejemplo en la cola
    return {"status": "ok", "leads_cargados": len(SEED_LEADS)}


@app.get("/reporting/funnel")
def reporting_funnel():
    """Ejercicio C: métricas de funnel sobre los CSV fixture."""
    return reporting.calcular_funnel()


@app.get("/reporting/stalled-leads")
def reporting_stalled():
    return reporting.leads_estancados()


@app.get("/reporting/commission-breaks")
def reporting_commission_breaks():
    return reporting.reporte_ruptura_comisiones()


@app.get("/content/scripts")
def content_scripts():
    """Ejercicio D: guiones priorizados, con evidencia de leads reales."""
    return generar_guiones()

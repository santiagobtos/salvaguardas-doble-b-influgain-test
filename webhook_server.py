"""API HTTP de la demo. Todo local, sin servicios externos.

Correr: uvicorn webhook_server:app --reload
Docs interactivas: http://127.0.0.1:8000/docs
"""
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from src import crm_automation, db, reporting
from src.content_system import generar_guiones
from src.prequalification_agent import procesar_mensaje_entrante

app = FastAPI(title="Salvaguardas Doble B — demo técnica Influgain")
db.init_db()


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


@app.post("/webhook/lead")
def webhook_lead(lead: LeadIn):
    """Ejercicio A: ingesta y clasifica un mensaje nuevo."""
    return procesar_mensaje_entrante(
        lead_id=lead.lead_id, creador=lead.creador, canal=lead.canal,
        mensaje=lead.mensaje, telefono=lead.telefono,
    )


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
def content_scripts(top_n: int = 3):
    """Ejercicio D: guiones priorizados."""
    return generar_guiones(top_n)


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}

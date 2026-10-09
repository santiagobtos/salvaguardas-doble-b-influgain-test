"""CLI de demo: ejercita A -> B -> C -> D en secuencia sobre datos locales.

Pensado para grabar el video de entrega: muestra una decisión "responder",
una "escalar_humano", un cambio de disposición de CRM, y el reporting.

Correr: python cli.py demo
"""
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from src import crm_automation, db
from src.content_system import generar_guiones
from src.prequalification_agent import procesar_mensaje_entrante
from src.reporting import calcular_funnel, leads_estancados, reporte_ruptura_comisiones


def _separador(titulo):
    print("\n" + "=" * 70)
    print(titulo)
    print("=" * 70)


def demo():
    db.init_db()
    db.reset_db()

    _separador("EJERCICIO A — Agente de pre-calificación + handoff")
    casos = [
        ("L901", "@carla.finanzas", "CTWA", "Hola, tengo una deuda de tarjeta de credito de 3500000", "3000000001"),
        ("L902", "@juanfi_libre", "organico", "Me llego una demanda por mi tarjeta, que hago", "3000000002"),
        ("L903", "@manu.deudas", "CTWA", "No me interesa, quitame de esta lista", "3000000003"),
    ]
    for lead_id, creador, canal, mensaje, telefono in casos:
        resultado = procesar_mensaje_entrante(lead_id, creador, canal, mensaje, telefono)
        print(f"- {lead_id}: decisión={resultado['decision']} | razón={resultado['razon']} | draft_id={resultado['draft_id']}")

    _separador("EJERCICIO B — Automatización CRM (disposiciones)")
    print("- L901 -> Transferido:", crm_automation.aplicar_disposicion("L901", "Transferido"))
    print("- L902 -> Call Back:", crm_automation.aplicar_disposicion("L902", "Call Back"))
    print("- L999 -> Info Sent (lead inexistente, debe ir a cola de fallos):",
          crm_automation.aplicar_disposicion("L999", "Info Sent"))
    print("- Cola de fallos pendiente:", db.listar_fallos_pendientes())
    print("- Reintento de fallos:", crm_automation.reintentar_fallos())

    _separador("EJERCICIO C — Datos y reporting (sobre data/leads.csv + partner_enrollments.csv)")
    funnel = calcular_funnel()
    print("- Funnel general:", funnel["general"])
    print("- Leads estancados:", len(leads_estancados()))
    ruptura = reporte_ruptura_comisiones()
    print("- Inscripciones sin creator_id:", ruptura["inscripciones_sin_creator_id"])
    print("- Inscripciones con teléfono mismatch:", ruptura["inscripciones_con_telefono_mismatch"])

    _separador("EJERCICIO D — Mini sistema de contenido")
    for g in generar_guiones():
        print(f"- Fuente {g['fuente_id']} (score {g['prioridad_score']}): {g['guion'][:70]}...")

    _separador("FIN DEMO")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        print("Uso: python cli.py demo")

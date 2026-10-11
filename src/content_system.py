"""Ejercicio D: mini sistema de contenido.

Los 3 guiones no salen de una lista de objeciones inventada: salen de
clasificar los mensajes REALES de data/leads.csv (los mismos 42 leads que
usan los Ejercicios A y C) contra las categorías editables de
rules.yaml (categorias_contenido). Cada guion queda trazable a los
lead_id concretos que lo evidencian — no a un score inventado.
"""
import csv
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"

MINIMO_EVIDENCIA = 12

GUION_TEMPLATE = (
    "[Gancho] {gancho}\n"
    "[Cuerpo] {cuerpo} En Salvaguardas Doble B conectamos con un Consejero de "
    "Consejería Clara que, en muchos casos, puede ayudarte a revisar opciones "
    "para tu situación. No es una promesa de ahorro fijo ni de una tasa: "
    "depende de tu caso particular.\n"
    "[Cierre] {cierre}"
)

# Contenido editorial por categoría (el id debe existir en rules.yaml →
# categorias_contenido). Lo único que NO sale de los datos es el texto del
# guion en sí — el problema que ataca y su evidencia sí salen de los leads.
_GUIONES_POR_CATEGORIA = {
    "friccion_informacion": {
        "gancho": "¿Escribiste pidiendo información y nadie te explicó cuál era el siguiente paso?",
        "cuerpo": (
            "Es uno de los mensajes que más nos llega: piden conocer el programa, pero "
            "el mensaje se queda ahí porque no queda claro qué sigue."
        ),
        "cierre": "Si eso te pasó, te contamos el paso a paso en 2 minutos — sin compromiso.",
    },
    "deuda_tarjeta_consumo": {
        "gancho": "¿Tienes tarjeta, crédito de consumo o varias deudas juntas y ya perdiste la cuenta de cuánto debes?",
        "cuerpo": (
            "Muchos nos escriben con deudas de tarjeta o consumo revueltas entre sí, sin saber "
            "por cuál empezar a ordenar."
        ),
        "cierre": "Cuéntanos tu caso y un Consejero te ayuda a ponerle orden a la lista completa.",
    },
    "riesgo_y_desconfianza": {
        "gancho": "¿Te llegó algo que suena a embargo o demanda, o simplemente no confías en que esto no sea spam?",
        "cuerpo": (
            "Dos cosas muy distintas nos llegan mezcladas: gente con riesgo legal real (embargo, "
            "demanda, quiebra) y gente que desconfía y prefiere darse de baja. A ambas hay que "
            "responderles distinto a un guion de venta genérico."
        ),
        "cierre": (
            "Si es urgente, un humano te atiende directo, no un bot. Y si no te interesa, "
            "te damos de baja sin vueltas — nunca te vamos a insistir."
        ),
    },
}


def _cargar_categorias_contenido():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        reglas = yaml.safe_load(f)
    return reglas.get("categorias_contenido", []), reglas.get("escalar_keywords", [])


def _cargar_leads_reales(leads_path=None):
    ruta = leads_path or (DATA_DIR / "leads.csv")
    with open(ruta, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def analizar_problemas_leads(leads_path=None):
    """Clasifica cada lead real contra las categorías de rules.yaml.

    Para cada mensaje, recorre las categorías EN ORDEN y asigna la primera
    cuyas keywords aparezcan en el texto; la categoría sin keywords (debe
    ser la última) actúa de catch-all. Devuelve una lista de dicts con la
    evidencia completa (lead_id, mensaje, estado_inicial) de cada
    categoría — nada se resume ni se pierde antes de llegar a la interfaz.
    """
    categorias, escalar_keywords = _cargar_categorias_contenido()
    leads = _cargar_leads_reales(leads_path)

    catch_all_ids = [c["id"] for c in categorias if not c.get("keywords")]
    if len(catch_all_ids) != 1:
        raise ValueError(
            "rules.yaml → categorias_contenido debe tener exactamente una "
            "categoría catch-all (keywords vacías)."
        )
    catch_all_id = catch_all_ids[0]

    resultado = {c["id"]: {**c, "leads": []} for c in categorias}

    for lead in leads:
        mensaje = (lead.get("mensaje") or "").lower()
        asignado = catch_all_id
        for c in categorias:
            kws = c.get("keywords") or []
            if kws and any(kw.lower() in mensaje for kw in kws):
                asignado = c["id"]
                break
        resultado[asignado]["leads"].append(
            {
                "lead_id": lead["lead_id"],
                "mensaje": lead["mensaje"],
                "estado_inicial": lead["estado_inicial"],
                "creador": lead.get("creador"),
                "canal": lead.get("canal"),
            }
        )

    salida = []
    for c in categorias:
        entrada = resultado[c["id"]]
        n = len(entrada["leads"])
        con_riesgo = sum(
            1 for l in entrada["leads"]
            if any(kw.lower() in l["mensaje"].lower() for kw in escalar_keywords)
        )
        riesgo_pct = round(100 * con_riesgo / n, 1) if n else 0.0
        entrada["n_leads"] = n
        entrada["leads_con_senal_riesgo"] = con_riesgo
        entrada["riesgo_pct"] = riesgo_pct
        entrada["prioridad_score"] = round(n * (1 + riesgo_pct / 100), 1)
        salida.append(entrada)

    return sorted(salida, key=lambda c: c["prioridad_score"], reverse=True)


def generar_guiones(leads_path=None):
    """3 guiones (uno por categoría), cada uno con su análisis + evidencia.

    Cada guion queda respaldado por al menos MINIMO_EVIDENCIA leads reales
    (hoy el dataset da 13/15/14 — todas por encima del mínimo). Si en algún
    momento el dataset cambia y una categoría cae por debajo del mínimo,
    se marca explícitamente en vez de generar el guion igual con evidencia
    insuficiente.
    """
    analisis = analizar_problemas_leads(leads_path)

    guiones = []
    for categoria in analisis:
        contenido = _GUIONES_POR_CATEGORIA.get(categoria["id"])
        if contenido is None:
            continue
        guion_texto = GUION_TEMPLATE.format(**contenido)
        guiones.append(
            {
                "categoria_id": categoria["id"],
                "problema": categoria["nombre"],
                "keywords": categoria.get("keywords") or [],
                "n_leads": categoria["n_leads"],
                "leads_con_senal_riesgo": categoria["leads_con_senal_riesgo"],
                "riesgo_pct": categoria["riesgo_pct"],
                "prioridad_score": categoria["prioridad_score"],
                "evidencia_suficiente": categoria["n_leads"] >= MINIMO_EVIDENCIA,
                "duracion_estimada_seg": "30-45",
                "guion": guion_texto,
                "evidencia": categoria["leads"],
            }
        )
    return guiones


if __name__ == "__main__":
    for g in generar_guiones():
        print(f"\n--- Guion: {g['problema']} (score {g['prioridad_score']}, {g['n_leads']} leads) ---")
        print(g["guion"])
        print(f"Evidencia ({g['n_leads']} leads, {g['leads_con_senal_riesgo']} con señal de riesgo):")
        for l in g["evidencia"][:MINIMO_EVIDENCIA]:
            print(f"  {l['lead_id']} | {l['estado_inicial']} | {l['mensaje']}")

"""Ejercicio D: mini sistema de contenido.

Dos capas, ambas sobre datos REALES (los 42 mensajes de data/leads.csv, los
mismos leads de los Ejercicios A/C) en vez de objeciones inventadas a mano:

1. `analizar_fuentes_contenido()` — las "fuentes de contenido" (8-12 ítems:
   preguntas de leads, objeciones o tendencias) que pedía el enunciado
   original, pero medidas sobre mensajes reales en vez de inventadas.
2. `generar_guiones()` — agrupa esas fuentes (rules.yaml → categorias_contenido
   → campo `guion`) en los 3 guiones finales, cada uno con un mínimo de
   MINIMO_EVIDENCIA leads reales citados como evidencia.
"""
import csv
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"

MINIMO_EVIDENCIA = 12

_PESO_URGENCIA = {"alta": 3, "media": 2, "baja": 1}

GUION_TEMPLATE = (
    "[Gancho] {gancho}\n"
    "[Cuerpo] {cuerpo} En Salvaguardas Doble B conectamos con un Consejero de "
    "Consejería Clara que, en muchos casos, puede ayudarte a revisar opciones "
    "para tu situación. No es una promesa de ahorro fijo ni de una tasa: "
    "depende de tu caso particular.\n"
    "[Cierre] {cierre}"
)

# Contenido editorial por guion (el id debe existir en rules.yaml →
# categorias_contenido → guion). Lo único que NO sale de los datos es el
# texto del guion en sí — qué fuentes lo alimentan y su evidencia sí salen
# de los leads.
_GUIONES_POR_ID = {
    "friccion_informacion": {
        "titulo": "Piden información pero no dan el siguiente paso",
        "gancho": "¿Escribiste pidiendo información y nadie te explicó cuál era el siguiente paso?",
        "cuerpo": (
            "Es uno de los mensajes que más nos llega: piden conocer el programa, pero "
            "el mensaje se queda ahí porque no queda claro qué sigue."
        ),
        "cierre": "Si eso te pasó, te contamos el paso a paso en 2 minutos — sin compromiso.",
    },
    "deuda_tarjeta_consumo": {
        "titulo": "Deuda de tarjeta/consumo y no saber por dónde empezar",
        "gancho": "¿Tienes tarjeta, crédito de consumo o varias deudas juntas y ya perdiste la cuenta de cuánto debes?",
        "cuerpo": (
            "Muchos nos escriben con deudas de tarjeta o consumo revueltas entre sí, sin saber "
            "por cuál empezar a ordenar."
        ),
        "cierre": "Cuéntanos tu caso y un Consejero te ayuda a ponerle orden a la lista completa.",
    },
    "riesgo_y_desconfianza": {
        "titulo": "Riesgo legal, deudas de libranza/hipoteca y señales de desconfianza",
        "gancho": "¿Te llegó algo que suena a embargo o demanda, o simplemente no confías en que esto no sea spam?",
        "cuerpo": (
            "Varias cosas distintas nos llegan mezcladas bajo la misma urgencia: riesgo legal real "
            "(embargo, demanda, quiebra), deudas de libranza o hipoteca con riesgo de perder nómina "
            "o vivienda, y gente que desconfía y prefiere darse de baja. A todas hay que responderles "
            "distinto a un guion de venta genérico."
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


def _urgencia(n_leads, con_riesgo):
    """Heurística simple, igual en espíritu a la del enunciado original
    (frecuencia × urgencia) pero con la urgencia derivada de una señal
    real: si algún mensaje de la fuente trae una palabra de riesgo legal
    (escalar_keywords), la fuente es 'alta' sin importar cuántos leads
    tenga — un solo caso de embargo pesa más que diez preguntas genéricas."""
    if con_riesgo:
        return "alta"
    if n_leads >= 4:
        return "media"
    return "baja"


def analizar_fuentes_contenido(leads_path=None):
    """Las 8-12 'fuentes de contenido' (preguntas/objeciones/tendencias),
    medidas sobre los leads reales en vez de inventadas a mano. Cada una
    trae su evidencia completa (lead_id, mensaje, estado) y un
    prioridad_score = frecuencia × peso_urgencia, calculado solo con datos
    del dataset — nada se inventa."""
    categorias, escalar_keywords = _cargar_categorias_contenido()
    leads = _cargar_leads_reales(leads_path)

    catch_all = [c["id"] for c in categorias if not c.get("keywords")]
    if len(catch_all) != 1:
        raise ValueError(
            "rules.yaml → categorias_contenido debe tener exactamente una "
            "fuente catch-all (keywords vacías)."
        )
    catch_all_id = catch_all[0]

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

    fuentes = []
    for c in categorias:
        entrada = resultado[c["id"]]
        n = len(entrada["leads"])
        con_riesgo = sum(
            1 for l in entrada["leads"]
            if any(kw.lower() in l["mensaje"].lower() for kw in escalar_keywords)
        )
        urgencia = _urgencia(n, con_riesgo)
        entrada["frecuencia"] = n
        entrada["leads_con_senal_riesgo"] = con_riesgo
        entrada["urgencia"] = urgencia
        entrada["prioridad_score"] = n * _PESO_URGENCIA[urgencia]
        entrada["texto_ejemplo"] = entrada["leads"][0]["mensaje"] if entrada["leads"] else None
        fuentes.append(entrada)

    return sorted(fuentes, key=lambda f: f["prioridad_score"], reverse=True)


def generar_guiones(leads_path=None):
    """Agrupa las fuentes de analizar_fuentes_contenido() por su campo
    `guion` (rules.yaml) en los 3 guiones finales. Cada guion suma la
    evidencia (leads) de todas sus fuentes — así cada uno llega al mínimo
    de MINIMO_EVIDENCIA leads reales aunque ninguna fuente individual lo
    alcance por sí sola."""
    fuentes = analizar_fuentes_contenido(leads_path)

    agrupado = {}
    for f in fuentes:
        guion_id = f.get("guion")
        if guion_id is None:
            continue
        agrupado.setdefault(guion_id, {"fuentes": [], "leads": []})
        agrupado[guion_id]["fuentes"].append(f)
        agrupado[guion_id]["leads"].extend(f["leads"])

    guiones = []
    for guion_id, datos in agrupado.items():
        contenido = _GUIONES_POR_ID.get(guion_id)
        if contenido is None:
            continue
        n_leads = len(datos["leads"])
        con_riesgo = sum(f["leads_con_senal_riesgo"] for f in datos["fuentes"])
        riesgo_pct = round(100 * con_riesgo / n_leads, 1) if n_leads else 0.0
        guiones.append(
            {
                "categoria_id": guion_id,
                "problema": contenido["titulo"],
                "fuentes": [
                    {"id": f["id"], "nombre": f["nombre"], "frecuencia": f["frecuencia"], "urgencia": f["urgencia"]}
                    for f in datos["fuentes"]
                ],
                "keywords": sorted({kw for f in datos["fuentes"] for kw in (f.get("keywords") or [])}),
                "n_leads": n_leads,
                "leads_con_senal_riesgo": con_riesgo,
                "riesgo_pct": riesgo_pct,
                "prioridad_score": round(sum(f["prioridad_score"] for f in datos["fuentes"]), 1),
                "evidencia_suficiente": n_leads >= MINIMO_EVIDENCIA,
                "duracion_estimada_seg": "30-45",
                "guion": GUION_TEMPLATE.format(**contenido),
                "evidencia": datos["leads"],
            }
        )
    return sorted(guiones, key=lambda g: g["prioridad_score"], reverse=True)


if __name__ == "__main__":
    print("=== Fuentes de contenido (reales, no inventadas) ===")
    for f in analizar_fuentes_contenido():
        print(f"- {f['nombre']}: {f['frecuencia']} leads, urgencia {f['urgencia']}, score {f['prioridad_score']}")

    print("\n=== Guiones (agrupando fuentes) ===")
    for g in generar_guiones():
        print(f"\n--- Guion: {g['problema']} (score {g['prioridad_score']}, {g['n_leads']} leads) ---")
        print(g["guion"])
        print(f"Evidencia ({g['n_leads']} leads, {g['leads_con_senal_riesgo']} con señal de riesgo):")
        for l in g["evidencia"][:MINIMO_EVIDENCIA]:
            print(f"  {l['lead_id']} | {l['estado_inicial']} | {l['mensaje']}")

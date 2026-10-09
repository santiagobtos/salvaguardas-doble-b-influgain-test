"""Ejercicio D: mini sistema de contenido.

Toma fuentes (preguntas/objeciones/tendencias ficticias de leads) y genera
guiones cortos (30-45s) priorizados, cada uno trazable a su fuente.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

GUION_TEMPLATE = (
    "[Gancho] {gancho}\n"
    "[Cuerpo] Mucha gente con {tema} nos escribe por lo mismo: {detalle} "
    "En Salvaguardas Doble B conectamos con un Consejero de Consejería Clara que, "
    "en muchos casos, puede ayudarte a revisar opciones para tu situación. "
    "No es una promesa de ahorro, depende de tu caso particular.\n"
    "[Cierre] Si te pasa esto, escríbenos y te contamos cómo funciona."
)


def _cargar_fuentes():
    with open(DATA_DIR / "content_sources.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _prioridad(fuente):
    """Heurística simple: frecuencia reportada x peso de urgencia."""
    peso_urgencia = {"alta": 3, "media": 2, "baja": 1}
    return fuente.get("frecuencia", 0) * peso_urgencia.get(fuente.get("urgencia", "baja"), 1)


def generar_guiones(top_n=3):
    fuentes = _cargar_fuentes()
    fuentes_ordenadas = sorted(fuentes, key=_prioridad, reverse=True)

    guiones = []
    for fuente in fuentes_ordenadas[:top_n]:
        guion = GUION_TEMPLATE.format(
            gancho=fuente["texto"],
            tema=fuente.get("tema", "deudas"),
            detalle=fuente.get("detalle", fuente["texto"]),
        )
        guiones.append(
            {
                "fuente_id": fuente["id"],
                "prioridad_score": _prioridad(fuente),
                "duracion_estimada_seg": "30-45",
                "guion": guion,
            }
        )
    return guiones


if __name__ == "__main__":
    for g in generar_guiones():
        print(f"\n--- Guion (fuente {g['fuente_id']}, score {g['prioridad_score']}) ---")
        print(g["guion"])

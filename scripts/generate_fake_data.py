"""Genera los datasets ficticios usados por la demo y el reporting.

Reproducible (seed fija). No usa ninguna API ni dato real: todo inventado.
Correr: python scripts/generate_fake_data.py

El estado inicial de cada lead (Respondido/Escalado/Ignorado) no se
asigna al azar: se calcula pasando el mensaje de verdad por el mismo
motor de reglas que usa el Ejercicio A en vivo (src/rules_engine +
rules/rules.yaml) — así data/leads.csv refleja lo que el agente real
decidiría, no una etiqueta inventada aparte.
"""
import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.rules_engine import clasificar_mensaje, load_rules  # noqa: E402

random.seed(42)

DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

CREADORES = ["@carla.finanzas", "@juanfi_libre", "@manu.deudas", "@laura_consejos", "@pedro.ahorra"]
CANALES = ["CTWA", "organico"]

MENSAJES_NORMALES = [
    "Hola, tengo una deuda de tarjeta de credito de 3500000 y no se que hacer",
    "Buenas, debo libranza por 12000000, quiero informacion del programa",
    "Hola quiero saber si me pueden ayudar con mi credito de consumo de 7800000",
    "Me interesa el programa, tengo una deuda hipotecaria de 45000000",
    "Hola vi el video, debo como 2200000 en tarjeta, quiero hablar con un consejero",
    "Buenas tardes, tengo varias deudas y no sé por dónde empezar, suman 15000000",
    "Hola, quiero asesoria para mi libranza de nomina de 9000000",
    "Me pueden dar informacion sobre el programa de consejeria",
]
MENSAJES_ESCALAR = [
    "Me llego una demanda por mi tarjeta de credito, que hago",
    "Un abogado me contacto por el embargo de mi cuenta, estoy muy preocupado",
    "Esto es urgente, me amenazan con quitarme la casa",
    "Quiero denunciar un fraude con mi tarjeta",
    "La empresa esta en quiebra y no se que hacer con mis deudas",
]
MENSAJES_IGNORAR = [
    "No me interesa, quitame de esta lista por favor",
    "Stop, no quiero recibir mas mensajes",
    "Dejen de escribirme, es spam",
    "Dame de baja, no vuelvan a escribirme",
]
MENSAJES_SIN_MONTO = [
    "Hola, quiero mas informacion sobre el programa",
    "Buenas, como funciona la consejeria de ustedes",
    "Hola vi el anuncio, me pueden contar mas",
]

# "Nuevo" es el único estado que NO sale del motor de reglas: representa
# un lead que llegó pero todavía nadie (ni el agente) lo ha procesado,
# así que una fracción se deja así a propósito en vez de clasificarlo.
PROB_NUEVO_SIN_PROCESAR = 5 / 14  # misma proporción que tenía el peso viejo

_DECISION_A_ESTADO = {
    "responder": "Respondido",
    "escalar_humano": "Escalado",
    "ignorar": "Ignorado",
}


def _telefono_falso(i):
    return f"300{i:07d}"


def _fecha_aleatoria(dias_atras_max=12):
    dias = random.randint(0, dias_atras_max)
    horas = random.randint(0, 23)
    return datetime.now(timezone.utc) - timedelta(days=dias, hours=horas)


def generar_leads(n=42):
    rules = load_rules()
    filas = []
    for i in range(1, n + 1):
        lead_id = f"L{i:03d}"
        creador = random.choice(CREADORES)
        canal = random.choice(CANALES)

        bucket = random.random()
        if bucket < 0.60:
            mensaje = random.choice(MENSAJES_NORMALES)
        elif bucket < 0.75:
            mensaje = random.choice(MENSAJES_ESCALAR)
        elif bucket < 0.88:
            mensaje = random.choice(MENSAJES_IGNORAR)
        else:
            mensaje = random.choice(MENSAJES_SIN_MONTO)

        telefono = _telefono_falso(i)
        if random.random() < PROB_NUEVO_SIN_PROCESAR:
            estado_inicial = "Nuevo"  # llegó, todavía nadie lo procesó
        else:
            decision, _razon = clasificar_mensaje(mensaje, rules)
            estado_inicial = _DECISION_A_ESTADO[decision]
        timestamp = _fecha_aleatoria().isoformat()

        filas.append(
            {
                "lead_id": lead_id,
                "timestamp": timestamp,
                "creador": creador,
                "canal": canal,
                "mensaje": mensaje,
                "telefono": telefono,
                "estado_inicial": estado_inicial,
            }
        )
    return filas


def generar_enrollments(leads, n=27):
    creators = CREADORES + [""]  # "" simula creator_id vacío a propósito
    statuses = ["Activo", "Pendiente", "Cancelado"]
    filas = []

    # Solo leads que fueron "Respondido" o "Escalado" (y luego revisado por un
    # humano) pueden llegar a inscribirse con el partner. Un lead "Nuevo" o
    # "Ignorado" no debería aparecer aquí: si apareciera, el funnel del
    # Ejercicio C mostraría tasas de conversión imposibles (>100%).
    elegibles = [l for l in leads if l["estado_inicial"] in ("Respondido", "Escalado")]
    # con reemplazo: un mismo lead puede tener varios intentos de inscripción
    muestra_leads = random.choices(elegibles, k=n) if elegibles else []

    for i, lead in enumerate(muestra_leads, start=1):
        enrollment_id = f"E{i:03d}"
        creator_id = random.choice(creators)

        telefono = lead["telefono"]
        # Filas 1-2: teléfono con formato inválido a propósito (letras / incompleto).
        if i == 1:
            telefono = "30011XX22"
        elif i == 2:
            telefono = "30112"
        # Fila 3: teléfono distinto Y creador distinto — sin ninguna señal
        # que corrobore que es el mismo lead ("Sin Coincidencia").
        # Fila 4: teléfono distinto PERO el mismo creador que originó al
        # lead — corrobora que probablemente es la misma persona con un
        # typo del partner, no una atribución robada ("Atribución
        # Probabilística"). Las dos filas prueban los dos caminos del
        # fuzzy matching con datos reales del dataset, no solo en teoría.
        elif i == 4:
            telefono = _telefono_falso(999 - i)
            creator_id = lead["creador"]
        elif i == 3:
            telefono = _telefono_falso(999 - i)

        fecha = _fecha_aleatoria(dias_atras_max=10).strftime("%Y-%m-%d")
        # Filas 5-7: fecha rota a propósito (garantizado).
        if 5 <= i <= 7:
            fecha = ["31/02/2026", "", "2026-13-45"][i - 5]

        filas.append(
            {
                "enrollment_id": enrollment_id,
                "lead_id": lead["lead_id"],
                "creator_id": creator_id,
                "telefono": telefono,
                "fecha_inscripcion": fecha,
                "monto_pactado": random.choice([0, 500000, 1200000, 3000000, 8000000]),
                "status": random.choice(statuses),
            }
        )

    # duplicados a propósito (mismo enrollment_id repetido)
    if filas:
        dup = dict(filas[0])
        filas.append(dup)

    return filas


FUENTES_CONTENIDO = [
    {"id": "S01", "texto": "¿Esto afecta mi historial de crédito?", "tema": "tarjeta de crédito",
     "detalle": "les preocupa el impacto en su reporte más que la deuda misma.", "frecuencia": 18, "urgencia": "alta"},
    {"id": "S02", "texto": "¿De verdad me pueden ayudar a pagar menos?", "tema": "deudas en general",
     "detalle": "quieren saber qué tan real es el programa.", "frecuencia": 22, "urgencia": "alta"},
    {"id": "S03", "texto": "¿Tengo que dar información bancaria?", "tema": "seguridad",
     "detalle": "desconfían de compartir datos sensibles.", "frecuencia": 9, "urgencia": "media"},
    {"id": "S04", "texto": "Me llamaron de un banco amenazando con demanda", "tema": "cobranza agresiva",
     "detalle": "sienten presión y no saben si es legal.", "frecuencia": 14, "urgencia": "alta"},
    {"id": "S05", "texto": "¿Cuánto cuesta el programa?", "tema": "costos",
     "detalle": "temen que sea otro gasto más.", "frecuencia": 16, "urgencia": "media"},
    {"id": "S06", "texto": "Tengo varias deudas, ¿por cuál empiezo?", "tema": "libranza",
     "detalle": "no saben priorizar entre varios créditos.", "frecuencia": 11, "urgencia": "media"},
    {"id": "S07", "texto": "¿Esto es lo mismo que un abogado de deudas?", "tema": "confusión de servicio",
     "detalle": "confunden el programa con servicios legales.", "frecuencia": 7, "urgencia": "baja"},
    {"id": "S08", "texto": "Perdí mi trabajo y no puedo pagar la tarjeta", "tema": "tarjeta de crédito",
     "detalle": "situación de urgencia económica reciente.", "frecuencia": 13, "urgencia": "alta"},
    {"id": "S09", "texto": "¿Cuánto tiempo se demora el proceso?", "tema": "expectativas",
     "detalle": "quieren una línea de tiempo realista.", "frecuencia": 10, "urgencia": "baja"},
    {"id": "S10", "texto": "¿Qué pasa con mi hipoteca si entro al programa?", "tema": "hipotecario",
     "detalle": "temen perder la vivienda.", "frecuencia": 6, "urgencia": "media"},
]


def main():
    leads = generar_leads()
    enrollments = generar_enrollments(leads)

    with open(DATA_DIR / "leads.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(leads[0].keys()))
        writer.writeheader()
        writer.writerows(leads)

    with open(DATA_DIR / "partner_enrollments.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(enrollments[0].keys()))
        writer.writeheader()
        writer.writerows(enrollments)

    with open(DATA_DIR / "content_sources.json", "w", encoding="utf-8") as f:
        json.dump(FUENTES_CONTENIDO, f, ensure_ascii=False, indent=2)

    print(f"Generados {len(leads)} leads, {len(enrollments)} inscripciones, "
          f"{len(FUENTES_CONTENIDO)} fuentes de contenido en {DATA_DIR}")


if __name__ == "__main__":
    main()

"""Ejercicio C: limpieza de datos + reporting de funnel sobre datos sucios.

Fuentes (fixtures, no la base SQLite en vivo):
- data/leads.csv: leads de chat con su estado inicial.
- data/partner_enrollments.csv: export del partner, con errores a propósito.

Las decisiones de limpieza se devuelven explícitas en el resultado (no quedan
escondidas en el código) para que sean auditables.
"""
from pathlib import Path

import pandas as pd
import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


def _leads_estancados_dias():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    return rules.get("leads_estancados_dias", 3)


def _normalizar_telefono(telefono):
    if pd.isna(telefono):
        return None
    digitos = "".join(ch for ch in str(telefono) if ch.isdigit())
    return digitos[-10:] if len(digitos) >= 10 else (digitos or None)


def cargar_enrollments_crudo():
    """Lee partner_enrollments.csv tal cual viene, sin limpiar. Para la vista "datos sucios"."""
    return pd.read_csv(DATA_DIR / "partner_enrollments.csv", dtype=str)


def detectar_problemas(enroll_raw):
    """Para cada fila del CSV crudo, marca qué columnas tienen un error conocido.

    Devuelve un DataFrame booleano con las mismas filas y columnas
    [creator_id, telefono, fecha_inscripcion, enrollment_id] listo para
    resaltar en la interfaz.
    """
    problemas = pd.DataFrame(False, index=enroll_raw.index, columns=enroll_raw.columns)

    creator_vacio = enroll_raw["creator_id"].isna() | (enroll_raw["creator_id"].str.strip() == "")
    problemas["creator_id"] = creator_vacio

    telefono_valido = enroll_raw["telefono"].str.fullmatch(r"\d{10}", na=False)
    problemas["telefono"] = ~telefono_valido

    fecha_valida = pd.to_datetime(enroll_raw["fecha_inscripcion"], errors="coerce").notna()
    problemas["fecha_inscripcion"] = ~fecha_valida

    problemas["enrollment_id"] = enroll_raw["enrollment_id"].duplicated(keep=False)

    return problemas


def cargar_y_limpiar(enroll_df=None):
    """Carga leads.csv + inscripciones (fixture o uno pasado por parámetro) y limpia.

    `enroll_df` permite pasar un DataFrame ya leído (ej. un CSV subido por el
    usuario en la interfaz) en vez del fixture bundleado en data/.

    Devuelve (leads_df, enrollments_df, notas_limpieza: list[str]).
    """
    notas = []

    leads = pd.read_csv(DATA_DIR / "leads.csv", dtype=str)
    leads["timestamp"] = pd.to_datetime(leads["timestamp"], errors="coerce", utc=True)
    leads["telefono_normalizado"] = leads["telefono"].apply(_normalizar_telefono)

    antes = len(leads)
    leads = leads.drop_duplicates(subset=["lead_id"])
    if len(leads) < antes:
        notas.append(f"Se eliminaron {antes - len(leads)} leads duplicados por lead_id.")

    enroll = enroll_df.copy() if enroll_df is not None else cargar_enrollments_crudo()

    vacios_creator = enroll["creator_id"].isna() | (enroll["creator_id"].str.strip() == "")
    if vacios_creator.any():
        notas.append(
            f"{vacios_creator.sum()} inscripciones sin creator_id: no se pueden atribuir "
            "a un creador para comisión; se marcan como 'sin_atribuir' en vez de descartarse."
        )
    enroll["creator_id"] = enroll["creator_id"].where(~vacios_creator, "sin_atribuir")

    enroll["telefono_normalizado"] = enroll["telefono"].apply(_normalizar_telefono)

    enroll["fecha_inscripcion_parsed"] = pd.to_datetime(
        enroll["fecha_inscripcion"], errors="coerce", utc=True
    )
    fechas_invalidas = enroll["fecha_inscripcion_parsed"].isna()
    if fechas_invalidas.any():
        notas.append(
            f"{fechas_invalidas.sum()} inscripciones con fecha_inscripcion inválida o vacía: "
            "se conservan pero quedan fuera de los reportes que agrupan por fecha."
        )

    antes = len(enroll)
    enroll = enroll.drop_duplicates(subset=["enrollment_id"])
    if len(enroll) < antes:
        notas.append(f"Se eliminaron {antes - len(enroll)} inscripciones duplicadas por enrollment_id.")

    return leads, enroll, notas


def calcular_funnel(leads=None, enroll=None):
    if leads is None or enroll is None:
        leads, enroll, _ = cargar_y_limpiar()

    total = len(leads)
    respondidos = (leads["estado_inicial"] == "Respondido").sum()
    # "Respondido" (el bot pre-califica) y "Escalado" (un humano revisa y
    # puede transferir) son los dos caminos que pueden llegar a inscripción.
    pre_calificados = leads["estado_inicial"].isin(["Respondido", "Escalado"]).sum()

    lead_ids_transferidos = set(enroll["lead_id"].dropna())
    transferidos = leads["lead_id"].isin(lead_ids_transferidos).sum()

    activos_por_lead = set(
        enroll.loc[enroll["status"] == "Activo", "lead_id"].dropna()
    )
    inscritos_activos = leads["lead_id"].isin(activos_por_lead).sum()

    def tasa(n, d):
        return round(100 * float(n) / float(d), 1) if d else 0.0

    funnel_general = {
        "leads_totales": int(total),
        "respondidos": int(respondidos),
        "pre_calificados": int(pre_calificados),
        "transferidos": int(transferidos),
        "inscritos_activos": int(inscritos_activos),
        "tasa_respuesta_pct": tasa(respondidos, total),
        "tasa_transferencia_pct": tasa(transferidos, pre_calificados),
        "tasa_inscripcion_pct": tasa(inscritos_activos, transferidos),
    }

    por_canal = (
        leads.groupby("canal")["lead_id"]
        .count()
        .rename("leads_totales")
        .reset_index()
        .to_dict(orient="records")
    )
    por_creador = (
        leads.groupby("creador")["lead_id"]
        .count()
        .rename("leads_totales")
        .reset_index()
        .to_dict(orient="records")
    )

    return {
        "general": funnel_general,
        "por_canal": por_canal,
        "por_creador": por_creador,
    }


def leads_estancados(leads=None, enroll=None, referencia=None):
    """Leads que llevan más de N días (rules.yaml) sin avanzar a enrollments."""
    if leads is None or enroll is None:
        leads, enroll, _ = cargar_y_limpiar()

    referencia = referencia or leads["timestamp"].max()
    dias_umbral = _leads_estancados_dias()

    lead_ids_avanzados = set(enroll["lead_id"].dropna())
    antiguedad_dias = (referencia - leads["timestamp"]).dt.total_seconds() / 86400

    estancados_mask = (
        leads["estado_inicial"].isin(["Nuevo", "Escalado"])
        & (antiguedad_dias > dias_umbral)
        & ~leads["lead_id"].isin(lead_ids_avanzados)
    )

    cols = ["lead_id", "creador", "canal", "estado_inicial", "timestamp"]
    return leads.loc[estancados_mask, cols].to_dict(orient="records")


def reporte_ruptura_comisiones(leads=None, enroll=None):
    """Qué rompería el cálculo de comisiones, con evidencia concreta del dataset."""
    if leads is None or enroll is None:
        leads, enroll, _ = cargar_y_limpiar()

    sin_atribuir = enroll[enroll["creator_id"] == "sin_atribuir"]

    telefonos_lead = leads.set_index("lead_id")["telefono_normalizado"]
    enroll_con_lead = enroll[enroll["lead_id"].isin(telefonos_lead.index)].copy()
    enroll_con_lead["telefono_lead"] = enroll_con_lead["lead_id"].map(telefonos_lead)
    mismatch = enroll_con_lead[
        enroll_con_lead["telefono_lead"].notna()
        & enroll_con_lead["telefono_normalizado"].notna()
        & (enroll_con_lead["telefono_lead"] != enroll_con_lead["telefono_normalizado"])
    ]

    return {
        "inscripciones_sin_creator_id": int(len(sin_atribuir)),
        "inscripciones_con_telefono_mismatch": int(len(mismatch)),
        "ejemplos_mismatch": mismatch[["enrollment_id", "lead_id", "telefono_lead", "telefono_normalizado"]]
        .head(5)
        .to_dict(orient="records"),
        "resumen": (
            "creator_id vacío impide pagar la comisión al creador correcto (o paga de más a "
            "'sin_atribuir' si no se filtra). Un teléfono distinto entre el lead original y la "
            "inscripción del partner impide confirmar que es la misma persona: puede pagarse "
            "comisión por un lead que no se originó en nuestros creadores, o negarse una "
            "comisión legítima por un error de captura del partner."
        ),
    }


if __name__ == "__main__":
    leads, enroll, notas = cargar_y_limpiar()
    print("Notas de limpieza:")
    for n in notas:
        print(" -", n)
    print("\nFunnel:", calcular_funnel(leads, enroll)["general"])
    print("\nLeads estancados:", len(leads_estancados(leads, enroll)))
    print("\nRuptura de comisiones:", reporte_ruptura_comisiones(leads, enroll)["resumen"])

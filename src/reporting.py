"""Ejercicio C: limpieza de datos + reconciliación + reporting de funnel
sobre datos sucios.

Fuentes (fixtures, no la base SQLite en vivo):
- data/leads.csv: leads de chat con su estado inicial (calculado con el
  motor de reglas real, ver scripts/generate_fake_data.py).
- data/partner_enrollments.csv: export del partner, con errores a propósito.

Las decisiones de limpieza se devuelven explícitas en el resultado (no quedan
escondidas en el código) para que sean auditables.
"""
from pathlib import Path

import pandas as pd
import yaml

from src.rules_engine import extraer_monto_deuda

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


def _cargar_reglas_reporting():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _leads_estancados_dias():
    return _cargar_reglas_reporting().get("leads_estancados_dias", 2)


def _comision_pct_estimada():
    return _cargar_reglas_reporting().get("comision_pct_estimada", 20)


_CODIGO_PAIS_DEFECTO = "57"  # Colombia — todos los celulares de esta demo son locales


def _normalizar_telefono(telefono, codigo_pais=_CODIGO_PAIS_DEFECTO):
    """Normalización estricta a E.164 (+<código país><número local>).

    No es una limpieza "suave" que rescata cualquier cosa: si después de
    quitar +, espacios, guiones y prefijos locales no queda un número de
    10 dígitos reconocible, se devuelve None en vez de inventar un
    teléfono — eso es justo lo que separa un dato "sucio pero salvable"
    de uno que de verdad no sirve para reconciliar nada.
    """
    if pd.isna(telefono):
        return None
    digitos = "".join(ch for ch in str(telefono) if ch.isdigit())
    if not digitos:
        return None
    if len(digitos) == 11 and digitos.startswith("0"):
        digitos = digitos[1:]  # prefijo troncal local (ej. "0" + celular)
    if len(digitos) == 12 and digitos.startswith(codigo_pais):
        local = digitos[2:]
    elif len(digitos) == 10:
        local = digitos
    else:
        return None
    return f"+{codigo_pais}{local}"


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

    # Deduplicar priorizando la primera fecha de conversión VÁLIDA, no la
    # primera fila que aparezca en el archivo — si dos filas comparten
    # enrollment_id, la que tiene una fecha real gana sobre la que no, y
    # entre dos fechas reales gana la más antigua (la conversión original).
    antes = len(enroll)
    enroll = enroll.sort_values("fecha_inscripcion_parsed", na_position="last")
    enroll = enroll.drop_duplicates(subset=["enrollment_id"], keep="first")
    enroll = enroll.sort_values("enrollment_id").reset_index(drop=True)
    if len(enroll) < antes:
        notas.append(
            f"Se eliminaron {antes - len(enroll)} inscripciones duplicadas por enrollment_id "
            "(se conservó la de fecha de conversión más antigua y válida)."
        )

    return leads, enroll, notas


def reconciliar_conversiones(leads=None, enroll=None):
    """Tabla final de inscripciones reconciliadas contra los leads
    originales, con flags de auditoría — pensada para que Finanzas pueda
    filtrar de un vistazo qué se puede pagar tal cual y qué necesita
    revisión humana antes.

    match_type:
      - "Exacta": el teléfono de la inscripción coincide con el que el
        lead dio en el chat.
      - "Atribución Probabilística": el teléfono NO coincide, pero el
        creator_id de la inscripción sí es el mismo creador que originó
        ese lead — corrobora que probablemente es la misma persona con
        un error de captura del partner, no una atribución robada.
      - "Sin Coincidencia": el teléfono no coincide y tampoco hay
        corroboración por creador — no hay evidencia de que sea el
        mismo lead; hace falta confirmar a mano con el partner.
      - "Sin Atribuir": la inscripción no trae creator_id en absoluto.

    commission_status (qué puede hacer Finanzas con la fila tal como
    está): "Pagable" / "En Disputa" / "Bloqueada".
    """
    if leads is None or enroll is None:
        leads, enroll, _ = cargar_y_limpiar()

    leads_idx = leads.set_index("lead_id")
    filas = []
    for _, fila in enroll.iterrows():
        lead_id = fila.get("lead_id")
        lead = leads_idx.loc[lead_id] if lead_id in leads_idx.index else None

        creator_id = fila.get("creator_id")
        sin_creator = not creator_id or creator_id == "sin_atribuir"

        telefono_match = False
        creador_match = False
        if lead is not None:
            telefono_lead = lead.get("telefono_normalizado")
            telefono_enroll = fila.get("telefono_normalizado")
            telefono_match = bool(telefono_lead) and bool(telefono_enroll) and telefono_lead == telefono_enroll
            creador_match = (not sin_creator) and (creator_id == lead.get("creador"))

        fecha_valida = pd.notna(fila.get("fecha_inscripcion_parsed"))

        if sin_creator:
            match_type = "Sin Atribuir"
        elif telefono_match:
            match_type = "Exacta"
        elif creador_match:
            match_type = "Atribución Probabilística"
        else:
            match_type = "Sin Coincidencia"

        is_clean = (match_type == "Exacta") and fecha_valida

        if is_clean:
            commission_status = "Pagable"
        elif match_type == "Atribución Probabilística":
            commission_status = "En Disputa"
        else:
            commission_status = "Bloqueada"

        filas.append(
            {
                "enrollment_id": fila.get("enrollment_id"),
                "lead_id": lead_id,
                "creator_id": fila.get("creator_id"),
                "telefono": fila.get("telefono_normalizado"),
                "fecha_inscripcion": fila.get("fecha_inscripcion"),
                "monto_pactado": fila.get("monto_pactado"),
                "status": fila.get("status"),
                "is_clean": is_clean,
                "match_type": match_type,
                "commission_status": commission_status,
            }
        )

    return pd.DataFrame(filas)


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

    # Performance por creador/canal: no solo cuántos leads trajo, sino
    # cuántos de verdad se confirmaron (Activo + comisión Pagable sin
    # disputa) y cuánto representa eso en comisión estimada — el
    # porcentaje es una tasa configurable en rules.yaml (comision_pct_estimada),
    # una aproximación interna para priorizar, nunca un número que se le
    # promete al lead.
    reconciliado = reconciliar_conversiones(leads, enroll)
    pct_comision = _comision_pct_estimada()

    confirmados = reconciliado[
        (reconciliado["commission_status"] == "Pagable") & (reconciliado["status"] == "Activo")
    ].copy()
    confirmados["monto_pactado"] = pd.to_numeric(confirmados["monto_pactado"], errors="coerce").fillna(0)
    confirmados = confirmados.merge(leads[["lead_id", "creador", "canal"]], on="lead_id", how="left")

    conteo_confirmados_creador = confirmados.groupby("creador")["lead_id"].count()
    comision_por_creador = confirmados.groupby("creador")["monto_pactado"].sum() * pct_comision / 100
    conteo_confirmados_canal = confirmados.groupby("canal")["lead_id"].count()
    comision_por_canal = confirmados.groupby("canal")["monto_pactado"].sum() * pct_comision / 100

    por_canal = []
    for canal, leads_totales in leads.groupby("canal")["lead_id"].count().items():
        inscritos = int(conteo_confirmados_canal.get(canal, 0))
        por_canal.append({
            "canal": canal,
            "leads_totales": int(leads_totales),
            "inscritos_confirmados": inscritos,
            "conversion_pct": tasa(inscritos, leads_totales),
            "comision_estimada": round(float(comision_por_canal.get(canal, 0)), 0),
        })

    por_creador = []
    for creador, leads_totales in leads.groupby("creador")["lead_id"].count().items():
        inscritos = int(conteo_confirmados_creador.get(creador, 0))
        por_creador.append({
            "creador": creador,
            "leads_totales": int(leads_totales),
            "inscritos_confirmados": inscritos,
            "conversion_pct": tasa(inscritos, leads_totales),
            "comision_estimada": round(float(comision_por_creador.get(creador, 0)), 0),
        })

    return {
        "general": funnel_general,
        "por_canal": por_canal,
        "por_creador": por_creador,
        "comision_pct_estimada": pct_comision,
    }


def leads_estancados(leads=None, enroll=None, referencia=None):
    """Leads ya pre-calificados (Respondido/Escalado — el bot o un humano
    ya los tocó) que nunca llegaron a aparecer en las inscripciones del
    partner y llevan más de N días sin avanzar (rules.yaml,
    leads_estancados_dias — 2 por defecto, ~48h). Un lead que sigue
    "Nuevo" no cuenta como estancado: todavía nadie lo ha procesado, es
    backlog, no un caso que se cayó del funnel.

    Ordenados por el monto de deuda que mencionaron, de mayor a menor —
    para priorizar primero los que tienen más plata en juego.
    """
    if leads is None or enroll is None:
        leads, enroll, _ = cargar_y_limpiar()

    referencia = referencia or leads["timestamp"].max()
    dias_umbral = _leads_estancados_dias()

    lead_ids_avanzados = set(enroll["lead_id"].dropna())
    antiguedad_dias = (referencia - leads["timestamp"]).dt.total_seconds() / 86400

    estancados_mask = (
        leads["estado_inicial"].isin(["Respondido", "Escalado"])
        & (antiguedad_dias > dias_umbral)
        & ~leads["lead_id"].isin(lead_ids_avanzados)
    )

    estancados = leads.loc[estancados_mask].copy()
    estancados["monto_estimado"] = estancados["mensaje"].apply(extraer_monto_deuda)
    estancados = estancados.sort_values("monto_estimado", ascending=False, na_position="last")

    cols = ["lead_id", "creador", "canal", "estado_inicial", "timestamp", "monto_estimado"]
    return estancados[cols].to_dict(orient="records")


def reporte_ruptura_comisiones(leads=None, enroll=None):
    """Qué rompería el cálculo de comisiones, con evidencia concreta del
    dataset — construido sobre reconciliar_conversiones() para que no
    haya dos cálculos distintos (uno acá, otro en la tabla reconciliada)
    que se puedan desalinear."""
    if leads is None or enroll is None:
        leads, enroll, _ = cargar_y_limpiar()

    reconciliado = reconciliar_conversiones(leads, enroll)

    sin_atribuir = reconciliado[reconciliado["match_type"] == "Sin Atribuir"]
    mismatch = reconciliado[reconciliado["match_type"].isin(["Atribución Probabilística", "Sin Coincidencia"])]

    telefonos_lead = leads.set_index("lead_id")["telefono_normalizado"]
    ejemplos = mismatch.copy()
    ejemplos["telefono_lead"] = ejemplos["lead_id"].map(telefonos_lead)

    return {
        "inscripciones_sin_creator_id": int(len(sin_atribuir)),
        "inscripciones_con_telefono_mismatch": int(len(mismatch)),
        "ejemplos_mismatch": ejemplos[["enrollment_id", "lead_id", "telefono_lead", "telefono", "match_type"]]
        .rename(columns={"telefono": "telefono_normalizado"})
        .head(5)
        .to_dict(orient="records"),
        "resumen": (
            "creator_id vacío impide pagar la comisión al creador correcto (o paga de más a "
            "'sin_atribuir' si no se filtra). Un teléfono distinto entre el lead original y la "
            "inscripción del partner impide confirmar que es la misma persona: puede pagarse "
            "comisión por un lead que no se originó en nuestros creadores, o negarse una "
            "comisión legítima por un error de captura del partner. Ver RUPTURA_COMISIONES.md "
            "para el análisis completo y el protocolo de resolución."
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
    print("\nReconciliación (conteo por match_type):")
    print(reconciliar_conversiones(leads, enroll)["match_type"].value_counts().to_dict())

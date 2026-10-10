"""Panel operativo en Streamlit — Salvaguardas Doble B × Consejería Clara.

Reutiliza toda la lógica de negocio ya construida y probada en src/
(rules_engine, prequalification_agent, crm_automation, reporting,
content_system). Esta es solo la capa de interfaz.

Correr: streamlit run streamlit_app.py
"""
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from src import crm_automation, db, reporting
from src.content_system import generar_guiones
from src.prequalification_agent import procesar_mensaje_entrante

RULES_PATH = Path(__file__).resolve().parent / "rules" / "rules.yaml"

st.set_page_config(
    page_title="Salvaguardas Doble B — Panel de Operación",
    layout="wide",
)

# ---------------------------------------------------------------- estilos --
# Paleta inspirada en el sitio de Notion: blanco, negro audaz, azul como
# único acento — nada de paletas cálidas "editoriales" ni serif.
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --brand:#2563eb; --brand-dark:#1d4ed8; --brand-tint:#eaf1fe;
  --amber:#b45309; --amber-tint:#fef3dc; --gray-tint:#f1f2f4;
  --ink:#111317; --ink-soft:#44464c; --ink-muted:#80838a; --border:#e7e8eb;
}
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Inter', sans-serif !important; font-weight: 800 !important; color: var(--ink); letter-spacing: -.02em; }
.stApp { background: #ffffff; }
.eyebrow { font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--brand); font-weight: 700; margin-bottom: 2px; }
.lede { font-size: 15px; color: var(--ink-soft); max-width: 70ch; }
.badge { display:inline-block; font-size:10.5px; font-weight:700; text-transform:uppercase; padding:2px 9px; border-radius:999px; margin-left:6px;}
.badge.responder { background: var(--brand-tint); color: var(--brand-dark); }
.badge.escalar_humano { background: var(--amber-tint); color: var(--amber); }
.badge.ignorar { background: var(--gray-tint); color: var(--ink-muted); }
.chat-bubble { background:#fff; border:1px solid var(--border); border-radius:12px 12px 12px 3px; padding:10px 14px; font-size:13px; margin:8px 0; max-width:85%; }
.chat-bubble.draft { background: var(--brand-tint); border-color:#d7e4fc; border-radius:12px 12px 3px 12px; margin-left:auto; color: var(--brand-dark); }
.chat-bubble.descartado { background: var(--gray-tint); border-color:var(--border); color: var(--ink-muted); text-decoration: line-through; }
.chat-bubble .stamp { font-size:9.5px; text-transform:uppercase; letter-spacing:.04em; opacity:.7; display:block; margin-bottom:3px; text-decoration:none; }
.sin-respuesta { text-align:center; color: var(--ink-muted); font-size:11.5px; margin:10px 0; }
.script-card { background:#fff; border:1px solid var(--border); border-radius:14px; overflow:hidden; margin-bottom:12px; }
.script-card .strip { background: var(--brand-tint); color: var(--brand-dark); font-size:11px; font-weight:700; padding:8px 14px; display:flex; justify-content:space-between; }
.script-card .body { padding:14px; font-size:12.8px; color: var(--ink-soft); white-space:pre-wrap; line-height:1.55; }
.callout { background: var(--amber-tint); border:1px solid #f3dca8; border-left:3px solid var(--amber); border-radius:10px; padding:16px 18px; font-size:13.3px; color:#6b4414; }
.lead-card { background:#fff; border:1px solid var(--border); border-radius:14px; padding:20px 22px; margin-top:4px; }
.lead-card h4 { margin:0 0 4px; font-size:17px; font-weight:800; }
.lead-card .meta { color: var(--ink-muted); font-size:12.5px; margin-bottom:12px; }
.lead-card .field-label { font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color: var(--ink-muted); font-weight:700; margin-top:14px; }
.lead-card .field-value { font-size:14px; color: var(--ink); margin-top:2px; }
.top-banner { background: var(--gray-tint); color: var(--ink-soft); font-size: 12.5px; padding: 8px 14px; margin-top: 2.2rem; margin-bottom: 10px; border-radius: 8px; text-align: center; }
.top-banner b { color: var(--ink); }
.topbar-brand { font-size: 17px; font-weight: 800; padding-top: 6px; }
.topbar-brand .topbar-sub { color: var(--ink-muted); font-weight: 400; font-size: 12.5px; margin-left: 6px; }
div[data-testid="stTabs"] button[role="tab"] p { font-size: 14px; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

db.init_db()

if "primera_carga_hecha" not in st.session_state:
    st.session_state["primera_carga_hecha"] = bool(db.listar_leads())
if "lead_counter" not in st.session_state:
    existentes = db.listar_leads()
    nums = [int(l["lead_id"][1:]) for l in existentes if l["lead_id"].startswith("N") and l["lead_id"][1:].isdigit()]
    st.session_state["lead_counter"] = (max(nums) + 1) if nums else 1
st.session_state.setdefault("auto_gen_activo", False)
st.session_state.setdefault("ultimo_auto_gen_ts", 0.0)

# --------------------------------------------------------- datos iniciales --
# Pool para la generación automática — plantillas parecidas a mensajes
# reales, combinadas con montos, creadores y teléfonos aleatorios en cada
# generación para que ningún lead se repita igual. Agrupado por categoría
# para que se note la variedad de tono, no solo de monto.
CREADORES_POOL = [
    "@carla.finanzas", "@juanfi_libre", "@manu.deudas", "@laura_consejos",
    "@pedro.ahorra", "@sofia.claridad", "@andres.deudafree", "@valen.consejos",
    "@diana.respira", "@oscar.sinsustos", "@camila.alivia", "@fer.consejos",
]
MENSAJES_POOL = [
    # --- normales: monto + tipo de deuda, tono directo ---
    "Hola, tengo una deuda de tarjeta de credito de {monto} y no se que hacer",
    "Buenas, debo libranza por {monto}, quiero informacion del programa",
    "Me interesa el programa, tengo una deuda hipotecaria de {monto}",
    "Hola vi el video, debo como {monto} en tarjeta, quiero hablar con un consejero",
    "Buenas tardes, tengo varias deudas y no sé por dónde empezar, suman {monto}",
    "Hola quiero asesoria para mi libranza de nomina de {monto}",
    "Vi el reel de ustedes, tengo deudas de consumo por {monto}, me pueden ayudar?",
    "Hola, quiero saber si me pueden ayudar con mi credito de {monto}",
    "Buenas, una amiga me recomendo escribirles, debo {monto} en tarjetas",
    "Tengo 2 tarjetas y un libre inversion, entre las 2 debo como {monto}",
    "Hola, mi credito hipotecario quedo atrasado, debo {monto} en mora",
    # --- normales: tono preocupado / contexto emocional ---
    "Buenas, perdi mi trabajo hace 2 meses y debo {monto} en tarjetas, no se que hacer",
    "Hola, con el aumento de las cuotas ya no me alcanza, debo {monto} de libranza",
    "No he podido dormir pensando en esto, debo {monto} y cada mes es peor",
    "Hola, me da pena escribir pero ya no se a quien acudir, debo {monto}",
    "Buenas, mi esposa y yo juntamos deudas de {monto} y estamos agobiados",
    # --- normales: con preguntas específicas de proceso ---
    "Hola, si entro al programa esto afecta mi historial de credito? debo {monto}",
    "Buenas, cuanto se demora el proceso? tengo {monto} en tarjetas",
    "Hola, ustedes cobran algo por la asesoria? debo {monto} de libre inversion",
    "Me pueden decir si esto es legal? tengo deudas por {monto} y me da desconfianza",
    "Hola, que pasa con mi reporte en centrales si hago esto? debo {monto}",
    # --- normales: informal / con errores de tecleo, como chat real ---
    "ola buenas dias debo {monto} en targeta y nose q ace",
    "hola vi el reel, deboo como {monto} entre varias deudas ayuda porfa",
    "buenas tardes😔 tengo una deuda de {monto} y stoy muy estresada",
    "hola necesito ayuda urgente debo {monto} y no m alcanza el sueldo",
    # --- riesgo: debe escalar a humano ---
    "Me llego una demanda por mi tarjeta de credito, que hago",
    "Un abogado me contacto por el embargo de mi cuenta, estoy muy preocupado",
    "Esto es urgente, me amenazan con quitarme la casa",
    "Quiero denunciar un fraude con mi tarjeta",
    "La empresa esta en quiebra y no se que hacer con mis deudas",
    "Me estan llamando de un juzgado por una deuda vieja, no entiendo nada",
    "Un cobrador me amenaza con ir a mi trabajo, eso es legal?",
    "No entiendo la carta que me llego del banco, parece una demanda",
    # --- salida: deben ignorarse ---
    "No me interesa, quitame de esta lista por favor",
    "Stop, no quiero recibir mas mensajes",
    "Dejen de escribirme, es spam",
    "Ya resolví mis deudas, quítame de la lista por favor",
    "Por favor quitame de aquí, esto me llega sin que yo pida nada",
    # --- interés vago / sin monto claro ---
    "Hola, quiero mas informacion sobre el programa",
    "Buenas, como funciona la consejeria de ustedes",
    "Hola vi el anuncio, me pueden contar mas",
    "Hola, que es exactamente lo que ofrecen?",
    "Buenas, un amigo me hablo de ustedes pero no entendi bien que hacen",
    "Hola, esto es como un abogado o que es?",
]
MONTOS_POOL = [
    650000, 980000, 1200000, 1800000, 2200000, 2600000, 3200000, 4100000,
    4800000, 5600000, 6300000, 7300000, 8200000, 9000000, 10400000, 11500000,
    13800000, 15000000, 17600000, 19900000, 22000000, 26500000, 31000000,
    38000000, 45000000, 52000000,
]


# Probabilidad de que un lead (de carga inicial o generado solo) llegue
# SIN teléfono — pasa en la vida real (el lead no lo compartió, el
# formulario lo dejó vacío, etc.) y es justo lo que ejercita la etapa
# "Pendiente de Teléfono" del Ejercicio B sin depender del botón de
# simulación.
_PROB_SIN_TELEFONO = 0.12


def _generar_carga_defecto(n=42):
    """Set reproducible (semilla fija, no toca el random global) para la
    primera carga — mínimo 42 leads mezclando los 3 caminos de clasificación."""
    rnd = random.Random(7)
    entradas = []
    for i in range(n):
        plantilla = rnd.choice(MENSAJES_POOL)
        mensaje = plantilla.format(monto=rnd.choice(MONTOS_POOL)) if "{monto}" in plantilla else plantilla
        creador = rnd.choice(CREADORES_POOL)
        canal = rnd.choices(["CTWA", "organico"], weights=[60, 40])[0]
        if rnd.random() < _PROB_SIN_TELEFONO:
            telefono = None
        else:
            telefono = "300" + "".join(str(rnd.randint(0, 9)) for _ in range(7))
        entradas.append((creador, canal, mensaje, telefono))
    return entradas


CARGA_DEFECTO = _generar_carga_defecto(42)


def _telefono_aleatorio():
    if random.random() < _PROB_SIN_TELEFONO:
        return None
    return "3" + "".join(str(random.randint(0, 9)) for _ in range(9))


def generar_lead_aleatorio(lead_id):
    plantilla = random.choice(MENSAJES_POOL)
    mensaje = plantilla.format(monto=random.choice(MONTOS_POOL)) if "{monto}" in plantilla else plantilla
    creador = random.choice(CREADORES_POOL)
    canal = random.choices(["CTWA", "organico"], weights=[60, 40])[0]
    return {"lead_id": lead_id, "creador": creador, "canal": canal, "mensaje": mensaje, "telefono": _telefono_aleatorio()}


def siguiente_lead_id():
    st.session_state.setdefault("lead_counter", 1)
    lead_id = f"N{st.session_state.lead_counter:04d}"
    st.session_state.lead_counter += 1
    return lead_id


def ingresar_lead(creador, canal, mensaje, telefono, lead_id=None):
    lead_id = lead_id or siguiente_lead_id()
    return procesar_mensaje_entrante(lead_id, creador, canal, mensaje, telefono)


def resetear_operacion_en_vivo():
    db.reset_db()
    for key in ("primera_carga_hecha", "auto_gen_activo", "lead_counter", "lead_seleccionado"):
        st.session_state.pop(key, None)


@st.fragment(run_every="5s")
def stack_fragment():
    """Tabla en vivo + generación automática.

    El fragmento se re-evalúa cada 5s para que la tabla se sienta viva, pero
    un lead nuevo solo se genera si de verdad pasaron >=30s reales desde el
    último (gate por reloj, con st.session_state["ultimo_auto_gen_ts"]).
    Importante: NO se llama a st.rerun() de alcance completo aquí — eso
    destruye y vuelve a montar el fragmento en cada ciclo, lo que rompe el
    intervalo real y puede generar leads en bucle sin control.
    """
    if st.session_state.get("auto_gen_activo"):
        ahora = time.time()
        if ahora - st.session_state.get("ultimo_auto_gen_ts", 0.0) >= 30:
            lead = generar_lead_aleatorio(siguiente_lead_id())
            ingresar_lead(lead["creador"], lead["canal"], lead["mensaje"], lead["telefono"], lead_id=lead["lead_id"])
            st.session_state["ultimo_auto_gen_ts"] = ahora
            st.toast(f"Nuevo lead automático: {lead['lead_id']}")

    leads_actuales = db.listar_leads()
    st.markdown(f"**Stack de leads** &nbsp;·&nbsp; {len(leads_actuales)} en total &nbsp;·&nbsp; <span style='color:var(--ink-muted); font-weight:400; font-size:12.5px;'>clic en una fila para ver el detalle</span>", unsafe_allow_html=True)

    if not leads_actuales:
        st.info("Sin leads todavía.")
        return

    df_stack = pd.DataFrame(leads_actuales).sort_values("timestamp", ascending=False)
    df_stack["hora"] = pd.to_datetime(df_stack["timestamp"]).dt.strftime("%H:%M:%S")
    # Mensaje va justo después del ID (no al final) para que se alcance a
    # leer sin tener que arrastrar el scroll horizontal de la tabla.
    df_view = df_stack[["lead_id", "mensaje", "estado", "creador", "canal", "hora"]].rename(columns={
        "lead_id": "ID", "mensaje": "Mensaje", "estado": "Decisión",
        "creador": "Creador", "canal": "Canal", "hora": "Hora",
    })

    evento = st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        height=430,
        on_select="rerun",
        selection_mode="single-row",
        key="stack_leads_tabla",
        column_config={
            "ID": st.column_config.TextColumn(width="small"),
            "Mensaje": st.column_config.TextColumn(width="large"),
            "Decisión": st.column_config.TextColumn(width="small"),
            "Creador": st.column_config.TextColumn(width="small"),
            "Canal": st.column_config.TextColumn(width="small"),
            "Hora": st.column_config.TextColumn(width="small"),
        },
    )

    filas_sel = evento.selection["rows"] if evento and evento.selection else []
    lead_id_sel = None
    if filas_sel:
        lead_id_sel = df_view.iloc[filas_sel[0]]["ID"]
        lead_detalle = db.get_lead(lead_id_sel)
        decisiones_lead = [d for d in db.listar_decisiones() if d["lead_id"] == lead_id_sel]
        drafts_lead = [d for d in db.listar_drafts() if d["lead_id"] == lead_id_sel]
        ultima_decision = decisiones_lead[-1] if decisiones_lead else None
        ultimo_draft = drafts_lead[-1] if drafts_lead else None

        badge = lead_detalle["estado"]
        detalle_html = f"""
        <div class="lead-card">
          <h4>{lead_detalle['lead_id']} <span class="badge {badge}">{badge.replace('_',' ')}</span></h4>
          <div class="meta">{lead_detalle['creador']} · {lead_detalle['canal']} · {lead_detalle.get('telefono') or 'sin teléfono'} · llegó {lead_detalle['timestamp']}</div>
          <div class="field-label">Mensaje</div>
          <div class="field-value">{lead_detalle['mensaje']}</div>
        """
        if ultima_decision:
            label_razon = "Motivo" if badge == "escalar_humano" else "Por qué el sistema decidió esto"
            detalle_html += f"""
          <div class="field-label">{label_razon}</div>
          <div class="field-value">{ultima_decision['razon']}</div>
            """
            if badge == "escalar_humano" and ultima_decision.get("resumen"):
                detalle_html += f"""
          <div class="field-label">Resumen para el agente</div>
          <div class="field-value">{ultima_decision['resumen']}</div>
                """
        if lead_detalle.get("monto_deuda") or lead_detalle.get("tipo_deuda"):
            detalle_html += f"""
          <div class="field-label">Pre-calificación</div>
          <div class="field-value">Monto: {lead_detalle.get('monto_deuda') or '—'} · Tipo de deuda: {lead_detalle.get('tipo_deuda') or '—'} · Interés en Consejero: {'sí' if lead_detalle.get('interes_consejero') else 'no'}</div>
            """
        detalle_html += f"""
          <div class="field-label">Etapa actual en el CRM</div>
          <div class="field-value">{lead_detalle['stage']}</div>
        </div>
        """
        st.markdown(detalle_html, unsafe_allow_html=True)

        if ultimo_draft:
            st.markdown(
                f'<div class="chat-bubble draft"><span class="stamp">Borrador generado · {ultimo_draft["status"]}</span>{ultimo_draft["contenido"]}</div>',
                unsafe_allow_html=True,
            )

    # ---- Log mínimo: timestamp, lead_id, decisión, razón, link al borrador ----
    decisiones_todas = db.listar_decisiones()
    if not decisiones_todas:
        return

    st.markdown(
        "**Log de decisiones** &nbsp;·&nbsp; "
        "<span style='color:var(--ink-muted); font-weight:400; font-size:12.5px;'>"
        "timestamp, lead, decisión, razón y link al borrador — clic en una fila para abrir el borrador</span>",
        unsafe_allow_html=True,
    )
    df_log = pd.DataFrame(decisiones_todas).sort_values("id", ascending=False)
    df_log["borrador"] = df_log["draft_id"].apply(
        lambda d: f"Ver borrador #{int(d)}" if pd.notna(d) else "— sin borrador"
    )
    df_log_view = df_log[["timestamp", "lead_id", "decision", "razon", "borrador"]].rename(columns={
        "timestamp": "Timestamp", "lead_id": "Lead", "decision": "Decisión",
        "razon": "Razón", "borrador": "Link al borrador",
    }).reset_index(drop=True)

    # Si se seleccionó un lead en el stack de arriba, se selecciona también
    # su fila correspondiente aquí — hay que fijar esto en session_state
    # ANTES de instanciar la tabla para que nazca ya con esa fila marcada.
    if lead_id_sel is not None:
        pos_match = df_log_view.index[df_log_view["Lead"] == lead_id_sel].tolist()
        if pos_match:
            st.session_state["log_decisiones_tabla"] = {"selection": {"rows": [pos_match[0]], "columns": []}}

    evento_log = st.dataframe(
        df_log_view,
        use_container_width=True,
        hide_index=True,
        height=260,
        on_select="rerun",
        selection_mode="single-row",
        key="log_decisiones_tabla",
        column_config={
            "Razón": st.column_config.TextColumn(width="large"),
            "Link al borrador": st.column_config.TextColumn(width="medium"),
        },
    )
    filas_log = evento_log.selection["rows"] if evento_log and evento_log.selection else []
    if filas_log:
        fila_log_sel = df_log.iloc[filas_log[0]]
        draft_id_sel = fila_log_sel["draft_id"]
        if pd.notna(draft_id_sel):
            draft_match = next((d for d in db.listar_drafts() if d["draft_id"] == int(draft_id_sel)), None)
            if draft_match:
                st.markdown(
                    f'<div class="chat-bubble draft"><span class="stamp">Borrador #{draft_match["draft_id"]} · {draft_match["status"]}</span>{draft_match["contenido"]}</div>',
                    unsafe_allow_html=True,
                )
        elif fila_log_sel["decision"] == "escalar_humano" and fila_log_sel.get("resumen"):
            st.markdown(
                f'<div class="chat-bubble"><span class="stamp">Resumen para el agente</span>{fila_log_sel["resumen"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("Este lead no generó borrador (fue ignorado).")


_TABLAS_B_KEYS = ["tabla_b_no_manejadas", "tabla_b_pendientes", "tabla_b_manejadas"]


def _cerrar_modal_b():
    """Callback de on_dismiss (X, Escape, clic afuera). No basta con
    borrar _modal_b_lead_id: si no se limpia TAMBIÉN la selección de la
    fila en su tabla, en el próximo rerun el código la vuelve a leer como
    "hubo un clic" sobre ese mismo lead y reabre el modal al instante —
    el bug de "nunca se cierra"."""
    st.session_state["_modal_b_lead_id"] = None
    for key in _TABLAS_B_KEYS:
        st.session_state.pop(key, None)


_ETIQUETA_TIPO_DRAFT = {
    "pedir_telefono": "pedido de teléfono",
}


@st.dialog("Detalle del lead", on_dismiss=_cerrar_modal_b)
def mostrar_detalle_lead_b(lead_id):
    """Ventana emergente con el detalle completo de un lead — y, a
    diferencia de un simple visor, las acciones reales pasan aquí mismo
    (aplicar disposición, completar el teléfono, aprobar el borrador) en
    vez de obligar a cerrarla y buscar la fila otra vez."""
    _contenido_modal_b(lead_id)


@st.fragment
def _contenido_modal_b(lead_id):
    """Todo lo interactivo del modal vive en un fragmento: un clic adentro
    (aplicar disposición, aprobar/descartar, enviar un mensaje) solo vuelve
    a correr ESTE fragmento (st.rerun(scope="fragment")), no la app entera
    — así la ventana no se cierra y se reabre en cada clic, se siente como
    un panel que se actualiza en el sitio."""
    lead = db.get_lead(lead_id)
    if not lead:
        st.error("Este lead ya no existe (puede que se haya reiniciado el panel).")
        return

    badge = lead["estado"]
    st.markdown(
        f'<h3 style="margin:0 0 4px;">{lead["lead_id"]} <span class="badge {badge}">{badge.replace("_"," ")}</span></h3>'
        f'<div style="color:var(--ink-muted); font-size:12.5px; margin-bottom:14px;">'
        f'{lead["creador"]} · {lead["canal"]} · {lead.get("telefono") or "sin teléfono"} · llegó {lead["timestamp"]}</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    c1.metric("Etapa actual", lead["stage"])
    c2.metric("Decisión del agente", lead["estado"])

    if lead.get("monto_deuda") or lead.get("tipo_deuda"):
        st.markdown(
            f"**Pre-calificación:** monto {lead.get('monto_deuda') or '—'} · "
            f"tipo de deuda {lead.get('tipo_deuda') or '—'} · "
            f"interés en Consejero: {'sí' if lead.get('interes_consejero') else 'no'}"
        )

    drafts_lead = [d for d in db.listar_drafts() if d["lead_id"] == lead_id]
    pendiente = next((d for d in drafts_lead if d["status"] == "pending_review"), None)

    # ---- 1. Teléfono faltante: se arregla aquí mismo, no solo se avisa ----
    if not lead.get("telefono"):
        motivo_tel = " — por eso el último mensaje le está pidiendo justamente ese dato" if pendiente and pendiente.get("tipo") == "pedir_telefono" else ""
        st.warning(
            f"Este lead no tiene teléfono — no se puede transferir al partner hasta conseguirlo{motivo_tel}.",
            icon="⚠️",
        )
        with st.form(f"form_tel_{lead_id}", clear_on_submit=True):
            nuevo_tel = st.text_input("Agregar teléfono", placeholder="3001234567")
            guardar_tel = st.form_submit_button("Guardar y reintentar transferencia", type="primary")
        if guardar_tel:
            if not nuevo_tel.strip():
                st.error("Escribe un teléfono antes de guardar.")
            else:
                db.upsert_lead(
                    lead_id, lead["timestamp"], lead["creador"], lead["canal"],
                    lead["mensaje"], nuevo_tel.strip(), lead["estado"],
                )
                r = crm_automation.aplicar_disposicion(lead_id, "Transferido")
                if r["status"] == "ok":
                    st.success(f"Teléfono guardado y transferido → {r['stage']}.")
                elif r["status"] == "borrador_pendiente":
                    st.warning("Teléfono guardado — pero debes aprobar o descartar el borrador de WhatsApp pendiente antes de poder transferir.")
                else:
                    st.info("Teléfono guardado.")
                st.rerun(scope="fragment")

    # ---- 2. Conversación estilo WhatsApp: mensaje del lead primero, y
    # luego cada mensaje que ya le mandamos, en orden cronológico ----
    st.markdown("---")
    st.markdown("**Conversación de WhatsApp**")
    st.markdown(
        f'<div class="chat-bubble"><span class="stamp">{lead["creador"]} · {lead["timestamp"]}</span>{lead["mensaje"]}</div>',
        unsafe_allow_html=True,
    )
    resueltos = sorted([d for d in drafts_lead if d["status"] in ("aprobado", "descartado")], key=lambda d: d["draft_id"])
    for d in resueltos:
        etiqueta = _ETIQUETA_TIPO_DRAFT.get(d["tipo"])
        stamp = d["timestamp"] + (f" · {etiqueta}" if etiqueta else "") + (" · descartado" if d["status"] == "descartado" else "")
        clase = "chat-bubble draft" + (" descartado" if d["status"] == "descartado" else "")
        st.markdown(f'<div class="{clase}"><span class="stamp">{stamp}</span>{d["contenido"]}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sin-respuesta">Este lead no ha enviado respuesta — este WhatsApp de demo es de solo salida, no recibe mensajes reales.</div>',
        unsafe_allow_html=True,
    )

    # ---- 3. Borrador sin enviar, si lo hay — se revisa aquí mismo, nunca
    # se manda solo ----
    if pendiente:
        etiqueta = _ETIQUETA_TIPO_DRAFT.get(pendiente["tipo"])
        st.markdown(f"**Borrador sin enviar{f' — {etiqueta}' if etiqueta else ''}**")
        texto_editado = st.text_area(
            "Editar antes de aprobar", value=pendiente["contenido"],
            key=f"draft_edit_{pendiente['draft_id']}", label_visibility="collapsed",
        )
        bcol1, bcol2 = st.columns(2)
        if bcol1.button("Aprobar y enviar", type="primary", key=f"aprobar_{pendiente['draft_id']}", use_container_width=True):
            db.actualizar_draft(pendiente["draft_id"], texto_editado, "aprobado")
            st.rerun(scope="fragment")
        if bcol2.button("Descartar", key=f"descartar_{pendiente['draft_id']}", use_container_width=True):
            db.actualizar_draft(pendiente["draft_id"], pendiente["contenido"], "descartado")
            st.rerun(scope="fragment")

    st.markdown("---")

    # ---- 4. Cambiar de stage sin salir del modal, maneje o no maneje ----
    st.markdown("**Cambiar de stage**")
    dcol1, dcol2 = st.columns([3, 2])
    disposicion_sel = dcol1.selectbox(
        "Disposición", ["", *crm_automation.STAGE_MAP.keys()],
        key=f"disp_sel_{lead_id}", label_visibility="collapsed",
    )
    forzar_webhook_caido = st.checkbox(
        "Simular caída del webhook del CRM al aplicar (se reintenta solo 2 veces antes de ir a la cola de fallos)",
        key=f"forzar_webhook_{lead_id}",
    )
    if dcol2.button("Aplicar", type="primary", key=f"aplicar_btn_{lead_id}", use_container_width=True):
        if not disposicion_sel:
            st.warning("Selecciona una disposición primero.")
        else:
            r = crm_automation.aplicar_disposicion(lead_id, disposicion_sel, forzar_fallo_webhook=forzar_webhook_caido)
            if r["status"] == "ok":
                intentos = r.get("intentos_webhook", 1)
                st.success(f"→ **{r['stage']}**. Borrador de WhatsApp generado" + (f" (tras {intentos} intentos)." if intentos > 1 else "."))
            elif r["status"] == "borrador_pendiente":
                st.warning("Debes aprobar o descartar el borrador de WhatsApp pendiente antes de aplicar una disposición.")
            elif r["status"] == "pendiente_dato":
                st.warning(f"Sin teléfono → **{r['stage']}**. Se le pidió el dato por WhatsApp.")
            elif r["status"] == "escalado":
                st.warning("No se pudo aplicar — se escaló a revisión humana.")
            else:
                st.error(f"Error ({r.get('motivo')}) → enviado a la cola de fallos.")
            st.rerun(scope="fragment")

    audit_lead = [a for a in db.listar_audit_trail() if a["lead_id"] == lead_id]
    if audit_lead:
        st.markdown("---")
        st.markdown("**Historial de auditoría de este lead**")
        st.dataframe(
            pd.DataFrame(audit_lead)[["timestamp", "actor", "accion", "estado_anterior", "estado_nuevo"]],
            use_container_width=True, hide_index=True,
        )


# --------------------------------------------------------------- top bar --
# Nada de sidebar: la navegación (pestañas) queda arriba del todo, como en
# un sitio tipo Notion — banner delgado, barra de marca, y debajo las
# pestañas, sin título/hero por encima que empuje todo hacia abajo.
st.markdown(
    '<div class="top-banner"><b>Escenario 100% ficticio</b> — ni la marca, ni los leads, '
    "ni las inscripciones del partner existen. Nada aquí toca un sistema real.</div>",
    unsafe_allow_html=True,
)

topbar_l, topbar_r = st.columns([4, 1])
with topbar_l:
    st.markdown(
        '<div class="topbar-brand">Salvaguardas Doble B '
        '<span class="topbar-sub">× Consejería Clara — prueba técnica Influgain</span></div>',
        unsafe_allow_html=True,
    )
with topbar_r:
    if st.button("Reiniciar panel", use_container_width=True):
        resetear_operacion_en_vivo()
        st.rerun()

tab_inicio, tab_a, tab_b, tab_c, tab_d = st.tabs(
    ["Inicio", "Leads que llegan", "B · CRM y disposiciones", "C · Datos y reporting", "D · Contenido"]
)

# ======================================================================= #
# INICIO                                                                   #
# ======================================================================= #
with tab_inicio:
    st.markdown('<span class="eyebrow">Prueba técnica · Influgain</span>', unsafe_allow_html=True)
    st.title("Un sistema que sigue trabajando aunque nadie esté mirando")
    st.markdown(
        '<p class="lede">Salvaguardas Doble B hace marketing de alivio de deudas vía creadores. '
        "Los leads escriben por chat a cualquier hora; este panel muestra qué decide el sistema "
        "solo y en qué momento le pasa el control a un humano.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    leads_vivo = db.listar_leads()
    decisiones = db.listar_decisiones()
    fallos = db.listar_fallos_pendientes()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads en operación (vivo)", len(leads_vivo))
    c2.metric("Decisiones del agente", len(decisiones))
    c3.metric("Fallos pendientes", len(fallos))
    funnel_hist = reporting.calcular_funnel()["general"]
    c4.metric("Tasa de transferencia (histórico)", f"{funnel_hist['tasa_transferencia_pct']}%")

    st.markdown("---")
    st.subheader("Qué hace cada pestaña")
    cc1, cc2, cc3, cc4 = st.columns(4)
    with cc1:
        st.markdown("**Leads que llegan (A)**")
        st.caption("30% — Ingesta y clasifica cada mensaje nuevo solo: responder, ignorar o escalar a un humano.")
    with cc2:
        st.markdown("**B · CRM y disposiciones**")
        st.caption("30% — Aplica disposiciones, mueve etapas, genera borradores de WhatsApp y maneja fallos.")
    with cc3:
        st.markdown("**C · Datos y reporting**")
        st.caption("25% — Limpia el CSV sucio del partner, calcula el funnel y qué rompería comisiones.")
    with cc4:
        st.markdown("**D · Contenido**")
        st.caption("15% — Genera guiones cortos priorizados, cada uno trazable a una fuente real.")

    st.markdown("---")
    st.caption(
        "Documentos complementarios en el repo: README.md · NOTA_ESCALA.md · NOTA_IA.md · DECISIONES.md"
    )

# ======================================================================= #
# LEADS QUE LLEGAN (EJERCICIO A)                                           #
# ======================================================================= #
with tab_a:
    st.markdown(
        '<span class="eyebrow">Ejercicio A · 30%</span>'
        '<span style="font-size:13px;color:var(--ink-muted);"> — cada mensaje nuevo pasa directo a procesamiento, sin que nadie lo toque.</span>',
        unsafe_allow_html=True,
    )
    st.markdown("### Leads que llegan")

    if not st.session_state["primera_carga_hecha"]:
        # ---- Estado inicial: todavía no se ha hecho la primera carga ----
        st.markdown("#### Primera carga")
        st.caption(f"Antes de que el panel empiece a recibir leads, cárgalo con un set inicial ({len(CARGA_DEFECTO)} leads).")
        if st.button("Cargar leads por defecto", type="primary"):
            for i, (creador, canal, mensaje, telefono) in enumerate(CARGA_DEFECTO, start=1):
                ingresar_lead(creador, canal, mensaje, telefono, lead_id=f"P{i:03d}")
            st.session_state["primera_carga_hecha"] = True
            st.rerun()

        with st.expander("O añade un lead manualmente para empezar"):
            with st.form("form_lead_inicial", clear_on_submit=True):
                fc1, fc2, fc3 = st.columns(3)
                creador = fc1.text_input("creador", placeholder="@carla.finanzas")
                canal = fc2.selectbox("canal", ["CTWA", "organico"])
                telefono = fc3.text_input("teléfono (opcional)", placeholder="3001234567")
                mensaje = st.text_area("mensaje del lead", placeholder="Escribe el mensaje, como si fuera un chat real...")
                enviado = st.form_submit_button("Añadir e iniciar", type="primary")
            if enviado and creador and mensaje:
                ingresar_lead(creador, canal, mensaje, telefono or None)
                st.session_state["primera_carga_hecha"] = True
                st.rerun()

    else:
        # ---- Ya hubo primera carga: controles de operación en vivo ----
        ctrl1, ctrl2 = st.columns([2, 1])
        with ctrl1:
            activo = st.toggle(
                "Generar un lead nuevo cada 30 segundos (totalmente aleatorio)",
                key="auto_gen_activo",
            )
            if activo:
                st.caption("Activo — cada 30s entra un lead nuevo del pool y pasa directo a procesamiento. No necesitas hacer nada.")
            else:
                st.caption("Apagado — actívalo para que el panel reciba leads solo, como lo haría un webhook real.")
        with ctrl2:
            with st.popover("Añadir lead manual"):
                with st.form("form_lead_manual", clear_on_submit=True):
                    creador = st.text_input("creador", placeholder="@carla.finanzas")
                    canal = st.selectbox("canal", ["CTWA", "organico"])
                    telefono = st.text_input("teléfono (opcional)", placeholder="3001234567")
                    mensaje = st.text_area("mensaje", placeholder="Mensaje del lead...")
                    enviado = st.form_submit_button("Añadir al stack", type="primary")
                if enviado and creador and mensaje:
                    ingresar_lead(creador, canal, mensaje, telefono or None)
                    st.rerun()

        stack_fragment()

        with st.expander("Reglas de clasificación (editables fuera del código)"):
            st.caption(
                "Viven en rules/rules.yaml, no en el código del agente. Se leen de nuevo en cada "
                "mensaje — cambia algo aquí, guarda, y el próximo lead ya se clasifica distinto, "
                "sin reiniciar el panel."
            )
            reglas_texto_actual = RULES_PATH.read_text(encoding="utf-8")
            reglas_editadas = st.text_area(
                "rules/rules.yaml", value=reglas_texto_actual, height=320, key="reglas_editor", label_visibility="collapsed",
            )
            rcol1, rcol2 = st.columns([1, 3])
            if rcol1.button("Guardar reglas"):
                try:
                    yaml.safe_load(reglas_editadas)
                except yaml.YAMLError as e:
                    st.error(f"El YAML no es válido, no se guardó: {e}")
                else:
                    RULES_PATH.write_text(reglas_editadas, encoding="utf-8")
                    st.success("Reglas guardadas. El próximo mensaje ya se clasifica con los valores nuevos.")

# Colores por valor para que la tabla de la pestaña B se lea de un vistazo
# en el video — qué lead está en qué etapa, sin tener que leer el texto.
_COLOR_DECISION = {"responder": "#eaf1fe", "escalar_humano": "#fef3dc", "ignorar": "#f1f2f4"}
_COLOR_ETAPA = {
    "Reintento": "#fef3dc",
    "Información Enviada": "#eaf1fe",
    "Transferido al Partner": "#dcfce7",
    "Agendado": "#fef3dc",
    "Descartado": "#f1f2f4",
    "Pendiente de Teléfono": "#fde2e1",
}


def _colorear_fila_b(row):
    estilos = []
    for col in row.index:
        bg = _COLOR_DECISION.get(row[col]) if col == "Decisión" else None
        bg = _COLOR_ETAPA.get(row[col]) if col == "Etapa actual" else bg
        estilos.append(f"background-color:{bg}" if bg else "")
    return estilos


# ======================================================================= #
# EJERCICIO B — MÓDULO 1                                                   #
# ======================================================================= #
with tab_b:
    st.markdown('<span class="eyebrow">Ejercicio B · 30%</span>', unsafe_allow_html=True)
    st.header("Nadie se pierde en la fila, ni siquiera cuando algo falla")
    st.markdown(
        '<p class="lede">Cuando un humano aplica una disposición, el sistema mueve la etapa, '
        "redacta el WhatsApp correspondiente y deja constancia en el audit trail.</p>",
        unsafe_allow_html=True,
    )

    leads = db.listar_leads()
    if not leads:
        st.info("No hay leads todavía — ve a la pestaña 'Leads que llegan' para hacer la primera carga.")
    else:
        df_click = pd.DataFrame(leads)[["lead_id", "mensaje", "estado", "stage", "creador", "canal"]].rename(columns={
            "lead_id": "ID", "mensaje": "Mensaje", "estado": "Decisión",
            "stage": "Etapa actual", "creador": "Creador", "canal": "Canal",
        })
        st.caption("Haz clic en una fila para ver el detalle completo en una ventana emergente.")

        GRUPOS_ETAPA = [
            ("No manejadas", ["Nuevo"], "tabla_b_no_manejadas"),
            ("Pendientes", ["Reintento", "Agendado", "Pendiente de Teléfono", "Información Enviada"], "tabla_b_pendientes"),
            ("Manejadas", ["Transferido al Partner", "Descartado"], "tabla_b_manejadas"),
        ]

        lead_id_click = None
        for titulo, etapas, key in GRUPOS_ETAPA:
            subset = df_click[df_click["Etapa actual"].isin(etapas)].reset_index(drop=True)
            with st.expander(f"{titulo} · {len(subset)}", expanded=True):
                if subset.empty:
                    st.caption("Ninguno en este momento.")
                    continue
                # Sin "height" fijo: así, al abrir en pantalla completa (ícono
                # de la esquina de la tabla), Streamlit sí expande la tabla
                # para ocupar toda la pantalla en vez de dejarla con el mismo
                # tamaño chico y el resto en blanco.
                evento = st.dataframe(
                    subset.style.apply(_colorear_fila_b, axis=1),
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key=key,
                    column_config={"Mensaje": st.column_config.TextColumn(width="large")},
                )
                filas = evento.selection["rows"] if evento and evento.selection else []
                if filas:
                    lead_id_click = subset.iloc[filas[0]]["ID"]

        # Un clic nuevo en una fila cambia CUÁL lead debe mostrarse; una vez
        # fijado, el modal se vuelve a invocar en CADA rerun mientras el
        # estado siga apuntando a ese lead — así los botones de adentro
        # (aplicar disposición, guardar teléfono, aprobar borrador) pueden
        # hacer st.rerun() y la ventana se mantiene abierta con datos
        # frescos, en vez de cerrarse sola. Se limpia solo al cerrarla
        # (on_dismiss) o al seleccionar un lead distinto.
        if lead_id_click is not None and lead_id_click != st.session_state.get("_modal_b_lead_id"):
            st.session_state["_modal_b_lead_id"] = lead_id_click

        if st.session_state.get("_modal_b_lead_id"):
            mostrar_detalle_lead_b(st.session_state["_modal_b_lead_id"])

    st.markdown("### Último borrador de WhatsApp generado")
    drafts = db.listar_drafts()
    if drafts:
        ultimo = sorted(drafts, key=lambda d: d["draft_id"])[-1]
        st.markdown(
            f'<div class="chat-bubble draft"><span class="stamp">{ultimo["canal"]} · {ultimo["status"]}</span>{ultimo["contenido"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Todavía no se ha generado ningún borrador.")

    st.markdown("### Historial de auditoría")
    audit = db.listar_audit_trail()
    if audit:
        df_audit = pd.DataFrame(audit).sort_values("id", ascending=False)
        st.dataframe(
            df_audit[["timestamp", "lead_id", "actor", "accion", "estado_anterior", "estado_nuevo", "detalle"]],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("Sin movimientos todavía.")

    st.markdown("---")
    st.subheader("Manejo de errores simulado")
    st.caption(
        "Teléfono faltante, lead inexistente, disposición inválida o un webhook caído — nada se pierde en "
        "silencio. El webhook caído se simula con el checkbox dentro del detalle de cada lead (al aplicar "
        "una disposición real); estos dos botones cubren los otros dos casos."
    )

    e2, e3 = st.columns(2)
    if e2.button("Simular transferencia sin teléfono"):
        db.upsert_lead("SIM-NOPHONE", datetime.now(timezone.utc).isoformat(), "@demo", "CTWA", "lead de prueba sin teléfono", None, "responder")
        r = crm_automation.aplicar_disposicion("SIM-NOPHONE", "Transferido")
        st.warning(f"SIM-NOPHONE: sin teléfono → queda en **{r.get('stage')}** y se le pidió el dato por WhatsApp.")
        st.rerun()
    if e3.button("Simular disposición inválida"):
        r = crm_automation.aplicar_disposicion(leads[0]["lead_id"] if leads else "N/A", "Disposición Inventada")
        st.error(f"Resultado: {r}")
        st.rerun()

    st.markdown("#### Cola de fallos (dead-letter queue)")
    fallos = db.listar_fallos_pendientes()
    if st.button("Reintentar manualmente"):
        resultados = crm_automation.reintentar_fallos()
        resueltos = [r for r in resultados if r["status"] == "resuelto"]
        if resueltos:
            st.success(f"{len(resueltos)} fallo(s) resueltos al reintentar: {', '.join(r['lead_id'] for r in resueltos)}.")
        st.rerun()
    if fallos:
        st.dataframe(pd.DataFrame(fallos)[["tipo", "error", "retry_count", "status"]], use_container_width=True, hide_index=True)
    else:
        st.caption("Sin fallos pendientes.")

# ======================================================================= #
# EJERCICIO C — MÓDULO 2                                                   #
# ======================================================================= #
with tab_c:
    st.markdown('<span class="eyebrow">Ejercicio C · 25%</span>', unsafe_allow_html=True)
    st.header("Los números no mienten, pero los datos sí engañan")
    st.markdown(
        '<p class="lede">Las inscripciones que manda el partner llegan con errores reales: '
        "teléfonos mal capturados, creadores sin asignar, fechas imposibles, duplicados.</p>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Sube el CSV de inscripciones del partner (opcional — si no subes nada, se usa el dataset incluido)",
        type="csv",
    )
    if uploaded is not None:
        enroll_raw = pd.read_csv(uploaded, dtype=str)
        fuente_txt = f"archivo subido: {uploaded.name}"
    else:
        enroll_raw = reporting.cargar_enrollments_crudo()
        fuente_txt = "data/partner_enrollments.csv (incluido en el repo)"
    st.caption(f"Usando {fuente_txt} — {len(enroll_raw)} filas.")

    problemas = reporting.detectar_problemas(enroll_raw)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sin creator_id", int(problemas["creator_id"].sum()))
    m2.metric("Teléfono inválido", int(problemas["telefono"].sum()))
    m3.metric("Fecha inválida", int(problemas["fecha_inscripcion"].sum()))
    m4.metric("Filas duplicadas", int(problemas["enrollment_id"].sum()))

    st.markdown("#### Datos sucios detectados")
    cols_resaltar = ["creator_id", "telefono", "fecha_inscripcion", "enrollment_id"]

    def resaltar(row):
        return [
            "background-color:#f6d6cc" if (c in cols_resaltar and problemas.loc[row.name, c]) else ""
            for c in row.index
        ]

    st.dataframe(enroll_raw.style.apply(resaltar, axis=1), use_container_width=True, hide_index=True)

    if st.button("🧹 Limpiar y normalizar datos", type="primary"):
        st.session_state["c_limpio"] = True

    if st.session_state.get("c_limpio"):
        leads_c, enroll_limpio, notas = reporting.cargar_y_limpiar(enroll_df=enroll_raw)

        st.markdown("#### Datos limpios")
        st.dataframe(enroll_limpio, use_container_width=True, hide_index=True)

        st.markdown("**Qué se cambió y por qué:**")
        for n in notas:
            st.markdown(f"- {n}")

        funnel = reporting.calcular_funnel(leads_c, enroll_limpio)["general"]
        st.markdown("#### Métricas del funnel")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Leads totales", funnel["leads_totales"])
        f2.metric("Pre-calificados", funnel["pre_calificados"])
        f3.metric("Transferidos", funnel["transferidos"])
        f4.metric("Inscritos activos", funnel["inscritos_activos"])
        st.progress(min(funnel["tasa_transferencia_pct"] / 100, 1.0), text=f"Tasa de transferencia: {funnel['tasa_transferencia_pct']}%")

        estancados = reporting.leads_estancados(leads_c, enroll_limpio)
        st.markdown(f"#### Leads estancados ({len(estancados)})")
        if estancados:
            st.dataframe(pd.DataFrame(estancados), use_container_width=True, hide_index=True)
        else:
            st.caption("Ninguno en este momento.")

        comisiones = reporting.reporte_ruptura_comisiones(leads_c, enroll_limpio)
        st.markdown("#### Qué rompería el pago de comisiones")
        st.markdown(
            f"""<div class="callout">
            <strong>{comisiones['inscripciones_sin_creator_id']} inscripciones sin creador asignado</strong> y
            <strong>{comisiones['inscripciones_con_telefono_mismatch']} con teléfono que no coincide</strong>
            con el lead original.<br><br>
            {comisiones['resumen']}<br><br>
            En la práctica esto significa que, si la agencia paga comisión a creadores sobre estas
            inscripciones sin filtrar primero estos dos problemas, puede estar pagando de más (a un
            "sin_atribuir" genérico, o al creador equivocado por un teléfono mal capturado) o de menos
            (negando una comisión legítima porque el sistema no logra cruzar el lead con su inscripción).
            Por eso esta limpieza no es un paso cosmético: es la diferencia entre un reporte financiero
            confiable y uno que esconde errores de atribución.
            </div>""",
            unsafe_allow_html=True,
        )

# ======================================================================= #
# EJERCICIO D                                                              #
# ======================================================================= #
with tab_d:
    st.markdown('<span class="eyebrow">Ejercicio D · 15%</span>', unsafe_allow_html=True)
    st.header("Guiones que nacen de preguntas reales, no de la nada")
    st.markdown(
        '<p class="lede">Cada guion está atado a una fuente concreta y se prioriza por qué tan '
        "frecuente y urgente es, no por capricho.</p>",
        unsafe_allow_html=True,
    )

    for g in generar_guiones(top_n=3):
        st.markdown(
            f"""<div class="script-card">
            <div class="strip"><span>Fuente {g['fuente_id']}</span><span>score {g['prioridad_score']} · {g['duracion_estimada_seg']}s</span></div>
            <div class="body">{g['guion']}</div>
            </div>""",
            unsafe_allow_html=True,
        )

"""Panel operativo en Streamlit — Salvaguardas Doble B × Consejería Clara.

Reutiliza toda la lógica de negocio ya construida y probada en src/
(rules_engine, prequalification_agent, crm_automation, reporting,
content_system). Esta es solo la capa de interfaz.

Correr: streamlit run streamlit_app.py
"""
import random
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src import crm_automation, db, reporting
from src.content_system import generar_guiones
from src.prequalification_agent import procesar_mensaje_entrante

st.set_page_config(
    page_title="Salvaguardas Doble B — Panel de Operación",
    page_icon="🗂️",
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
.chat-bubble .stamp { font-size:9.5px; text-transform:uppercase; letter-spacing:.04em; opacity:.7; display:block; margin-bottom:3px; }
.script-card { background:#fff; border:1px solid var(--border); border-radius:14px; overflow:hidden; margin-bottom:12px; }
.script-card .strip { background: var(--brand-tint); color: var(--brand-dark); font-size:11px; font-weight:700; padding:8px 14px; display:flex; justify-content:space-between; }
.script-card .body { padding:14px; font-size:12.8px; color: var(--ink-soft); white-space:pre-wrap; line-height:1.55; }
.callout { background: var(--amber-tint); border:1px solid #f3dca8; border-left:3px solid var(--amber); border-radius:10px; padding:16px 18px; font-size:13.3px; color:#6b4414; }
.lead-card { background:#fff; border:1px solid var(--border); border-radius:14px; padding:20px 22px; margin-top:4px; }
.lead-card h4 { margin:0 0 4px; font-size:17px; font-weight:800; }
.lead-card .meta { color: var(--ink-muted); font-size:12.5px; margin-bottom:12px; }
.lead-card .field-label { font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color: var(--ink-muted); font-weight:700; margin-top:14px; }
.lead-card .field-value { font-size:14px; color: var(--ink); margin-top:2px; }
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
# Carga por defecto: un set curado y reconocible (no aleatorio) para la
# primera carga, mezclando los 3 caminos de clasificación.
CARGA_DEFECTO = [
    ("@carla.finanzas", "CTWA", "Hola, tengo una deuda de tarjeta de credito de 3200000 y no se que hacer", "3001000001"),
    ("@juanfi_libre", "organico", "Buenas, debo libranza por 11000000, quiero informacion del programa", "3001000002"),
    ("@manu.deudas", "CTWA", "Me interesa el programa, tengo una deuda hipotecaria de 38000000", "3001000003"),
    ("@laura_consejos", "organico", "Hola vi el video, debo como 2600000 en tarjeta, quiero hablar con un consejero", "3001000004"),
    ("@pedro.ahorra", "CTWA", "Buenas tardes, tengo varias deudas y no sé por dónde empezar, suman 17000000", "3001000005"),
    ("@carla.finanzas", "organico", "Hola quiero asesoria para mi libranza de nomina de 8700000", "3001000006"),
    ("@manu.deudas", "CTWA", "Me llego una demanda por mi tarjeta de credito, que hago", "3001000007"),
    ("@juanfi_libre", "organico", "Un abogado me contacto por el embargo de mi cuenta, estoy preocupado", "3001000008"),
    ("@pedro.ahorra", "CTWA", "No me interesa, quitame de esta lista por favor", "3001000009"),
    ("@laura_consejos", "organico", "Stop, no quiero recibir mas mensajes", "3001000010"),
    ("@carla.finanzas", "CTWA", "Hola, quiero mas informacion sobre el programa", "3001000011"),
    ("@manu.deudas", "organico", "Buenas, como funciona la consejeria de ustedes", "3001000012"),
]

# Pool para la generación automática — plantillas parecidas a mensajes
# reales, combinadas con montos, creadores y teléfonos aleatorios en cada
# generación para que ningún lead se repita igual.
CREADORES_POOL = [
    "@carla.finanzas", "@juanfi_libre", "@manu.deudas", "@laura_consejos",
    "@pedro.ahorra", "@sofia.claridad", "@andres.deudafree", "@valen.consejos",
]
MENSAJES_POOL = [
    "Hola, tengo una deuda de tarjeta de credito de {monto} y no se que hacer",
    "Buenas, debo libranza por {monto}, quiero informacion del programa",
    "Me interesa el programa, tengo una deuda hipotecaria de {monto}",
    "Hola vi el video, debo como {monto} en tarjeta, quiero hablar con un consejero",
    "Buenas tardes, tengo varias deudas y no sé por dónde empezar, suman {monto}",
    "Hola quiero asesoria para mi libranza de nomina de {monto}",
    "Vi el reel de ustedes, tengo deudas de consumo por {monto}, me pueden ayudar?",
    "Hola, quiero saber si me pueden ayudar con mi credito de {monto}",
    "Buenas, una amiga me recomendo escribirles, debo {monto} en tarjetas",
    "Me llego una demanda por mi tarjeta de credito, que hago",
    "Un abogado me contacto por el embargo de mi cuenta, estoy muy preocupado",
    "Esto es urgente, me amenazan con quitarme la casa",
    "Quiero denunciar un fraude con mi tarjeta",
    "La empresa esta en quiebra y no se que hacer con mis deudas",
    "No me interesa, quitame de esta lista por favor",
    "Stop, no quiero recibir mas mensajes",
    "Dejen de escribirme, es spam",
    "Hola, quiero mas informacion sobre el programa",
    "Buenas, como funciona la consejeria de ustedes",
    "Hola vi el anuncio, me pueden contar mas",
]
MONTOS_POOL = [1800000, 2600000, 3200000, 4100000, 5600000, 7300000, 9000000, 11500000, 15000000, 22000000, 38000000]


def _telefono_aleatorio():
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
            st.toast(f"📥 Nuevo lead automático: {lead['lead_id']}")

    leads_actuales = db.listar_leads()
    st.markdown(f"#### Stack de leads &nbsp;·&nbsp; {len(leads_actuales)} en total")
    st.caption("Haz clic en una fila para ver el lead a detalle.")

    if not leads_actuales:
        st.info("Sin leads todavía.")
        return

    df_stack = pd.DataFrame(leads_actuales).sort_values("timestamp", ascending=False)
    df_view = df_stack[["lead_id", "timestamp", "creador", "canal", "mensaje", "estado"]].rename(columns={
        "lead_id": "ID", "timestamp": "Llegó", "creador": "Creador", "canal": "Canal",
        "mensaje": "Mensaje", "estado": "Decisión",
    })

    evento = st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        height=360,
        on_select="rerun",
        selection_mode="single-row",
        key="stack_leads_tabla",
        column_config={"Mensaje": st.column_config.TextColumn(width="large")},
    )

    filas_sel = evento.selection["rows"] if evento and evento.selection else []
    if not filas_sel:
        return

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
        detalle_html += f"""
      <div class="field-label">Por qué el sistema decidió esto</div>
      <div class="field-value">{ultima_decision['razon']}</div>
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


# ------------------------------------------------------------------ header --
with st.sidebar:
    st.markdown("### 🗂️ Salvaguardas Doble B")
    st.caption("× Consejería Clara — prueba técnica Influgain")
    st.markdown("---")
    st.markdown(
        "Escenario **100% ficticio**: ni la marca, ni los leads, ni las "
        "inscripciones del partner existen. Nada aquí toca un sistema real."
    )
    st.markdown("---")
    if st.button("🔄 Reiniciar panel (resetea leads en vivo)", use_container_width=True):
        resetear_operacion_en_vivo()
        st.rerun()
    st.caption("Esto reinicia solo la operación en vivo (pestañas A y B). Los datos del Ejercicio C viven en data/.")

st.markdown('<span class="eyebrow">Prueba técnica · Influgain</span>', unsafe_allow_html=True)
st.title("Un sistema que sigue trabajando aunque nadie esté mirando")
st.markdown(
    '<p class="lede">Salvaguardas Doble B hace marketing de alivio de deudas vía creadores. '
    "Los leads escriben por chat a cualquier hora; este panel muestra qué decide el sistema "
    "solo y en qué momento le pasa el control a un humano.</p>",
    unsafe_allow_html=True,
)

tab_inicio, tab_a, tab_b, tab_c, tab_d = st.tabs(
    ["🏠 Inicio", "Leads que llegan", "B · CRM y disposiciones", "C · Datos y reporting", "D · Contenido"]
)

# ======================================================================= #
# INICIO                                                                   #
# ======================================================================= #
with tab_inicio:
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
    st.markdown('<span class="eyebrow">Ejercicio A · 30%</span>', unsafe_allow_html=True)
    st.header("Leads que llegan")
    st.markdown(
        '<p class="lede">Cada fila es un mensaje que acaba de entrar por chat. En cuanto llega, '
        "pasa directo a procesamiento: el sistema lo clasifica solo, sin que nadie lo toque.</p>",
        unsafe_allow_html=True,
    )

    if not st.session_state["primera_carga_hecha"]:
        # ---- Estado inicial: todavía no se ha hecho la primera carga ----
        st.markdown("#### Primera carga")
        st.caption("Antes de que el panel empiece a recibir leads, cárgalo con un set inicial.")
        if st.button("📥 Cargar leads por defecto", type="primary"):
            for i, (creador, canal, mensaje, telefono) in enumerate(CARGA_DEFECTO, start=1):
                ingresar_lead(creador, canal, mensaje, telefono, lead_id=f"P{i:03d}")
            st.session_state["primera_carga_hecha"] = True
            st.rerun()

        with st.expander("➕ O añade un lead manualmente para empezar"):
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
                "🔁 Generar un lead nuevo cada 30 segundos (totalmente aleatorio)",
                key="auto_gen_activo",
            )
            if activo:
                st.caption("Activo — cada 30s entra un lead nuevo del pool y pasa directo a procesamiento. No necesitas hacer nada.")
            else:
                st.caption("Apagado — actívalo para que el panel reciba leads solo, como lo haría un webhook real.")
        with ctrl2:
            with st.popover("➕ Añadir lead manual"):
                with st.form("form_lead_manual", clear_on_submit=True):
                    creador = st.text_input("creador", placeholder="@carla.finanzas")
                    canal = st.selectbox("canal", ["CTWA", "organico"])
                    telefono = st.text_input("teléfono (opcional)", placeholder="3001234567")
                    mensaje = st.text_area("mensaje", placeholder="Mensaje del lead...")
                    enviado = st.form_submit_button("Añadir al stack", type="primary")
                if enviado and creador and mensaje:
                    ingresar_lead(creador, canal, mensaje, telefono or None)
                    st.rerun()

        st.markdown("---")
        stack_fragment()

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
        df = pd.DataFrame(leads)[["lead_id", "timestamp", "creador", "canal", "mensaje", "telefono", "estado", "stage"]]
        df = df.rename(columns={
            "lead_id": "ID", "timestamp": "Timestamp", "creador": "Creador", "canal": "Canal",
            "mensaje": "Mensaje del lead", "telefono": "Teléfono", "estado": "Decisión del agente",
            "stage": "Etapa actual",
        })
        df["Disposición a aplicar"] = ""

        edited = st.data_editor(
            df,
            column_config={
                "Disposición a aplicar": st.column_config.SelectboxColumn(
                    options=["", *crm_automation.STAGE_MAP.keys()],
                ),
                "Mensaje del lead": st.column_config.TextColumn(width="large"),
            },
            disabled=["ID", "Timestamp", "Creador", "Canal", "Mensaje del lead", "Teléfono", "Decisión del agente", "Etapa actual"],
            hide_index=True,
            use_container_width=True,
            key="crm_editor",
        )

        if st.button("Aplicar disposiciones seleccionadas", type="primary"):
            pendientes = edited[edited["Disposición a aplicar"] != ""]
            if pendientes.empty:
                st.info("No seleccionaste ninguna disposición en la tabla.")
            else:
                for _, row in pendientes.iterrows():
                    r = crm_automation.aplicar_disposicion(row["ID"], row["Disposición a aplicar"])
                    if r["status"] == "ok":
                        st.success(f"{row['ID']}: → **{r['stage']}**. Borrador de WhatsApp generado.")
                    elif r["status"] == "escalado":
                        st.warning(f"{row['ID']}: no se pudo aplicar ({r['motivo']}) → se escaló a revisión humana.")
                    else:
                        st.error(f"{row['ID']}: error ({r.get('motivo')}) → enviado a la cola de fallos.")
                st.rerun()

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
    st.caption("Teléfono faltante, lead inexistente, disposición inválida o un webhook caído — nada se pierde en silencio.")

    e1, e2, e3 = st.columns(3)
    if e1.button("Simular webhook caído"):
        crm_automation.simular_fallo_webhook(
            {"origen": "CRM externo", "intento": datetime.now(timezone.utc).isoformat()},
            "Timeout simulado: el webhook del CRM externo no respondió.",
        )
        st.rerun()
    if e2.button("Simular transferencia sin teléfono"):
        db.upsert_lead("SIM-NOPHONE", datetime.now(timezone.utc).isoformat(), "@demo", "CTWA", "lead de prueba sin teléfono", None, "responder")
        r = crm_automation.aplicar_disposicion("SIM-NOPHONE", "Transferido")
        st.warning(f"Resultado: {r}")
        st.rerun()
    if e3.button("Simular disposición inválida"):
        r = crm_automation.aplicar_disposicion(leads[0]["lead_id"] if leads else "N/A", "Disposición Inventada")
        st.error(f"Resultado: {r}")
        st.rerun()

    st.markdown("#### Cola de fallos")
    fallos = db.listar_fallos_pendientes()
    if st.button("Reintentar pendientes"):
        crm_automation.reintentar_fallos()
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

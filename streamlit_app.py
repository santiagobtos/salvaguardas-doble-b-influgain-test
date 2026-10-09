"""Panel operativo en Streamlit — Salvaguardas Doble B × Consejería Clara.

Reutiliza toda la lógica de negocio ya construida y probada en src/
(rules_engine, prequalification_agent, crm_automation, reporting,
content_system). Esta es solo la capa de interfaz.

Correr: streamlit run streamlit_app.py
"""
import random
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
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,420;0,9..144,650;1,9..144,500&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --brand:#2f5d50; --brand-dark:#1f453b; --brand-tint:#e5ede8;
  --clay:#b2553a; --clay-tint:#f4e3da; --gold:#a9802f; --gold-tint:#f3ead1;
  --ink:#2b2620; --ink-soft:#554f44; --ink-muted:#8a8272; --border:#e6ddc9;
}
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; color: var(--ink); letter-spacing: -.01em; }
.stApp { background: #f6f2ea; }
.eyebrow { font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--brand); font-weight: 700; margin-bottom: 2px; }
.lede { font-size: 15px; color: var(--ink-soft); max-width: 70ch; }
.badge { display:inline-block; font-size:10.5px; font-weight:700; text-transform:uppercase; padding:2px 9px; border-radius:999px; margin-left:6px;}
.badge.responder { background: var(--brand-tint); color: var(--brand-dark); }
.badge.escalar_humano { background: var(--clay-tint); color: var(--clay); }
.badge.ignorar { background: #ece8df; color: var(--ink-muted); }
.chat-bubble { background:#fffdf9; border:1px solid var(--border); border-radius:12px 12px 12px 3px; padding:10px 14px; font-size:13px; margin:8px 0; max-width:85%; }
.chat-bubble.draft { background: var(--brand-tint); border-color:#cfe0d7; border-radius:12px 12px 3px 12px; margin-left:auto; color: var(--brand-dark); }
.chat-bubble .stamp { font-size:9.5px; text-transform:uppercase; letter-spacing:.04em; opacity:.7; display:block; margin-bottom:3px; }
.script-card { background:#fffdf9; border:1px solid var(--border); border-radius:14px; overflow:hidden; margin-bottom:12px; }
.script-card .strip { background: var(--brand-tint); color: var(--brand-dark); font-size:11px; font-weight:700; padding:8px 14px; display:flex; justify-content:space-between; }
.script-card .body { padding:14px; font-size:12.8px; color: var(--ink-soft); white-space:pre-wrap; line-height:1.55; }
.callout { background: var(--gold-tint); border:1px solid #e6d3a3; border-left:3px solid var(--gold); border-radius:10px; padding:16px 18px; font-size:13.3px; color:#5c4620; }
</style>
""",
    unsafe_allow_html=True,
)

db.init_db()

# --------------------------------------------------------- datos iniciales --
SEED_POOL = [
    ("@carla.finanzas", "CTWA", "Hola, tengo una deuda de tarjeta de credito de 3200000 y no se que hacer", "300100000{n}"),
    ("@juanfi_libre", "organico", "Buenas, debo libranza por 11000000, quiero informacion del programa", "300100001{n}"),
    ("@manu.deudas", "CTWA", "Me interesa el programa, tengo una deuda hipotecaria de 38000000", "300100002{n}"),
    ("@laura_consejos", "organico", "Hola vi el video, debo como 2600000 en tarjeta, quiero hablar con un consejero", "300100003{n}"),
    ("@pedro.ahorra", "CTWA", "Buenas tardes, tengo varias deudas y no sé por dónde empezar, suman 17000000", "300100004{n}"),
    ("@carla.finanzas", "organico", "Hola quiero asesoria para mi libranza de nomina de 8700000", "300100005{n}"),
    ("@manu.deudas", "CTWA", "Me llego una demanda por mi tarjeta de credito, que hago", "300100006{n}"),
    ("@juanfi_libre", "organico", "Un abogado me contacto por el embargo de mi cuenta, estoy preocupado", "300100007{n}"),
    ("@pedro.ahorra", "CTWA", "No me interesa, quitame de esta lista por favor", "300100008{n}"),
    ("@laura_consejos", "organico", "Stop, no quiero recibir mas mensajes", "300100009{n}"),
    ("@carla.finanzas", "CTWA", "Hola, quiero mas informacion sobre el programa", "300100010{n}"),
    ("@manu.deudas", "organico", "Buenas, como funciona la consejeria de ustedes", "300100011{n}"),
]


def seed_inicial(n=18):
    if db.listar_leads():
        return
    for i in range(n):
        creador, canal, mensaje, tel_tpl = SEED_POOL[i % len(SEED_POOL)]
        lead_id = f"P{i+1:03d}"
        telefono = tel_tpl.format(n=i % 10)
        procesar_mensaje_entrante(lead_id, creador, canal, mensaje, telefono)


seed_inicial()

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
        db.reset_db()
        seed_inicial()
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
    ["🏠 Inicio", "A · Pre-calificación", "B · CRM y disposiciones", "C · Datos y reporting", "D · Contenido"]
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
        st.markdown("**A · Pre-calificación**")
        st.caption("30% — El agente clasifica cada mensaje nuevo solo: responder, ignorar o escalar a un humano.")
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
# EJERCICIO A                                                              #
# ======================================================================= #
with tab_a:
    st.markdown('<span class="eyebrow">Ejercicio A · 30%</span>', unsafe_allow_html=True)
    st.header("El primer mensaje nunca espera a que alguien se despierte")
    st.markdown(
        '<p class="lede">Un lead escribe a las 11:47pm. El equipo humano está dormido. '
        "En segundos, el sistema toma uno de tres caminos — y deja un rastro claro de por qué.</p>",
        unsafe_allow_html=True,
    )

    p1, p2, p3 = st.columns(3)
    p1.success("**Responder** — dentro de las reglas estándar: pre-califica y deja un borrador en cola humana. Nunca lo envía solo.")
    p2.warning("**Escalar a humano** — palabra de riesgo o monto fuera de rango: se registra el motivo, espera a una persona.")
    p3.info("**Ignorar** — el lead pide salir de la lista: se registra, no se le vuelve a escribir.")

    st.markdown("### Simular un mensaje entrante")
    with st.form("form_lead", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns(3)
        lead_id = fc1.text_input("lead_id", placeholder="L500")
        creador = fc2.text_input("creador", placeholder="@carla.finanzas")
        canal = fc3.selectbox("canal", ["CTWA", "organico"])
        telefono = st.text_input("teléfono (opcional)", placeholder="3001234567")
        mensaje = st.text_area("mensaje del lead", placeholder="Escribe el mensaje, como si fuera un chat real...")
        enviado = st.form_submit_button("Enviar al agente", type="primary")

    if enviado and lead_id and creador and mensaje:
        r = procesar_mensaje_entrante(lead_id, creador, canal, mensaje, telefono or None)
        badge = r["decision"]
        st.markdown(
            f'<div class="chat-bubble">{mensaje}</div>'
            f'<span class="badge {badge}">{badge.replace("_"," ")}</span> &nbsp; <small>{r["razon"]}</small>',
            unsafe_allow_html=True,
        )
        if r["draft_id"]:
            st.markdown(
                '<div class="chat-bubble draft"><span class="stamp">Borrador · pendiente de revisión</span>'
                "Se dejó una respuesta lista para que un humano la apruebe.</div>",
                unsafe_allow_html=True,
            )

    st.markdown("### Historial de decisiones")
    decisiones = db.listar_decisiones()
    if decisiones:
        df_dec = pd.DataFrame(decisiones).sort_values("id", ascending=False)
        st.dataframe(df_dec[["timestamp", "lead_id", "decision", "razon", "draft_id"]], use_container_width=True, hide_index=True)
    else:
        st.caption("Aún no hay decisiones registradas.")

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
        st.info("No hay leads todavía — usa 'Reiniciar panel' en la barra lateral.")
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

"""Capa de almacenamiento: SQLite local (nada de servicios externos).

Tablas:
- leads: estado vivo de cada lead que pasa por el sistema en esta demo.
- decisions_log: cada decisión del agente de pre-calificación (Ejercicio A).
- drafts: borradores de mensajes, nunca se envían solos (quedan en cola humana).
- audit_trail: historial de cambios de etapa del CRM (Ejercicio B).
- failed_queue: cola de fallos/reintentos (webhooks caídos, datos inválidos).
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "salvaguardas.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT PRIMARY KEY,
    timestamp TEXT,
    creador TEXT,
    canal TEXT,
    mensaje TEXT,
    telefono TEXT,
    estado TEXT,
    monto_deuda INTEGER,
    tipo_deuda TEXT,
    interes_consejero INTEGER,
    stage TEXT DEFAULT 'Nuevo'
);

CREATE TABLE IF NOT EXISTS decisions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    lead_id TEXT,
    decision TEXT,
    razon TEXT,
    draft_id INTEGER,
    resumen TEXT
);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT,
    timestamp TEXT,
    canal TEXT,
    contenido TEXT,
    status TEXT DEFAULT 'pending_review'
);

CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    lead_id TEXT,
    actor TEXT,
    accion TEXT,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    detalle TEXT
);

CREATE TABLE IF NOT EXISTS failed_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    tipo TEXT,
    payload_json TEXT,
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending_retry'
);
"""


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    try:
        conn.execute("ALTER TABLE decisions_log ADD COLUMN resumen TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # ya existe (base creada con un esquema anterior)
    conn.close()


def reset_db():
    """Borra todas las tablas. Solo para la demo (cli.py demo)."""
    conn = get_connection()
    conn.executescript(
        "DELETE FROM leads; DELETE FROM decisions_log; DELETE FROM drafts; "
        "DELETE FROM audit_trail; DELETE FROM failed_queue;"
    )
    conn.commit()
    conn.close()


def upsert_lead(lead_id, timestamp, creador, canal, mensaje, telefono, estado):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO leads (lead_id, timestamp, creador, canal, mensaje, telefono, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lead_id) DO UPDATE SET
            timestamp=excluded.timestamp, creador=excluded.creador, canal=excluded.canal,
            mensaje=excluded.mensaje, telefono=excluded.telefono, estado=excluded.estado
        """,
        (lead_id, timestamp, creador, canal, mensaje, telefono, estado),
    )
    conn.commit()
    conn.close()


def listar_leads():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM leads ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def actualizar_prequalificacion(lead_id, monto_deuda, tipo_deuda, interes_consejero):
    conn = get_connection()
    conn.execute(
        "UPDATE leads SET monto_deuda=?, tipo_deuda=?, interes_consejero=? WHERE lead_id=?",
        (monto_deuda, tipo_deuda, int(bool(interes_consejero)), lead_id),
    )
    conn.commit()
    conn.close()


def get_lead(lead_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM leads WHERE lead_id=?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def actualizar_stage(lead_id, nuevo_stage):
    conn = get_connection()
    conn.execute("UPDATE leads SET stage=? WHERE lead_id=?", (nuevo_stage, lead_id))
    conn.commit()
    conn.close()


def crear_draft(lead_id, timestamp, canal, contenido):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO drafts (lead_id, timestamp, canal, contenido) VALUES (?, ?, ?, ?)",
        (lead_id, timestamp, canal, contenido),
    )
    conn.commit()
    draft_id = cur.lastrowid
    conn.close()
    return draft_id


def actualizar_draft(draft_id, contenido, status):
    """Edición + aprobación/descarte humano de un borrador — el momento de
    revisión que exige la regla de negocio de no enviar nada solo."""
    conn = get_connection()
    conn.execute(
        "UPDATE drafts SET contenido=?, status=? WHERE draft_id=?",
        (contenido, status, draft_id),
    )
    conn.commit()
    conn.close()


def listar_drafts(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute("SELECT * FROM drafts WHERE status=? ORDER BY draft_id", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM drafts ORDER BY draft_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_decision(timestamp, lead_id, decision, razon, draft_id, resumen=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO decisions_log (timestamp, lead_id, decision, razon, draft_id, resumen) VALUES (?, ?, ?, ?, ?, ?)",
        (timestamp, lead_id, decision, razon, draft_id, resumen),
    )
    conn.commit()
    conn.close()


def listar_decisiones():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM decisions_log ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def registrar_audit(timestamp, lead_id, actor, accion, estado_anterior, estado_nuevo, detalle):
    conn = get_connection()
    conn.execute(
        """INSERT INTO audit_trail
           (timestamp, lead_id, actor, accion, estado_anterior, estado_nuevo, detalle)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (timestamp, lead_id, actor, accion, estado_anterior, estado_nuevo, detalle),
    )
    conn.commit()
    conn.close()


def listar_audit_trail():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM audit_trail ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def encolar_fallo(timestamp, tipo, payload, error):
    conn = get_connection()
    conn.execute(
        "INSERT INTO failed_queue (timestamp, tipo, payload_json, error) VALUES (?, ?, ?, ?)",
        (timestamp, tipo, json.dumps(payload, ensure_ascii=False), error),
    )
    conn.commit()
    conn.close()


def listar_fallos_pendientes():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM failed_queue WHERE status='pending_retry' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def incrementar_retry(fallo_id):
    conn = get_connection()
    conn.execute(
        "UPDATE failed_queue SET retry_count = retry_count + 1 WHERE id=?", (fallo_id,)
    )
    conn.commit()
    conn.close()


def marcar_fallo_estado(fallo_id, status):
    conn = get_connection()
    conn.execute("UPDATE failed_queue SET status=? WHERE id=?", (status, fallo_id))
    conn.commit()
    conn.close()

"""Monitor en vivo de la base de datos — para mostrar en el video que el
panel sí está corriendo código real, no una maqueta de HTML.

Cómo usarlo para la grabación:
1. Deja el panel corriendo en el navegador (streamlit run streamlit_app.py).
2. En OTRA terminal de VS Code (icono "+" junto a la terminal, o
   Terminal > New Terminal), activa el entorno y corre este script:

       .venv\\Scripts\\activate
       python scripts/watch_db.py

3. Acomoda la ventana del navegador y la terminal una al lado de la otra.
4. Cada vez que hagas clic en algo del panel (cargar leads, aplicar una
   disposición, forzar un fallo, etc.), vas a ver aparecer aquí, en
   tiempo real, exactamente qué escribió el código Python en la base de
   datos SQLite (data/salvaguardas.db). Eso es la prueba: si fuera HTML
   decorativo, aquí no aparecería nada.

Ctrl+C para detenerlo.
"""
import sqlite3
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "salvaguardas.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _esperar_db():
    avisado = False
    while not DB_PATH.exists():
        if not avisado:
            print(f"Esperando a que exista {DB_PATH} — abre el panel en el navegador primero.")
            avisado = True
        time.sleep(2)


def _marcar_existentes(conn, vistos, estado_fallos):
    for row in conn.execute("SELECT lead_id FROM leads"):
        vistos["leads"].add(row["lead_id"])
    for row in conn.execute("SELECT id FROM decisions_log"):
        vistos["decisions_log"].add(row["id"])
    for row in conn.execute("SELECT draft_id FROM drafts"):
        vistos["drafts"].add(row["draft_id"])
    for row in conn.execute("SELECT id FROM audit_trail"):
        vistos["audit_trail"].add(row["id"])
    for row in conn.execute("SELECT id, status FROM failed_queue"):
        estado_fallos[row["id"]] = row["status"]


def main():
    _esperar_db()
    print("=" * 72)
    print(" MONITOR EN VIVO — data/salvaguardas.db")
    print(" Deja esto corriendo y usa el panel en el navegador en paralelo.")
    print("=" * 72)

    vistos = {"leads": set(), "decisions_log": set(), "drafts": set(), "audit_trail": set()}
    estado_fallos = {}

    conn = _connect()
    _marcar_existentes(conn, vistos, estado_fallos)
    conn.close()

    print(f"Listo — ignorando {len(vistos['leads'])} leads ya existentes. Solo se muestra lo NUEVO desde ahora.\n")

    while True:
        try:
            conn = _connect()

            for row in conn.execute("SELECT * FROM leads ORDER BY timestamp"):
                if row["lead_id"] not in vistos["leads"]:
                    vistos["leads"].add(row["lead_id"])
                    hora = time.strftime("%H:%M:%S")
                    print(f"[{hora}] NUEVO LEAD    | {row['lead_id']:8} | {row['creador']:18} | \"{row['mensaje'][:55]}\"")

            for row in conn.execute("SELECT * FROM decisions_log ORDER BY id"):
                if row["id"] not in vistos["decisions_log"]:
                    vistos["decisions_log"].add(row["id"])
                    hora = time.strftime("%H:%M:%S")
                    print(f"[{hora}] DECISION      | {row['lead_id']:8} | {row['decision']:16} | {row['razon'][:55]}")

            for row in conn.execute("SELECT * FROM drafts ORDER BY draft_id"):
                if row["draft_id"] not in vistos["drafts"]:
                    vistos["drafts"].add(row["draft_id"])
                    hora = time.strftime("%H:%M:%S")
                    print(f"[{hora}] BORRADOR #{row['draft_id']:<4}| {row['lead_id']:8} | {row['canal']:8} | \"{row['contenido'][:50]}\"")

            for row in conn.execute("SELECT * FROM audit_trail ORDER BY id"):
                if row["id"] not in vistos["audit_trail"]:
                    vistos["audit_trail"].add(row["id"])
                    hora = time.strftime("%H:%M:%S")
                    print(f"[{hora}] AUDIT         | {row['lead_id']:8} | {row['actor']:10} | {row['accion']:28} | {row['estado_anterior']} -> {row['estado_nuevo']}")

            for row in conn.execute("SELECT * FROM failed_queue ORDER BY id"):
                anterior = estado_fallos.get(row["id"])
                if anterior is None:
                    estado_fallos[row["id"]] = row["status"]
                    hora = time.strftime("%H:%M:%S")
                    print(f"[{hora}] FALLO NUEVO   | {row['tipo']:18} | {row['error'][:55]}")
                elif anterior != row["status"]:
                    estado_fallos[row["id"]] = row["status"]
                    hora = time.strftime("%H:%M:%S")
                    print(f"[{hora}] FALLO CAMBIO  | {row['tipo']:18} | {anterior} -> {row['status']}")

            conn.close()
        except sqlite3.OperationalError:
            pass  # la base puede estar momentáneamente ocupada por una escritura del panel

        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor detenido.")
        sys.exit(0)

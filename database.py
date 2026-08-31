import sqlite3
from datetime import datetime

DB_PATH = "inventory.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE,
            hostname TEXT,
            os_name TEXT,
            os_version TEXT,
            manufacturer TEXT,
            model TEXT,
            serial_number TEXT,
            cpu TEXT,
            ram_total_gb REAL,
            ram_free_gb REAL,
            disks_json TEXT,
            network_json TEXT,
            product_key TEXT,
            last_seen TEXT,
            status TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def upsert_machine(data: dict):
    """Insere ou atualiza uma máquina (chave única = ip)."""
    conn = get_connection()
    data = dict(data)
    data["last_seen"] = datetime.now().isoformat()

    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    updates = ", ".join(f"{k}=excluded.{k}" for k in data.keys() if k != "ip")

    sql = f"""
        INSERT INTO machines ({columns}) VALUES ({placeholders})
        ON CONFLICT(ip) DO UPDATE SET {updates}
    """
    conn.execute(sql, list(data.values()))
    conn.commit()
    conn.close()


def get_all_machines():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM machines ORDER BY ip").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_machine(ip):
    conn = get_connection()
    row = conn.execute("SELECT * FROM machines WHERE ip=?", (ip,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_status(ip, status):
    """Atualiza apenas o status (online/offline) de uma máquina já cadastrada,
    sem mexer nas demais informações. Usado pelo monitor de ping em background."""
    conn = get_connection()
    conn.execute(
        "UPDATE machines SET status=?, last_seen=? WHERE ip=?",
        (status, datetime.now().isoformat(), ip),
    )
    conn.commit()
    conn.close()


def get_all_ips():
    conn = get_connection()
    rows = conn.execute("SELECT ip FROM machines").fetchall()
    conn.close()
    return [r["ip"] for r in rows]

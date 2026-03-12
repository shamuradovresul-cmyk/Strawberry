"""
База данных бота клубники в шоколаде.
SQLite — один файл, никакого сервера.
"""

import sqlite3
import os
from datetime import datetime

DB_FILE = os.getenv("DB_FILE", "strawberry.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # доступ по имени колонки
    conn.execute("PRAGMA journal_mode=WAL")  # безопаснее при конкурентных записях
    return conn


def init_db():
    """Создаёт таблицы при первом запуске."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id              INTEGER PRIMARY KEY,   -- Telegram ID (никогда не меняется)
            name            TEXT,                  -- имя которое ввёл сам
            username        TEXT,                  -- @username если есть
            phone           TEXT,                  -- телефон
            blacklisted     INTEGER DEFAULT 0,     -- 1 = в чёрном списке
            blacklist_reason TEXT,
            blacklisted_at  TEXT,
            first_seen      TEXT DEFAULT (datetime('now')),
            last_seen       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER NOT NULL,
            item_desc       TEXT,    -- что хочет (текст/описание скрина)
            quantity        TEXT,
            wishes          TEXT,    -- пожелания (орехи, посыпка и т.д.)
            address         TEXT,
            delivery_time   TEXT,
            payment_method  TEXT,    -- наличные / перевод
            status          TEXT DEFAULT 'new',
            -- new → accepted → confirmed → delivering → done / cancelled
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE TABLE IF NOT EXISTS admins (
            id          INTEGER PRIMARY KEY,  -- Telegram ID
            name        TEXT,
            role        TEXT DEFAULT 'admin', -- 'owner' или 'admin'
            added_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS invite_codes (
            code        TEXT PRIMARY KEY,
            created_by  INTEGER,
            used_by     INTEGER,
            used        INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """)
    print("✅ База данных инициализирована")


# ─── Клиенты ─────────────────────────────────────────────────────────────────

def upsert_client(tg_id: int, name: str, username: str | None):
    """Создаёт клиента или обновляет имя/username при каждом заходе."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO clients (id, name, username, last_seen)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                name     = excluded.name,
                username = excluded.username,
                last_seen = datetime('now')
        """, (tg_id, name, username))


def get_client(tg_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM clients WHERE id = ?", (tg_id,)
        ).fetchone()


def set_client_phone(tg_id: int, phone: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET phone = ? WHERE id = ?", (phone, tg_id)
        )


def is_blacklisted(tg_id: int) -> bool:
    client = get_client(tg_id)
    return bool(client and client["blacklisted"])


def add_to_blacklist(tg_id: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute("""
            UPDATE clients SET
                blacklisted = 1,
                blacklist_reason = ?,
                blacklisted_at = datetime('now')
            WHERE id = ?
        """, (reason, tg_id))


def remove_from_blacklist(tg_id: int):
    with get_conn() as conn:
        conn.execute("""
            UPDATE clients SET
                blacklisted = 0,
                blacklist_reason = NULL,
                blacklisted_at = NULL
            WHERE id = ?
        """, (tg_id,))


def get_client_orders_count(tg_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE client_id = ?", (tg_id,)
        ).fetchone()
        return row["cnt"] if row else 0


# ─── Заказы ──────────────────────────────────────────────────────────────────

def create_order(client_id: int, item_desc: str, quantity: str,
                 wishes: str, address: str, delivery_time: str,
                 payment_method: str) -> int:
    """Создаёт заказ, возвращает его ID."""
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO orders
                (client_id, item_desc, quantity, wishes, address, delivery_time, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, item_desc, quantity, wishes, address, delivery_time, payment_method))
        return cur.lastrowid


def get_order(order_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()


def update_order_status(order_id: int, status: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE orders SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (status, order_id))


def get_orders_by_status(status: str) -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT o.*, c.name as client_name, c.phone as client_phone,
                   c.username as client_username
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            WHERE o.status = ?
            ORDER BY o.created_at DESC
        """, (status,)).fetchall()


def get_orders_today() -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT o.*, c.name as client_name, c.phone as client_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            WHERE date(o.created_at) = date('now')
            ORDER BY o.created_at DESC
        """).fetchall()


def get_orders_stats() -> dict:
    with get_conn() as conn:
        today = conn.execute("""
            SELECT COUNT(*) as cnt FROM orders
            WHERE date(created_at) = date('now')
        """).fetchone()["cnt"]

        week = conn.execute("""
            SELECT COUNT(*) as cnt FROM orders
            WHERE created_at >= datetime('now', '-7 days')
        """).fetchone()["cnt"]

        by_status = conn.execute("""
            SELECT status, COUNT(*) as cnt FROM orders GROUP BY status
        """).fetchall()

        return {
            "today": today,
            "week": week,
            "by_status": {row["status"]: row["cnt"] for row in by_status},
        }


def search_orders(query: str) -> list:
    """Поиск по имени клиента или телефону."""
    q = f"%{query}%"
    with get_conn() as conn:
        return conn.execute("""
            SELECT o.*, c.name as client_name, c.phone as client_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            WHERE c.name LIKE ? OR c.phone LIKE ?
            ORDER BY o.created_at DESC
            LIMIT 20
        """, (q, q)).fetchall()


# ─── Админы ──────────────────────────────────────────────────────────────────

def is_admin(tg_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM admins WHERE id = ?", (tg_id,)
        ).fetchone()
        return row is not None


def is_owner(tg_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM admins WHERE id = ? AND role = 'owner'", (tg_id,)
        ).fetchone()
        return row is not None


def add_admin(tg_id: int, name: str, role: str = "admin"):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO admins (id, name, role)
            VALUES (?, ?, ?)
        """, (tg_id, name, role))


def remove_admin(tg_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE id = ? AND role != 'owner'", (tg_id,))


def get_all_admins() -> list:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM admins ORDER BY role DESC").fetchall()


# ─── Инвайт-коды ─────────────────────────────────────────────────────────────

def create_invite_code(created_by: int) -> str:
    import secrets
    code = secrets.token_hex(4).upper()  # например: A3F9B2C1
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO invite_codes (code, created_by) VALUES (?, ?)
        """, (code, created_by))
    return code


def use_invite_code(code: str, used_by: int) -> bool:
    """Возвращает True если код валидный и ещё не использован."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invite_codes WHERE code = ? AND used = 0", (code,)
        ).fetchone()
        if not row:
            return False
        conn.execute("""
            UPDATE invite_codes SET used = 1, used_by = ? WHERE code = ?
        """, (used_by, code))
        return True
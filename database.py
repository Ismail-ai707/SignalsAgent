"""
Investment Watcher — Database Layer
SQLite with Supabase-ready schema (UUID PKs, timestamps).
"""

import sqlite3
import uuid
import json
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "investment_watcher.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            llm_provider TEXT DEFAULT '',
            llm_api_key TEXT DEFAULT '',
            llm_model TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL DEFAULT 'stock',
            market TEXT NOT NULL DEFAULT 'US',
            shares REAL NOT NULL DEFAULT 0,
            avg_cost REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'EUR',
            sector TEXT DEFAULT '',
            country TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            position_id TEXT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            fees REAL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'EUR',
            executed_at TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (position_id) REFERENCES positions(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            ticker TEXT,
            action TEXT,
            confidence TEXT,
            summary TEXT NOT NULL,
            reasoning TEXT,
            sources TEXT,
            raw_response TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            total_value REAL NOT NULL,
            total_cost REAL NOT NULL,
            positions_json TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# --- User CRUD ---

def create_user(username: str, password_hash: str) -> str:
    conn = get_connection()
    uid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES (?,?,?,?,?)",
            (uid, username.lower().strip(), password_hash, now, now),
        )
        conn.commit()
        return uid
    except sqlite3.IntegrityError:
        return ""
    finally:
        conn.close()


def get_user(username: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.lower().strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_llm(user_id: str, provider: str, api_key: str, model: str):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE users SET llm_provider=?, llm_api_key=?, llm_model=?, updated_at=? WHERE id=?",
        (provider, api_key, model, now, user_id),
    )
    conn.commit()
    conn.close()


# --- Positions CRUD ---

def add_position(user_id: str, ticker: str, name: str, shares: float, avg_cost: float,
                 asset_type: str = "stock", market: str = "US", currency: str = "EUR",
                 sector: str = "", country: str = "", notes: str = "") -> str:
    conn = get_connection()
    pid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO positions
           (id, user_id, ticker, name, asset_type, market, shares, avg_cost,
            currency, sector, country, notes, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, user_id, ticker.upper().strip(), name, asset_type, market, shares,
         avg_cost, currency, sector, country, notes, now, now),
    )
    conn.commit()
    conn.close()
    return pid


def update_position(position_id: str, **kwargs):
    conn = get_connection()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [position_id]
    conn.execute(f"UPDATE positions SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_position(position_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM positions WHERE id=?", (position_id,))
    conn.commit()
    conn.close()


def get_positions(user_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id=? ORDER BY ticker", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Transactions ---

def add_transaction(user_id: str, ticker: str, action: str, shares: float,
                    price: float, fees: float = 0, currency: str = "EUR",
                    executed_at: str = "", position_id: str = "", notes: str = "") -> str:
    conn = get_connection()
    tid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    if not executed_at:
        executed_at = now
    conn.execute(
        """INSERT INTO transactions
           (id, user_id, position_id, ticker, action, shares, price, fees,
            currency, executed_at, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tid, user_id, position_id, ticker.upper().strip(), action, shares,
         price, fees, currency, executed_at, notes, now),
    )
    conn.commit()
    conn.close()
    return tid


def get_transactions(user_id: str, ticker: str = ""):
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id=? AND ticker=? ORDER BY executed_at DESC",
            (user_id, ticker.upper()),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY executed_at DESC",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Price cache ---

def cache_prices(ticker: str, prices: list[dict]):
    """prices: list of {date, open, high, low, close, volume}"""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    for p in prices:
        conn.execute(
            """INSERT OR REPLACE INTO price_cache
               (ticker, date, open, high, low, close, volume, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (ticker.upper(), p["date"], p.get("open"), p.get("high"),
             p.get("low"), p["close"], p.get("volume"), now),
        )
    conn.commit()
    conn.close()


def get_cached_prices(ticker: str, start_date: str = "", end_date: str = ""):
    conn = get_connection()
    query = "SELECT * FROM price_cache WHERE ticker=?"
    params = [ticker.upper()]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Signals ---

def save_signal(user_id: str, signal_type: str, summary: str, reasoning: str = "",
                ticker: str = "", action: str = "", confidence: str = "",
                sources: str = "", raw_response: str = "") -> str:
    conn = get_connection()
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO signals
           (id, user_id, signal_type, ticker, action, confidence, summary,
            reasoning, sources, raw_response, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, user_id, signal_type, ticker, action, confidence, summary,
         reasoning, sources, raw_response, now),
    )
    conn.commit()
    conn.close()
    return sid


def get_signals(user_id: str, limit: int = 50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM signals WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Portfolio snapshots ---

def save_snapshot(user_id: str, total_value: float, total_cost: float, positions_json: str):
    conn = get_connection()
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    # Upsert: one snapshot per day
    existing = conn.execute(
        "SELECT id FROM portfolio_snapshots WHERE user_id=? AND snapshot_date=?",
        (user_id, today),
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE portfolio_snapshots
               SET total_value=?, total_cost=?, positions_json=?, created_at=?
               WHERE id=?""",
            (total_value, total_cost, positions_json, now, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO portfolio_snapshots
               (id, user_id, total_value, total_cost, positions_json, snapshot_date, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (sid, user_id, total_value, total_cost, positions_json, today, now),
        )
    conn.commit()
    conn.close()


def get_snapshots(user_id: str, limit: int = 365):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE user_id=? ORDER BY snapshot_date DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
init_db()

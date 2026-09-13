import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "dashboard.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Alerts table - populated by the TradingView webhook (setup tracker + alert history)
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            symbol TEXT,
            timeframe TEXT,
            direction TEXT,
            status TEXT,
            reasons TEXT,
            raw_payload TEXT,
            taken INTEGER DEFAULT NULL,
            outcome_note TEXT
        )
    """)

    # Trade journal
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            session TEXT,
            timeframe TEXT,
            entry_price REAL,
            stop_price REAL,
            target_price REAL,
            exit_price REAL,
            contracts REAL,
            risk_amount REAL,
            pnl REAL,
            account_name TEXT,
            cond_htf_trend INTEGER DEFAULT 0,
            cond_liquidity_sweep INTEGER DEFAULT 0,
            cond_killzone INTEGER DEFAULT 0,
            cond_smt_divergence INTEGER DEFAULT 0,
            cond_clean_move INTEGER DEFAULT 0,
            result TEXT,
            notes TEXT,
            alert_id INTEGER,
            source TEXT DEFAULT 'manual',
            external_key TEXT,
            FOREIGN KEY (alert_id) REFERENCES alerts (id)
        )
    """)

    # Safe migration: add columns if this DB was created before source/external_key existed
    existing_cols = {row["name"] for row in c.execute("PRAGMA table_info(trades)").fetchall()}
    if "source" not in existing_cols:
        c.execute("ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'manual'")
    if "external_key" not in existing_cols:
        c.execute("ALTER TABLE trades ADD COLUMN external_key TEXT")

    # Accounts (for later multi-account phase, created now so schema is ready)
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            firm TEXT,
            account_type TEXT,
            starting_balance REAL,
            current_balance REAL,
            profit_target REAL,
            max_drawdown REAL,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_external_key
        ON trades (external_key) WHERE external_key IS NOT NULL
    """)

    # Economic calendar events (manual entry, plus optional sync from a
    # Forex Factory data source)
    c.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT NOT NULL,
            event_time TEXT,
            title TEXT NOT NULL,
            impact TEXT NOT NULL DEFAULT 'yellow',
            notes TEXT,
            created_at TEXT,
            source TEXT DEFAULT 'manual',
            external_key TEXT
        )
    """)

    existing_cal_cols = {row["name"] for row in c.execute("PRAGMA table_info(calendar_events)").fetchall()}
    if "source" not in existing_cal_cols:
        c.execute("ALTER TABLE calendar_events ADD COLUMN source TEXT DEFAULT 'manual'")
    if "external_key" not in existing_cal_cols:
        c.execute("ALTER TABLE calendar_events ADD COLUMN external_key TEXT")

    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_external_key
        ON calendar_events (external_key) WHERE external_key IS NOT NULL
    """)

    # Goals / milestones - tied optionally to an account
    c.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            account_id INTEGER,
            starting_value REAL DEFAULT 0,
            target_value REAL NOT NULL,
            current_value REAL DEFAULT 0,
            target_date TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    """)

    # Simple key-value settings store (e.g. daily/weekly risk caps)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()

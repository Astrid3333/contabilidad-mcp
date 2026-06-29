import sqlite3
import os
from contextlib import contextmanager

def _db_path():
    return os.environ.get("ACCOUNTING_DB_PATH", os.path.expanduser("~/contabilidad-mcp/contabilidad.db"))

ACCOUNT_TYPES = ("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
    taxable     INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    description TEXT NOT NULL,
    reference   TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS journal_lines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id  INTEGER NOT NULL REFERENCES accounts(id),
    debit       REAL NOT NULL DEFAULT 0,
    credit      REAL NOT NULL DEFAULT 0,
    CHECK (debit >= 0 AND credit >= 0),
    CHECK (NOT (debit > 0 AND credit > 0))
);
CREATE TABLE IF NOT EXISTS category_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT NOT NULL,
    account_id  INTEGER NOT NULL REFERENCES accounts(id)
);
CREATE INDEX IF NOT EXISTS idx_journal_lines_entry ON journal_lines(entry_id);
CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date);
"""

DEFAULT_ACCOUNTS = [
    ("1000", "Caja",                    "ASSET",     0),
    ("1010", "Banco",                   "ASSET",     0),
    ("1100", "Cuentas por Cobrar",      "ASSET",     0),
    ("2000", "Cuentas por Pagar",       "LIABILITY", 0),
    ("2100", "IVA por Pagar",           "LIABILITY", 0),
    ("3000", "Capital",                 "EQUITY",    0),
    ("3900", "Resultado del Ejercicio", "EQUITY",    0),
    ("4000", "Ventas",                  "REVENUE",   1),
    ("5000", "Costo de Ventas",         "EXPENSE",   1),
    ("5100", "Gastos Operacionales",    "EXPENSE",   1),
    ("5200", "Gastos Administrativos",  "EXPENSE",   1),
]

def init_db(seed_defaults: bool = True):
    path = _db_path()
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        if seed_defaults:
            existing = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            if existing == 0:
                conn.executemany(
                    "INSERT INTO accounts (code, name, type, taxable) VALUES (?, ?, ?, ?)",
                    DEFAULT_ACCOUNTS,
                )
        conn.commit()

@contextmanager
def get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

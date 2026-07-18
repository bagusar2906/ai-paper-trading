import sqlite3
from pathlib import Path

DB_PATH = Path("data/papertrade.db")

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            signal TEXT,
            price REAL,
            rsi REAL,
            adx REAL,
            ema REAL,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def save_signal(signal):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO signals (symbol, signal, price, rsi, adx, ema, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal["symbol"],
            signal["signal"],
            signal["price"],
            signal["rsi"],
            signal["adx"],
            signal["ema"],
            signal["time"],
        ),
    )
    conn.commit()
    conn.close()

def get_recent_signals(limit=20):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT symbol, signal, price, rsi, adx, ema, created_at FROM signals ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows
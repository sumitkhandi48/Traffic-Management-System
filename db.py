"""Database management and schema initialization for Traffic Management System."""

from pathlib import Path
import sqlite3
from typing import Union

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "traffic_system.db"

SCHEMA_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Operator',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(
    db_path: Union[str, Path, sqlite3.Connection, None] = None,
) -> sqlite3.Connection:
    """Open or create a SQLite database connection with row factory enabled."""
    if isinstance(db_path, sqlite3.Connection):
        db_path.row_factory = sqlite3.Row
        return db_path

    target_path = str(db_path) if db_path is not None else str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_database(
    db_path: Union[str, Path, None] = None,
) -> None:
    """Create essential tables if they do not exist."""
    with get_connection(db_path) as conn:
        conn.execute(SCHEMA_USERS_TABLE)
        conn.commit()

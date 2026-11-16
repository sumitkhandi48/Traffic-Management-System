"""Authentication, password hashing, and user session management."""

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3
from typing import Optional, Union

from db import get_connection, initialize_database

PBKDF2_ITERATIONS = 100_000
DEFAULT_ROLE = "Operator"
ADMIN_ROLE = "Admin"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


@dataclass
class UserSession:
    """Session representation for an authenticated user."""

    user_id: int
    username: str
    role: str
    logged_in_at: datetime = field(default_factory=datetime.now)


def hash_password(
    password: str,
    salt: Optional[str] = None,
) -> tuple[str, str]:
    """Hash a plaintext password with PBKDF2-HMAC-SHA256 and a cryptographically secure salt.

    Returns:
        tuple of (hash_hex, salt_hex)
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    if salt is None:
        salt_bytes = secrets.token_bytes(16)
        salt_hex = salt_bytes.hex()
    else:
        salt_hex = salt
        salt_bytes = bytes.fromhex(salt)

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS,
    )
    return derived_key.hex(), salt_hex


def create_user(
    username: str,
    password: str,
    role: str = DEFAULT_ROLE,
    db_path: Union[str, Path, sqlite3.Connection, None] = None,
) -> bool:
    """Create a new user with hashed credentials.

    Returns True if user creation succeeded, False if username already exists or inputs are invalid.
    """
    if not isinstance(username, str) or not username.strip():
        return False
    if not isinstance(password, str) or not password:
        return False

    clean_username = username.strip()
    clean_role = role.strip() if isinstance(role, str) and role.strip() else DEFAULT_ROLE

    initialize_database(db_path)
    password_hash, salt_hex = hash_password(password)

    query = (
        "INSERT INTO users (username, password_hash, salt, role) "
        "VALUES (?, ?, ?, ?);"
    )

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                query,
                (clean_username, password_hash, salt_hex, clean_role),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def verify_credentials(
    username: str,
    password: str,
    db_path: Union[str, Path, sqlite3.Connection, None] = None,
) -> Optional[UserSession]:
    """Verify username and password against the database.

    Returns a UserSession on success, or None on failure.
    Uses timing-attack resistant hmac.compare_digest for hash verification.
    """
    if not isinstance(username, str) or not username.strip():
        return None
    if not isinstance(password, str) or not password:
        return None

    clean_username = username.strip()
    initialize_database(db_path)

    query = (
        "SELECT id, username, password_hash, salt, role "
        "FROM users WHERE username = ?;"
    )

    with get_connection(db_path) as conn:
        cursor = conn.execute(query, (clean_username,))
        row = cursor.fetchone()

    if row is None:
        return None

    stored_hash = row["password_hash"]
    stored_salt = row["salt"]

    computed_hash, _ = hash_password(password, salt=stored_salt)

    if hmac.compare_digest(computed_hash, stored_hash):
        return UserSession(
            user_id=row["id"],
            username=row["username"],
            role=row["role"],
        )

    return None


def seed_default_admin(
    db_path: Union[str, Path, sqlite3.Connection, None] = None,
) -> bool:
    """Seed the default 'admin' account ('admin123' / 'Admin') if no users exist.

    Returns True if the default admin was created, False if users already existed.
    """
    initialize_database(db_path)

    count_query = "SELECT COUNT(*) AS total FROM users;"
    with get_connection(db_path) as conn:
        cursor = conn.execute(count_query)
        row = cursor.fetchone()
        user_count = row["total"] if row is not None else 0

    if user_count == 0:
        return create_user(
            username=DEFAULT_ADMIN_USERNAME,
            password=DEFAULT_ADMIN_PASSWORD,
            role=ADMIN_ROLE,
            db_path=db_path,
        )

    return False

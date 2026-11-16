"""Unit and security tests for authentication and database layer."""

import ast
from datetime import datetime
from pathlib import Path
import sqlite3
import pytest

from auth import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    UserSession,
    create_user,
    hash_password,
    seed_default_admin,
    verify_credentials,
)
from db import initialize_database


def test_hash_password_round_trip():
    """Hashing produces expected hex lengths and verifies matching password."""
    password = "SuperSecretPassword123!"
    pw_hash, salt = hash_password(password)

    assert isinstance(pw_hash, str) and len(pw_hash) == 64
    assert isinstance(salt, str) and len(salt) == 32

    # Verification with identical salt yields identical hash
    repeat_hash, repeat_salt = hash_password(password, salt=salt)
    assert repeat_hash == pw_hash
    assert repeat_salt == salt

    # Wrong password produces different hash
    wrong_hash, _ = hash_password("WrongPassword!", salt=salt)
    assert wrong_hash != pw_hash


def test_hash_password_rejects_invalid_inputs():
    """Empty or non-string passwords must be rejected."""
    with pytest.raises(ValueError):
        hash_password("")

    with pytest.raises(ValueError):
        hash_password(None)  # type: ignore[arg-type]


def test_create_user_and_verify_credentials(tmp_path):
    """Happy path: create_user stores credentials and verify_credentials returns UserSession."""
    db_file = tmp_path / "test_traffic.db"

    created = create_user(
        username="operator_alex",
        password="ValidPassword456",
        role="Operator",
        db_path=db_file,
    )
    assert created is True

    session = verify_credentials(
        username="operator_alex",
        password="ValidPassword456",
        db_path=db_file,
    )

    assert session is not None
    assert isinstance(session, UserSession)
    assert session.username == "operator_alex"
    assert session.role == "Operator"
    assert session.user_id >= 1
    assert isinstance(session.logged_in_at, datetime)


def test_verify_credentials_wrong_password_returns_none(tmp_path):
    """Providing an incorrect password returns None."""
    db_file = tmp_path / "test_traffic.db"
    create_user("operator_sam", "CorrectSecret", db_path=db_file)

    session = verify_credentials("operator_sam", "IncorrectSecret", db_path=db_file)
    assert session is None


def test_verify_credentials_unknown_username_returns_none(tmp_path):
    """Providing a non-existent username returns None without error."""
    db_file = tmp_path / "test_traffic.db"
    initialize_database(db_file)

    session = verify_credentials("non_existent_user", "AnyPassword", db_path=db_file)
    assert session is None


def test_duplicate_username_is_rejected(tmp_path):
    """Creating a duplicate username fails due to unique constraint."""
    db_file = tmp_path / "test_traffic.db"

    first = create_user("unique_operator", "Pass1", db_path=db_file)
    assert first is True

    second = create_user("unique_operator", "Pass2", db_path=db_file)
    assert second is False


def test_seed_default_admin_creates_only_once(tmp_path):
    """seed_default_admin creates the admin account on first run and is idempotent thereafter."""
    db_file = tmp_path / "test_traffic.db"

    first_seed = seed_default_admin(db_path=db_file)
    assert first_seed is True

    # Admin credentials work as expected
    admin_session = verify_credentials(
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_PASSWORD,
        db_path=db_file,
    )
    assert admin_session is not None
    assert admin_session.username == "admin"
    assert admin_session.role == "Admin"

    # Second seed must return False and not duplicate
    second_seed = seed_default_admin(db_path=db_file)
    assert second_seed is False


def test_assert_no_sql_string_interpolation_in_auth_and_db():
    """Code-level AST security check: ensure SQL statements in auth.py and db.py use parameter bindings."""
    root_dir = Path(__file__).resolve().parent.parent

    for filename in ("auth.py", "db.py"):
        filepath = root_dir / filename
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for calls to .execute(...)
                func = node.func
                is_execute = (
                    isinstance(func, ast.Attribute) and func.attr == "execute"
                )
                if is_execute and node.args:
                    first_arg = node.args[0]
                    # Disallow f-strings (JoinedStr)
                    assert not isinstance(first_arg, ast.JoinedStr), (
                        f"Found f-string in SQL execute in {filename}:line {node.lineno}"
                    )
                    # Disallow % formatting (BinOp with Mod)
                    if isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                        pytest.fail(f"Found % formatting in SQL execute in {filename}:line {node.lineno}")
                    # Disallow .format() calls
                    if isinstance(first_arg, ast.Call):
                        call_func = first_arg.func
                        if isinstance(call_func, ast.Attribute) and call_func.attr == "format":
                            pytest.fail(f"Found .format() in SQL execute in {filename}:line {node.lineno}")

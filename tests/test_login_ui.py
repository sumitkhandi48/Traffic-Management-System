"""UI tests for the authentication login interface."""

from unittest.mock import Mock, patch
import tkinter as tk
import pytest

from auth import UserSession
from ui.login import LoginView


@pytest.fixture
def login_view(session_tk_root):
    """Create a clean LoginView window on top of the shared root for each test."""
    if session_tk_root is None:
        pytest.skip("A graphical display is required for Tkinter login UI tests.")
    window = tk.Toplevel(session_tk_root)
    window.withdraw()
    view = LoginView(window)
    yield view
    view._on_close()


def test_empty_submit_shows_error_without_calling_verify(login_view):
    """Submitting empty fields displays an inline error without calling verify_credentials."""
    with patch("ui.login.verify_credentials") as mock_verify:
        login_view.username_var.set("")
        login_view.password_var.set("")
        login_view.handle_login()

        mock_verify.assert_not_called()
        error_text = login_view.error_label.cget("text")
        assert "Please enter both username and password." in error_text


def test_empty_password_only_shows_error_without_calling_verify(login_view):
    """Submitting only username displays an inline error without calling verify_credentials."""
    with patch("ui.login.verify_credentials") as mock_verify:
        login_view.username_var.set("admin")
        login_view.password_var.set("")
        login_view.handle_login()

        mock_verify.assert_not_called()
        error_text = login_view.error_label.cget("text")
        assert "Please enter both username and password." in error_text


def test_wrong_credentials_shows_generic_error(login_view):
    """Wrong credentials show generic error and never reveal which field was invalid."""
    with patch("ui.login.verify_credentials", return_value=None):
        login_view.username_var.set("admin")
        login_view.password_var.set("wrong_password")
        login_view.handle_login()

        error_text = login_view.error_label.cget("text")
        assert error_text == "Invalid username or password."
        assert "password" not in error_text.lower() or error_text == "Invalid username or password."
        assert "username" not in error_text.lower() or error_text == "Invalid username or password."


def test_consecutive_failures_triggers_cooldown(login_view):
    """Five consecutive failed attempts disables login button and initiates cooldown countdown."""
    with patch("ui.login.verify_credentials", return_value=None):
        login_view.username_var.set("admin")
        login_view.password_var.set("badpass")

        # 4 failed attempts: button still active
        for _ in range(4):
            login_view.handle_login()
            assert str(login_view.login_button.cget("state")) != "disabled"

        # 5th failed attempt: triggers lockout
        login_view.handle_login()
        assert str(login_view.login_button.cget("state")) == "disabled"

        error_text = login_view.error_label.cget("text")
        assert "Too many failed attempts" in error_text
        assert "30 seconds" in error_text

        # Calling handle_login during cooldown returns immediately without action
        with patch("ui.login.verify_credentials") as mock_verify:
            login_view.handle_login()
            mock_verify.assert_not_called()


def test_successful_login_invokes_handoff_with_session(login_view):
    """Successful authentication invokes the on_login_success callback with valid UserSession."""
    dummy_session = UserSession(user_id=1, username="admin", role="Admin")
    mock_handoff = Mock()
    login_view.on_login_success = mock_handoff

    with patch("ui.login.verify_credentials", return_value=dummy_session):
        login_view.username_var.set("admin")
        login_view.password_var.set("admin123")
        login_view.handle_login()

        mock_handoff.assert_called_once_with(dummy_session)
        assert login_view.error_label.cget("text") == ""
        assert login_view.failed_attempts == 0


def test_password_visibility_toggle(login_view):
    """Toggling the show password checkbox toggles entry masking."""
    assert login_view.password_entry.cget("show") == "*"

    login_view.show_password_var.set(True)
    login_view._toggle_password_visibility()
    assert login_view.password_entry.cget("show") == ""

    login_view.show_password_var.set(False)
    login_view._toggle_password_visibility()
    assert login_view.password_entry.cget("show") == "*"

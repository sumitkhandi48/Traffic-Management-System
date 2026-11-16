"""Pytest configuration and session-wide fixtures."""

import tkinter as tk
import pytest


@pytest.fixture(scope="session")
def session_tk_root():
    """Create a single shared Tk interpreter instance for the entire test session."""
    try:
        root = tk.Tk()
    except tk.TclError:
        root = None

    if root is not None:
        root.withdraw()

    yield root

    if root is not None:
        try:
            root.destroy()
        except tk.TclError:
            pass

"""Entry point for the Traffic Management System."""

import tkinter as tk

from auth import UserSession, seed_default_admin
from db import initialize_database
from ui.login import LoginView
from ui.traffic_dashboard import TrafficDashboard


def start_app() -> None:
    """Initialize database, seed default admin, and launch the authenticated application lifecycle."""
    initialize_database()
    seed_default_admin()

    def show_login() -> None:
        login_root = tk.Tk()

        def on_login_success(session: UserSession) -> None:
            login_root.destroy()
            show_dashboard(session)

        LoginView(login_root, on_login_success=on_login_success)
        login_root.mainloop()

    def show_dashboard(session: UserSession) -> None:
        dash_root = tk.Tk()

        def on_logout() -> None:
            show_login()

        TrafficDashboard(
            dash_root,
            session=session,
            on_logout=on_logout,
        )
        dash_root.mainloop()

    show_login()


if __name__ == "__main__":
    start_app()

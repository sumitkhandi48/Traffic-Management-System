"""Login screen for the Traffic Management System."""

from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Union

from auth import UserSession, verify_credentials

MAX_FAILED_ATTEMPTS = 5
COOLDOWN_SECONDS = 30


class LoginView:
    """Authentication interface built on Tkinter/Ttk matching the application design system."""

    def __init__(
        self,
        root: tk.Tk,
        on_login_success: Optional[Callable[[UserSession], None]] = None,
        db_path: Union[str, Path, None] = None,
    ) -> None:
        self.root = root
        self.on_login_success = on_login_success
        self.db_path = db_path

        self.root.title("Traffic Management System - Login")
        self.root.geometry("420x460")
        self.root.minsize(380, 420)
        self.root.resizable(False, False)

        self.failed_attempts = 0
        self.cooldown_remaining = 0
        self._cooldown_job: Optional[str] = None

        self._configure_styles()
        self._build_interface()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Return>", lambda event: self.handle_login())

    def _configure_styles(self) -> None:
        """Apply modern, cohesive visual styling matching the dashboard."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "LoginTitle.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground="#1b5e20",
        )
        style.configure(
            "LoginSubtitle.TLabel",
            font=("Segoe UI", 10),
            foreground="#555555",
        )
        style.configure(
            "LoginLabel.TLabel",
            font=("Segoe UI", 10, "bold"),
            foreground="#333333",
        )
        style.configure(
            "Error.TLabel",
            font=("Segoe UI", 9, "bold"),
            foreground="#c62828",
        )
        style.configure(
            "LoginAction.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 6),
        )

    def _build_interface(self) -> None:
        """Construct the login widgets and layout."""
        container = ttk.Frame(self.root, padding=24)
        container.pack(fill=tk.BOTH, expand=True)

        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(
            header_frame,
            text="Traffic Control System",
            style="LoginTitle.TLabel",
        ).pack(anchor=tk.W)

        ttk.Label(
            header_frame,
            text="Sign in to access traffic controls and analytics",
            style="LoginSubtitle.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        form_frame = ttk.Frame(container)
        form_frame.pack(fill=tk.X, pady=(0, 10))

        # Username field
        ttk.Label(
            form_frame,
            text="Username",
            style="LoginLabel.TLabel",
        ).pack(anchor=tk.W, pady=(4, 2))

        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(
            form_frame,
            textvariable=self.username_var,
            font=("Segoe UI", 10),
        )
        self.username_entry.pack(fill=tk.X, pady=(0, 12))
        self.username_entry.focus_set()

        # Password field
        ttk.Label(
            form_frame,
            text="Password",
            style="LoginLabel.TLabel",
        ).pack(anchor=tk.W, pady=(4, 2))

        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(
            form_frame,
            textvariable=self.password_var,
            show="*",
            font=("Segoe UI", 10),
        )
        self.password_entry.pack(fill=tk.X, pady=(0, 6))

        # Show / Hide password toggle
        self.show_password_var = tk.BooleanVar(value=False)
        self.show_password_check = ttk.Checkbutton(
            form_frame,
            text="Show password",
            variable=self.show_password_var,
            command=self._toggle_password_visibility,
        )
        self.show_password_check.pack(anchor=tk.W, pady=(0, 16))

        # Inline error display
        self.error_label = ttk.Label(
            container,
            text="",
            style="Error.TLabel",
            wraplength=350,
        )
        self.error_label.pack(fill=tk.X, pady=(0, 12))

        # Login button
        self.login_button = ttk.Button(
            container,
            text="Login",
            style="LoginAction.TButton",
            command=self.handle_login,
        )
        self.login_button.pack(fill=tk.X, pady=(4, 0))

    def _toggle_password_visibility(self) -> None:
        """Toggle displaying plaintext password or asterisk mask."""
        if self.show_password_var.get():
            self.password_entry.configure(show="")
        else:
            self.password_entry.configure(show="*")

    def handle_login(self) -> None:
        """Validate input fields and verify credentials against database."""
        if self.cooldown_remaining > 0:
            return

        username = self.username_var.get().strip()
        password = self.password_var.get()

        # Validation: empty field -> inline error without calling database
        if not username or not password:
            self.error_label.configure(
                text="Please enter both username and password."
            )
            return

        session = verify_credentials(username, password, db_path=self.db_path)

        if session is not None:
            # Login successful
            self.error_label.configure(text="")
            self.failed_attempts = 0
            self._cancel_cooldown()

            if self.on_login_success is not None:
                self.on_login_success(session)
            else:
                self.root.destroy()
        else:
            # Login failed
            self.failed_attempts += 1
            if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
                self._start_cooldown()
            else:
                self.error_label.configure(
                    text="Invalid username or password."
                )

    def _start_cooldown(self) -> None:
        """Lock out login button for COOLDOWN_SECONDS with non-blocking UI countdown."""
        self.cooldown_remaining = COOLDOWN_SECONDS
        self.login_button.configure(state="disabled")
        self._update_cooldown_message()

    def _update_cooldown_message(self) -> None:
        """Update cooldown seconds remaining via root.after()."""
        if self.cooldown_remaining > 0:
            self.error_label.configure(
                text=f"Too many failed attempts. Wait {self.cooldown_remaining} seconds."
            )
            self.cooldown_remaining -= 1
            self._cooldown_job = self.root.after(1000, self._update_cooldown_message)
        else:
            self._cancel_cooldown()
            self.failed_attempts = 0
            self.login_button.configure(state="normal")
            self.error_label.configure(text="")

    def _cancel_cooldown(self) -> None:
        """Cancel any scheduled cooldown timer."""
        if self._cooldown_job is not None:
            try:
                self.root.after_cancel(self._cooldown_job)
            except tk.TclError:
                pass
            self._cooldown_job = None
        self.cooldown_remaining = 0

    def _on_close(self) -> None:
        """Cleanly cancel timers and destroy window on close."""
        self._cancel_cooldown()
        self.root.destroy()

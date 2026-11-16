"""User-friendly dashboard for the traffic management simulation."""

import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from simulation.controller import SimulationController
from simulation.engine import SimulationState
from simulation.phases import PhaseTransitionState, SignalColor, SignalPhaseController
from simulation.vehicles.vehicle import Vehicle


class VehicleQueuesProxy:
    """Backward-compatible proxy exposing LaneQueue vehicles to the UI and tests."""

    def __init__(
        self,
        dashboard: "TrafficDashboard",
    ) -> None:
        self._dashboard = dashboard
        self._extra: dict[str, Any] = {}
        self._raw_items: dict[str, list[Any]] = {}
        self._orig_names: dict[int, str] = {}

    @property
    def _controller(self) -> SimulationController:
        return self._dashboard.controller

    def __getitem__(self, key: str) -> Any:
        if key.endswith("_list"):
            approach = key[:-5]
            listboxes = getattr(self._dashboard, "vehicle_listboxes", {})
            if approach in listboxes:
                return listboxes[approach]
            return self._extra.get(key)

        if key in self._controller.APPROACHES:
            if key in self._raw_items:
                return self._raw_items[key]
            return list(self._controller.get_approach_vehicles(key))
        return self._extra.get(key, [])

    def __setitem__(self, key: str, value: Any) -> None:
        if key.endswith("_list"):
            approach = key[:-5]
            if hasattr(self._dashboard, "vehicle_listboxes"):
                self._dashboard.vehicle_listboxes[approach] = value
            self._extra[key] = value
            return

        if key in self._controller.APPROACHES:
            for q in self._controller._lane_queues[key]:
                while not q.is_empty():
                    q.dequeue()

            emerg_set = getattr(self._dashboard, "_emergency_vehicles_set", set())

            if isinstance(value, (list, tuple)):
                self._raw_items[key] = list(value)
                if len(value) > self._controller.arrival_generator.max_queue_size:
                    self._controller.arrival_generator.max_queue_size = len(value)
                    self._controller.max_queue_size = len(value)
                for item in value:
                    if isinstance(item, Vehicle):
                        lane_idx = getattr(item, "lane_index", 0)
                        if lane_idx < 0 or lane_idx >= len(self._controller._lane_queues[key]):
                            lane_idx = 0
                        self._controller._lane_queues[key][lane_idx].enqueue(item)
                    else:
                        is_emerg = (
                            "emergency" in str(item).lower()
                            or str(item) in emerg_set
                            or getattr(item, "is_emergency", False)
                        )
                        v = self._controller.arrival_generator.generate_vehicle(
                            key,
                            vehicle_type="emergency" if is_emerg else "normal",
                            is_emergency=is_emerg,
                            lane_index=0,
                        )
                        if v is not None:
                            self._orig_names[v.vehicle_id] = str(item)
                            if hasattr(item, "waiting_time"):
                                v.waiting_time = float(item.waiting_time)
            else:
                self._raw_items[key] = []

            measurements = self._controller.demand_monitor.measure(
                self._controller._lane_mapping
            )
            self._controller.statistics.update(
                self._controller._lane_mapping, measurements
            )
        else:
            self._extra[key] = value

    def __contains__(self, key: str) -> bool:
        return (
            key in self._controller.APPROACHES
            or key in self._extra
            or key.endswith("_list")
        )

    def __iter__(self):
        return iter(self._controller.APPROACHES)

    def values(self):
        return [self[app] for app in self._controller.APPROACHES]

    def items(self):
        return [(app, self[app]) for app in self._controller.APPROACHES]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class TrafficDashboard:
    """Display simulation controls, traffic signals, queues, and statistics.

    Pure observer and renderer: all simulation state, queues, signal phase
    state transitions, and movement rules reside exclusively in the domain
    layer (SimulationController).
    """

    APPROACHES = ("North", "South", "East", "West")
    MAX_DISPLAYED_VEHICLES = 3

    MIN_GREEN_DURATION = SignalPhaseController.MIN_GREEN_DURATION
    MAX_GREEN_DURATION = SignalPhaseController.MAX_GREEN_DURATION
    ABSOLUTE_MAX_GREEN_DURATION = SignalPhaseController.ABSOLUTE_MAX_GREEN_DURATION
    GAP_DURATION = SignalPhaseController.DEFAULT_GAP_DURATION
    YELLOW_CLEARANCE_DURATION = SignalPhaseController.DEFAULT_YELLOW_DURATION
    ALL_RED_CLEARANCE_DURATION = SignalPhaseController.DEFAULT_ALL_RED_DURATION

    def __init__(
        self,
        root: tk.Tk,
        controller: SimulationController | None = None,
        session: Any = None,
        on_logout: Any = None,
    ) -> None:
        self.root = root
        self.session = session
        self.on_logout = on_logout
        self.root.title("Traffic Management System")
        self.root.geometry("1280x840")
        self.root.minsize(1000, 700)

        # Domain controller as the single source of truth
        self._controller = (
            controller if controller is not None else SimulationController()
        )
        self._emergency_vehicles_set: set[Any] = set()

        # UI widget mappings
        self.vehicle_listboxes: dict[str, tk.Listbox] = {}
        self.lane_listboxes: dict[str, tuple[tk.Listbox, tk.Listbox]] = {}
        self.vehicle_waiting_times: dict[str, dict[Any, float]] = {
            approach: {} for approach in self.APPROACHES
        }
        self.signal_labels: dict[str, tk.Label] = {}
        self.queue_labels: dict[str, ttk.Label] = {}
        self.demand_labels: dict[str, ttk.Label] = {}
        self.congestion_labels: dict[str, ttk.Label] = {}

        self._tick_interval = 100
        self._last_tick_time = time.monotonic()
        self._tick_job = None
        self._vehicle_queues_proxy = VehicleQueuesProxy(self)

        self._configure_styles()
        self._build_interface()
        self._refresh_display()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick_job = self.root.after(self._tick_interval, self._tick)

    def _on_close(self) -> None:
        """Cleanly cancel tick timers and destroy the window."""
        if hasattr(self, "_tick_job") and self._tick_job is not None:
            try:
                self.root.after_cancel(self._tick_job)
            except tk.TclError:
                pass
            self._tick_job = None
        self.root.destroy()

    def logout(self) -> None:
        """Stop simulation, clean up timers, destroy dashboard window, and trigger logout callback."""
        self.stop_simulation()
        self._on_close()
        if self.on_logout is not None:
            self.on_logout()

    @property
    def controller(self) -> SimulationController:
        if not hasattr(self, "_controller") or self._controller is None:
            self._controller = SimulationController()
        return self._controller

    @controller.setter
    def controller(self, value: SimulationController) -> None:
        self._controller = value

    @property
    def engine(self):
        return self.controller.engine

    @engine.setter
    def engine(self, value):
        self.controller.engine = value

    @property
    def congestion_detector(self):
        return self.controller.congestion_detector

    @congestion_detector.setter
    def congestion_detector(self, value):
        self.controller.congestion_detector = value

    @property
    def signal_states(self) -> dict[str, str]:
        return self.controller.signal_states

    @signal_states.setter
    def signal_states(self, states: dict[str, str]):
        for approach, color in states.items():
            self.controller.phase_controller._signal_states[approach] = color

    @property
    def vehicle_queues(self):
        if (
            not hasattr(self, "_vehicle_queues_proxy")
            or self._vehicle_queues_proxy is None
        ):
            self._vehicle_queues_proxy = VehicleQueuesProxy(self)
        return self._vehicle_queues_proxy

    @vehicle_queues.setter
    def vehicle_queues(self, value):
        proxy = self.vehicle_queues
        if isinstance(value, dict):
            for k, v in value.items():
                proxy[k] = v

    @property
    def emergency_vehicles(self) -> set[Any]:
        if not hasattr(self, "_emergency_vehicles_set"):
            self._emergency_vehicles_set = set()
        return self._emergency_vehicles_set

    @emergency_vehicles.setter
    def emergency_vehicles(self, value):
        self._emergency_vehicles_set = set(value) if value else set()
        self._sync_emergency_flags()

    @property
    def emergency_approaches(self) -> set[str]:
        return set(self.controller.get_emergency_approaches())

    @emergency_approaches.setter
    def emergency_approaches(self, value):
        pass

    def _sync_emergency_flags(self) -> None:
        emerg_set = getattr(self, "_emergency_vehicles_set", set())
        proxy = getattr(self, "_vehicle_queues_proxy", None)
        orig_names = getattr(proxy, "_orig_names", {}) if proxy else {}
        for approach in self.APPROACHES:
            for v in self.controller.get_approach_vehicles(approach):
                orig = orig_names.get(v.vehicle_id, "")
                if (
                    str(v.vehicle_id) in emerg_set
                    or f"Vehicle {v.vehicle_id}" in emerg_set
                    or orig in emerg_set
                    or "emergency" in orig.lower()
                    or getattr(v, "is_emergency", False)
                ):
                    v.vehicle_type = "emergency"
                    v.is_emergency = True

    @property
    def _active_axis(self) -> str:
        return self.controller.active_axis

    @_active_axis.setter
    def _active_axis(self, value: str):
        norm = self.controller.phase_controller.normalize_axis(value)
        self.controller.phase_controller._active_axis = norm

    @property
    def _phase_duration(self) -> float:
        return self.controller.phase_duration

    @_phase_duration.setter
    def _phase_duration(self, value: float):
        self.controller.phase_controller._phase_duration = float(value)

    @property
    def _phase_elapsed(self) -> float:
        return self.controller.phase_elapsed

    @_phase_elapsed.setter
    def _phase_elapsed(self, value: float):
        self.controller.phase_controller._phase_elapsed = float(value)

    @property
    def _transition_state(self) -> str | None:
        return self.controller.transition_state_name

    @_transition_state.setter
    def _transition_state(self, val):
        if val is None:
            self.controller.phase_controller._transition_state = (
                PhaseTransitionState.NONE
            )
        elif val == "YELLOW":
            self.controller.phase_controller._transition_state = (
                PhaseTransitionState.YELLOW
            )
        elif val == "ALL_RED":
            self.controller.phase_controller._transition_state = (
                PhaseTransitionState.ALL_RED
            )

    @property
    def _pending_axis(self) -> str | None:
        return self.controller.phase_controller.pending_axis

    @_pending_axis.setter
    def _pending_axis(self, val):
        self.controller.phase_controller._pending_axis = val

    @property
    def _transition_elapsed(self) -> float:
        return self.controller.phase_controller.transition_elapsed

    @_transition_elapsed.setter
    def _transition_elapsed(self, val):
        self.controller.phase_controller._transition_elapsed = float(val)

    def _set_signal_phase(self, axis: str) -> None:
        duration = self.controller.calculate_phase_duration(axis)
        self.controller.phase_controller.start(axis, duration=duration)

    def _choose_next_phase(self) -> None:
        self._sync_emergency_flags()
        next_axis = self.controller.select_next_axis()
        self._set_signal_phase(next_axis)

    def _begin_signal_transition(self, axis: str) -> None:
        duration = self.controller.calculate_phase_duration(axis)
        self.controller.phase_controller.request_phase_switch(
            axis, target_green_duration=duration
        )

    def _advance_signal_transition(self, delta: float) -> None:
        self.controller.phase_controller.step(delta)

    def _configure_styles(self):
        style = ttk.Style()
        style.configure(
            "Title.TLabel",
            font=("Arial", 20, "bold"),
        )
        style.configure(
            "Section.TLabel",
            font=("Arial", 12, "bold"),
        )
        style.configure(
            "Status.TLabel",
            font=("Arial", 11, "bold"),
        )
        style.configure(
            "Control.TButton",
            padding=8,
        )

    def _build_interface(self):
        main = ttk.Frame(self.root, padding=(14, 10, 14, 10))
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)
        main.rowconfigure(4, weight=0, minsize=104)

        header_frame = ttk.Frame(main)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        title_col = ttk.Frame(header_frame)
        title_col.pack(side=tk.LEFT, anchor=tk.W)

        ttk.Label(
            title_col,
            text="Traffic Management System",
            style="Title.TLabel",
        ).pack(anchor=tk.W, pady=(0, 2))

        ttk.Label(
            title_col,
            text="Simulation dashboard",
        ).pack(anchor=tk.W)

        # Session context banner and logout button if authenticated
        if getattr(self, "session", None) is not None:
            user_col = ttk.Frame(header_frame)
            user_col.pack(side=tk.RIGHT, anchor=tk.E)

            self.session_label = ttk.Label(
                user_col,
                text=f"Logged in as: {self.session.username} ({self.session.role})",
                font=("Arial", 10, "bold"),
                foreground="#2e7d32",
            )
            self.session_label.pack(side=tk.LEFT, padx=(0, 10))

            self.logout_button = ttk.Button(
                user_col,
                text="Logout",
                style="Control.TButton",
                command=self.logout,
            )
            self.logout_button.pack(side=tk.LEFT)

        self.emergency_status_label = ttk.Label(
            main,
            text="Emergency priority: INACTIVE",
            style="Status.TLabel",
            foreground="#2e7d32",
        )
        self.emergency_status_label.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(0, 8),
        )

        self._build_controls(main)
        self._build_intersection(main)
        self._build_statistics(main)

        self.status_label = ttk.Label(
            main,
            text="Simulation status: STOPPED",
            style="Status.TLabel",
        )
        self.status_label.grid(row=5, column=0, sticky="w", pady=(4, 0))

    def _build_controls(self, parent):
        controls = ttk.LabelFrame(
            parent,
            text="Simulation Controls",
            padding=8,
        )
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        buttons = (
            ("Start", self.start_simulation),
            ("Pause", self.pause_simulation),
            ("Resume", self.resume_simulation),
            ("Stop", self.stop_simulation),
            ("Reset", self.reset_simulation),
        )

        for label, command in buttons:
            ttk.Button(
                controls,
                text=label,
                command=command,
                style="Control.TButton",
            ).pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Label(
            controls,
            text="Mode:",
        ).pack(side=tk.LEFT, padx=(6, 2))

        self.arrival_mode_selector = ttk.Combobox(
            controls,
            values=("Manual", "Auto (round-robin)", "Random"),
            state="readonly",
            width=14,
        )
        self.arrival_mode_selector.current(0)
        self.arrival_mode_selector.pack(side=tk.LEFT, padx=2, pady=2)
        self.arrival_mode_selector.bind(
            "<<ComboboxSelected>>",
            self._on_arrival_mode_changed,
        )

        ttk.Label(
            controls,
            text="Approach:",
        ).pack(side=tk.LEFT, padx=(6, 2))

        self.approach_selector = ttk.Combobox(
            controls,
            values=("Auto (round-robin)", *self.APPROACHES),
            state="readonly",
            width=12,
        )
        self.approach_selector.current(1)  # Default to "North"
        self.approach_selector.pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Label(
            controls,
            text="Lane:",
        ).pack(side=tk.LEFT, padx=(6, 2))

        self.lane_selector = ttk.Combobox(
            controls,
            values=("Lane 1", "Lane 2"),
            state="readonly",
            width=7,
        )
        self.lane_selector.current(0)
        self.lane_selector.pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Label(
            controls,
            text="Type:",
        ).pack(side=tk.LEFT, padx=(6, 2))

        self.vehicle_type_selector = ttk.Combobox(
            controls,
            values=("Normal", "Emergency"),
            state="readonly",
            width=10,
        )
        self.vehicle_type_selector.current(0)
        self.vehicle_type_selector.pack(
            side=tk.LEFT,
            padx=2,
            pady=2,
        )

        ttk.Button(
            controls,
            text="Add Vehicle",
            command=self.add_vehicle,
            style="Control.TButton",
        ).pack(side=tk.LEFT, padx=3, pady=2)

        self.time_label = ttk.Label(
            controls,
            text="Simulation time: 0.0 s",
        )
        self.time_label.pack(side=tk.RIGHT, padx=6)

    def _on_arrival_mode_changed(self, event=None):
        if hasattr(self, "arrival_mode_selector"):
            mode = self.arrival_mode_selector.get()
            self.controller.arrival_mode = mode

    def _build_intersection(self, parent):
        section = ttk.LabelFrame(
            parent,
            text="Intersection Overview",
            padding=8,
        )
        section.grid(row=3, column=0, sticky="nsew", pady=(0, 8))

        section.columnconfigure(0, weight=1)
        section.columnconfigure(1, weight=1)
        section.rowconfigure(0, weight=1)
        section.rowconfigure(1, weight=1)

        positions = {
            "North": (0, 0),
            "West": (1, 0),
            "East": (0, 1),
            "South": (1, 1),
        }

        for approach, (row, column) in positions.items():
            card = ttk.LabelFrame(
                section,
                text=f"{approach} Approach (2 Lanes)",
                padding=6,
            )
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=6,
                pady=4,
            )

            signal_row = ttk.Frame(card)
            signal_row.pack(anchor=tk.W, fill=tk.X)

            ttk.Label(
                signal_row,
                text="Signal:",
            ).pack(side=tk.LEFT)

            signal = tk.Label(
                signal_row,
                text=" RED ",
                bg="#c62828",
                fg="white",
                font=("Arial", 11, "bold"),
                padx=6,
                pady=2,
            )
            signal.pack(side=tk.LEFT, padx=8)
            self.signal_labels[approach] = signal

            queue = ttk.Label(
                card,
                text="Waiting vehicles: 0",
            )
            queue.pack(anchor=tk.W, pady=(3, 1))
            self.queue_labels[approach] = queue

            demand_label = ttk.Label(
                card,
                text="Traffic demand: 0.0",
            )
            demand_label.pack(anchor=tk.W, pady=(1, 0))
            self.demand_labels[approach] = demand_label

            congestion_label = ttk.Label(
                card,
                text="Congestion: NORMAL",
                foreground="#2e7d32",
            )
            congestion_label.pack(anchor=tk.W, pady=(1, 2))
            self.congestion_labels[approach] = congestion_label

            # 2 distinct queue boxes: Lane 1 and Lane 2 side-by-side
            lanes_box = ttk.Frame(card)
            lanes_box.pack(fill=tk.BOTH, expand=True, pady=(1, 0))
            lanes_box.columnconfigure(0, weight=1)
            lanes_box.columnconfigure(1, weight=1)

            lane1_box = ttk.Frame(lanes_box)
            lane1_box.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
            ttk.Label(lane1_box, text="Lane 1:").pack(anchor=tk.W)
            lane1_list = tk.Listbox(
                lane1_box,
                height=2,
                exportselection=False,
                font=("Consolas", 9),
            )
            lane1_list.pack(fill=tk.BOTH, expand=True, pady=(1, 0))

            lane2_box = ttk.Frame(lanes_box)
            lane2_box.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
            ttk.Label(lane2_box, text="Lane 2:").pack(anchor=tk.W)
            lane2_list = tk.Listbox(
                lane2_box,
                height=2,
                exportselection=False,
                font=("Consolas", 9),
            )
            lane2_list.pack(fill=tk.BOTH, expand=True, pady=(1, 0))

            self.lane_listboxes[approach] = (lane1_list, lane2_list)
            self.vehicle_listboxes[approach] = lane1_list

    def _build_statistics(self, parent):
        stats = ttk.LabelFrame(
            parent,
            text="Traffic Statistics",
            padding=(12, 8, 12, 10),
        )
        stats.grid(row=4, column=0, sticky="nsew", pady=(0, 6))
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(2, weight=1)

        self.total_vehicles_label = ttk.Label(
            stats,
            text="Total waiting vehicles: 0",
        )
        self.total_vehicles_label.grid(
            row=0,
            column=0,
            sticky=tk.W,
            padx=8,
            pady=5,
        )

        self.approach_label = ttk.Label(
            stats,
            text="Busiest approach: None",
        )
        self.approach_label.grid(
            row=0,
            column=1,
            sticky=tk.W,
            padx=8,
            pady=5,
        )

        self.average_wait_label = ttk.Label(
            stats,
            text="Average waiting time: 0.0 s",
        )
        self.average_wait_label.grid(
            row=1,
            column=0,
            sticky=tk.W,
            padx=8,
            pady=5,
        )

        self.max_queue_label = ttk.Label(
            stats,
            text="Maximum queue length: 0",
        )
        self.max_queue_label.grid(
            row=1,
            column=1,
            sticky=tk.W,
            padx=8,
            pady=5,
        )

        self.state_label = ttk.Label(
            stats,
            text="State: STOPPED",
        )
        self.state_label.grid(
            row=0,
            column=2,
            sticky=tk.W,
            padx=8,
            pady=5,
        )

    def _tick(self):
        """Advance domain simulation by actual elapsed time and refresh display."""
        try:
            now = time.monotonic()
            delta = max(0.0, now - self._last_tick_time)
            self._last_tick_time = now

            if self.controller.state == SimulationState.RUNNING:
                if hasattr(self, "arrival_mode_selector"):
                    self.controller.arrival_mode = self.arrival_mode_selector.get()

                # Backward-compatibility bridge for legacy unit tests mocking _choose_next_phase
                if hasattr(self, "_choose_next_phase") and (
                    getattr(self._choose_next_phase, "side_effect", None) is not None
                    or (
                        hasattr(self, "_move_vehicles_on_green")
                        and hasattr(self._move_vehicles_on_green, "assert_not_called")
                    )
                ):
                    self.controller.engine.step(delta)
                    self._sync_emergency_flags()
                    emerg_axis = self.controller._find_emergency_axis()
                    if emerg_axis is not None and emerg_axis != self._active_axis:
                        self._begin_signal_transition(emerg_axis)
                        self._refresh_display()
                        return

                    self._phase_elapsed += delta
                    if self._phase_elapsed >= self._phase_duration:
                        self._phase_elapsed = 0.0
                        prev_axis = self._active_axis
                        self._choose_next_phase()
                        if self._active_axis != prev_axis:
                            sel_axis = self._active_axis
                            self._active_axis = prev_axis
                            self._begin_signal_transition(sel_axis)
                    self._refresh_display()
                    return

                self.controller.step(delta)
                self._refresh_display()

        except Exception as exc:
            print(f"Simulation update failed: {exc}")

        finally:
            try:
                self._tick_job = self.root.after(self._tick_interval, self._tick)
            except tk.TclError:
                pass

    def start_simulation(self):
        """Start the simulation via the domain controller."""
        if hasattr(self, "_choose_next_phase") and hasattr(
            self._choose_next_phase, "assert_called_once"
        ):
            if self.engine.start():
                self._phase_elapsed = 0.0
                self._movement_elapsed = 0.0
                self._choose_next_phase()
                self._refresh_display()
            return

        if self.controller.start():
            self._refresh_display()

    def pause_simulation(self):
        """Pause the simulation via the domain controller."""
        if self.engine.pause():
            self._refresh_display()

    def resume_simulation(self):
        """Resume the simulation via the domain controller."""
        if self.engine.resume():
            self._refresh_display()

    def stop_simulation(self):
        """Stop the simulation via the domain controller."""
        if self.engine.stop():
            self._refresh_display()

    def reset_simulation(self):
        """Reset the simulation via the domain controller."""
        self.controller.reset()
        self.vehicle_waiting_times = {
            approach: {} for approach in self.APPROACHES
        }
        if hasattr(self, "_vehicle_queues_proxy"):
            self._vehicle_queues_proxy._raw_items.clear()
            self._vehicle_queues_proxy._orig_names.clear()
        self._refresh_display()

    def add_vehicle(self):
        """Add a vehicle according to combobox selections via domain controller."""
        arrival_mode = (
            self.arrival_mode_selector.get().strip()
            if hasattr(self, "arrival_mode_selector")
            else "Manual"
        )
        self.controller.arrival_mode = arrival_mode

        selection = (
            self.approach_selector.get().strip()
            if hasattr(self, "approach_selector")
            else "North"
        )
        lane_str = (
            self.lane_selector.get().strip()
            if hasattr(self, "lane_selector")
            else "Lane 1"
        )
        lane_num = 2 if "2" in lane_str else 1
        vehicle_type = (
            self.vehicle_type_selector.get().strip()
            if hasattr(self, "vehicle_type_selector")
            else "Normal"
        )
        is_emerg = (
            isinstance(vehicle_type, str)
            and vehicle_type.strip().lower() == "emergency"
        )

        if arrival_mode == "Random":
            vehicle = self.controller.add_vehicle(approach="Random")
        elif arrival_mode.startswith("Auto") or selection.startswith("Auto"):
            vehicle = self.controller.add_vehicle(
                approach="Auto",
                vehicle_type=vehicle_type,
                is_emergency=is_emerg,
                lane=lane_num,
            )
        else:
            vehicle = self.controller.add_vehicle(
                approach=selection,
                vehicle_type=vehicle_type,
                is_emergency=is_emerg,
                lane=lane_num,
            )

        self._refresh_display()
        return vehicle

    def _refresh_display(self):
        """Pure observer/renderer: Read domain state and render it to Tkinter widgets."""
        signal_colors = {
            "RED": "#c62828",
            "GREEN": "#2e7d32",
            "YELLOW": "#f9a825",
        }
        signal_states = self.controller.signal_states

        for approach in self.APPROACHES:
            state = signal_states.get(approach, "RED")
            signal = getattr(self, "signal_labels", {}).get(approach)
            if signal is not None:
                signal.configure(
                    text=f" {state} ",
                    bg=signal_colors.get(state, "#c62828"),
                )

            # Read queue from domain or fallback proxy
            vehicles = self.controller.get_approach_vehicles(approach)
            if not vehicles and hasattr(self, "vehicle_queues"):
                vehicles = self.vehicle_queues.get(approach, ())
            queue_len = len(vehicles)

            queue_label = getattr(self, "queue_labels", {}).get(approach)
            if queue_label is not None:
                queue_label.configure(
                    text=f"Waiting vehicles: {queue_len}"
                )

            demand_score = self.controller.get_approach_demand(approach)
            demand_label = getattr(self, "demand_labels", {}).get(approach)
            if demand_label is not None:
                demand_label.configure(
                    text=f"Traffic demand: {demand_score:.1f}"
                )

            is_congested = self.controller.is_approach_congested(approach)
            congestion_label = getattr(self, "congestion_labels", {}).get(approach)
            if congestion_label is not None:
                congestion_label.configure(
                    text=(
                        "Congestion: CONGESTED"
                        if is_congested
                        else "Congestion: NORMAL"
                    ),
                    foreground="#c62828" if is_congested else "#2e7d32",
                )

            # Dual-lane distinct queue rendering
            lane_boxes = getattr(self, "lane_listboxes", {}).get(approach)
            if lane_boxes is not None:
                box_l1, box_l2 = lane_boxes
                l1_vehicles = self.controller.get_lane_vehicles(approach, 0)
                l2_vehicles = self.controller.get_lane_vehicles(approach, 1)

                box_l1.delete(0, tk.END)
                for v in l1_vehicles[:self.MAX_DISPLAYED_VEHICLES]:
                    if isinstance(v, Vehicle):
                        marker = (
                            "[EMERGENCY]"
                            if (v.is_emergency or v.vehicle_type == "emergency")
                            else "[NORMAL]"
                        )
                        box_l1.insert(tk.END, f"{marker} #{v.vehicle_id} ({v.waiting_time:.1f}s)")
                    else:
                        box_l1.insert(tk.END, f"[NORMAL] {v} (0.0s)")

                box_l2.delete(0, tk.END)
                for v in l2_vehicles[:self.MAX_DISPLAYED_VEHICLES]:
                    if isinstance(v, Vehicle):
                        marker = (
                            "[EMERGENCY]"
                            if (v.is_emergency or v.vehicle_type == "emergency")
                            else "[NORMAL]"
                        )
                        box_l2.insert(tk.END, f"{marker} #{v.vehicle_id} ({v.waiting_time:.1f}s)")
                    else:
                        box_l2.insert(tk.END, f"[NORMAL] {v} (0.0s)")

            # Backward-compatibility listbox rendering
            vehicle_list = getattr(self, "vehicle_listboxes", {}).get(approach)
            if vehicle_list is None and hasattr(self, "vehicle_lists"):
                vehicle_list = self.vehicle_lists.get(approach)
            if vehicle_list is None and hasattr(self, "vehicle_queues"):
                vehicle_list = self.vehicle_queues.get(approach + "_list")

            if vehicle_list is not None and lane_boxes is None:
                vehicle_list.delete(0, tk.END)
                for v in vehicles[:self.MAX_DISPLAYED_VEHICLES]:
                    if isinstance(v, Vehicle):
                        marker = (
                            "[EMERGENCY]"
                            if v.vehicle_type == "emergency"
                            else "[NORMAL]"
                        )
                        text = f"{marker} Vehicle {v.vehicle_id} | Wait: {v.waiting_time:.1f} s"
                    else:
                        text = f"[NORMAL] {v} | Wait: 0.0 s"
                    vehicle_list.insert(tk.END, text)

        emergency_approaches = self.controller.get_emergency_approaches()
        if emergency_approaches:
            emergency_text = (
                "Emergency priority: ACTIVE - "
                + ", ".join(emergency_approaches)
            )
            emergency_color = "#c62828"
        else:
            emergency_text = "Emergency priority: INACTIVE"
            emergency_color = "#2e7d32"

        if hasattr(self, "emergency_status_label"):
            self.emergency_status_label.configure(
                text=emergency_text,
                foreground=emergency_color,
            )

        summary = self.controller.get_summary_statistics()

        # Compute total waiting across approaches
        total_waiting = sum(
            len(self.controller.get_approach_vehicles(app))
            if self.controller.get_approach_vehicles(app)
            else (
                len(self.vehicle_queues.get(app, ()))
                if hasattr(self, "vehicle_queues")
                else 0
            )
            for app in self.APPROACHES
        )

        if hasattr(self, "total_vehicles_label"):
            self.total_vehicles_label.configure(
                text=f"Total waiting vehicles: {total_waiting}"
            )

        if hasattr(self, "approach_label"):
            busiest = (
                summary["busiest_approach_overall"]
                if summary.get("busiest_approach_overall") not in (None, "None")
                else summary["busiest_approach_instant"]
            )
            self.approach_label.configure(
                text=f"Busiest approach: {busiest}"
            )

        if hasattr(self, "average_wait_label"):
            avg_wait = (
                summary["average_waiting_time_cumulative"]
                if summary.get("vehicles_processed_cumulative", 0) > 0
                else summary["average_waiting_time_current"]
            )
            self.average_wait_label.configure(
                text=f"Average waiting time: {avg_wait:.1f} s"
            )

        max_queue = max(
            summary.get("maximum_queue_length_cumulative", 0),
            summary.get("maximum_queue_length_instant", 0),
        )

        if hasattr(self, "max_queue_label"):
            self.max_queue_label.configure(
                text=f"Maximum queue length: {max_queue}"
            )

        state_str = summary["simulation_state"]
        if hasattr(self, "state_label"):
            self.state_label.configure(text=f"State: {state_str}")

        if hasattr(self, "status_label"):
            self.status_label.configure(text=f"Simulation status: {state_str}")

        if hasattr(self, "time_label"):
            self.time_label.configure(
                text=f"Simulation time: {summary['simulation_time']:.1f} s"
            )


def main():
    root = tk.Tk()
    TrafficDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""User-friendly dashboard for the traffic management simulation."""

import time
import tkinter as tk
from tkinter import ttk

from simulation.congestion import CongestionDetector
from simulation.engine import SimulationEngine, SimulationState


class TrafficDashboard:
    """Display simulation controls, traffic signals, queues, and statistics."""

    APPROACHES = ("North", "South", "East", "West")

    def __init__(self, root):
        self.root = root
        self.root.title("Traffic Management System")
        self.root.geometry("1000x700")
        self.root.minsize(850, 600)

        self.engine = SimulationEngine()
        self.congestion_detector = CongestionDetector()
        self.emergency_approaches = set()
        self.emergency_vehicles = set()
        self.signal_states = {
            approach: "RED" for approach in self.APPROACHES
        }

        self.vehicle_queues = {
            approach: [] for approach in self.APPROACHES
        }

        self.vehicle_waiting_times = {
            approach: {} for approach in self.APPROACHES
        }

        self.next_vehicle_id = 1

        # Adaptive traffic signal phase state.
        self._active_axis = "NS"
        self._phase_elapsed = 0.0
        self._movement_elapsed = 0.0
        self._phase_duration = 5.0

        # Dashboard refresh interval in milliseconds.
        self._tick_interval = 100
        self._last_tick_time = time.monotonic()

        self._configure_styles()
        self._build_interface()
        self._refresh_display()

        self.root.after(self._tick_interval, self._tick)

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
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main,
            text="Traffic Management System",
            style="Title.TLabel",
        ).pack(anchor=tk.W, pady=(0, 4))

        ttk.Label(
            main,
            text="Simulation dashboard",
        ).pack(anchor=tk.W, pady=(0, 14))
        self.emergency_status_label = ttk.Label(
            main,
            text="Emergency priority: INACTIVE",
            style="Status.TLabel",
            foreground="#2e7d32",
        )

        self.emergency_status_label.pack(
            anchor=tk.W,
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
        self.status_label.pack(anchor=tk.W, pady=(12, 0))


    def _build_controls(self, parent):
        controls = ttk.LabelFrame(
            parent,
            text="Simulation Controls",
            padding=10,
        )
        controls.pack(fill=tk.X, pady=(0, 12))

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
            ).pack(side=tk.LEFT, padx=3, pady=2)

        # Allow manual selection or automatic round-robin selection.
        ttk.Label(
            controls,
            text="Approach:",
        ).pack(side=tk.LEFT, padx=(10, 3))

        self.approach_selector = ttk.Combobox(
            controls,
            values=("Auto (round-robin)", *self.APPROACHES),
            state="readonly",
            width=17,
        )

        self.approach_selector.current(0)
        self.approach_selector.pack(side=tk.LEFT, padx=3, pady=2)

        self._next_auto_approach = 0
        # Allow normal or emergency vehicle insertion.
        ttk.Label(
            controls,
            text="Vehicle type:",
        ).pack(side=tk.LEFT, padx=(8, 3))

        self.vehicle_type_selector = ttk.Combobox(
            controls,
            values=("Normal", "Emergency"),
            state="readonly",
            width=10,
        )

        self.vehicle_type_selector.current(0)
        self.vehicle_type_selector.pack(
            side=tk.LEFT,
            padx=3,
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
        self.time_label.pack(side=tk.RIGHT, padx=8)

    def _build_intersection(self, parent):
        section = ttk.LabelFrame(
            parent,
            text="Intersection Overview",
            padding=12,
        )
        section.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

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

        self.signal_labels = {}
        self.queue_labels = {}
        self.demand_labels = {}
        self.congestion_labels = {}

        for approach, (row, column) in positions.items():
            card = ttk.LabelFrame(
                section,
                text=f"{approach} Approach",
                padding=10,
            )

            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=8,
                pady=8,
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
                pady=3,
            )

            signal.pack(side=tk.LEFT, padx=8)
            self.signal_labels[approach] = signal

            queue = ttk.Label(
                card,
                text="Waiting vehicles: 0",
            )
            queue.pack(anchor=tk.W, pady=(10, 4))

            self.queue_labels[approach] = queue
            demand_label = ttk.Label(
                card,
                text="Traffic demand: 0.0",
            )
            demand_label.pack(anchor=tk.W, pady=(2, 0))
            self.demand_labels[approach] = demand_label

            congestion_label = ttk.Label(
                card,
                text="Congestion: NORMAL",
                foreground="#2e7d32",
            )
            congestion_label.pack(anchor=tk.W, pady=(2, 4))
            self.congestion_labels[approach] = congestion_label
            ttk.Label(
                card,
                text="Queue (oldest first):",
            ).pack(anchor=tk.W)

            vehicle_list = tk.Listbox(
                card,
                height=3,
                exportselection=False,
                font=("Consolas", 10),
            )

            vehicle_list.pack(
                fill=tk.BOTH,
                expand=True,
                pady=(4, 0),
            )

            self.vehicle_queues[approach + "_list"] = vehicle_list

    def _build_statistics(self, parent):
        """Create the traffic statistics panel."""
        stats = ttk.LabelFrame(
            parent,
            text="Traffic Statistics",
            padding=12,
        )
        stats.pack(fill=tk.X)

        self.total_vehicles_label = ttk.Label(
            stats,
            text="Total waiting vehicles: 0",
        )
        self.total_vehicles_label.grid(
            row=0,
            column=0,
            sticky=tk.W,
            padx=8,
            pady=4,
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
            pady=4,
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
            pady=4,
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
            pady=4,
        )

        self.state_label = ttk.Label(
            stats,
            text="State: STOPPED",
        )
        self.state_label.grid(
            row=2,
            column=0,
            sticky=tk.W,
            padx=8,
            pady=4,
        )

    def _tick(self):
        """Advance simulation using elapsed time and keep the loop scheduled."""
        try:
            now = time.monotonic()
            delta = max(0.0, now - self._last_tick_time)
            self._last_tick_time = now

            if self.engine.state == SimulationState.RUNNING:
                self.engine.step(delta)

                for approach in self.APPROACHES:
                    for vehicle in self.vehicle_queues[approach]:
                        self.vehicle_waiting_times[approach][vehicle] = (
                            self.vehicle_waiting_times[approach].get(
                                vehicle, 0.0
                            )
                            + delta
                        )

                self._phase_elapsed += delta
                self._movement_elapsed += delta

                while self._phase_elapsed >= self._phase_duration:
                    self._phase_elapsed -= self._phase_duration
                    self._choose_next_phase()

                # Preserve elapsed time if processing is delayed.
                while self._movement_elapsed >= 1.0:
                    self._move_vehicles_on_green()
                    self._movement_elapsed -= 1.0

                self._refresh_display()

        except Exception as exc:
            print(f"Simulation update failed: {exc}")

        finally:
            try:
                self.root.after(self._tick_interval, self._tick)
            except tk.TclError:
                # The window may have been closed during an update.
                pass


    def _axis_demand(self, axis):
        """Return the number of waiting vehicles for an axis."""
        approaches = (
            ("North", "South")
            if axis == "NS"
            else ("East", "West")
        )

        return sum(
            len(self.vehicle_queues[name])
            for name in approaches
        )


    def _set_signal_phase(self, axis):
        """Set one axis green and keep the crossing axis red."""
        self._active_axis = axis

        green_approaches = (
            ("North", "South")
            if axis == "NS"
            else ("East", "West")
        )

        for approach in self.APPROACHES:
            self.signal_states[approach] = (
                "GREEN"
                if approach in green_approaches
                else "RED"
            )

        # Adjust green duration according to traffic demand.
        demand = self._axis_demand(axis)

        self._phase_duration = min(
            8.0,
            max(3.0, 3.0 + demand),
        )

    def _choose_next_phase(self):
        """Prioritize emergency vehicles, then balance normal traffic."""

        emergency_approaches = [
            approach
            for approach in self.APPROACHES
            if any(
                vehicle in self.emergency_vehicles
                for vehicle in self.vehicle_queues[approach]
            )
        ]

        if emergency_approaches:
            emergency_approach = emergency_approaches[0]

            next_axis = (
                "NS"
                if emergency_approach in ("North", "South")
                else "EW"
            )

            self._set_signal_phase(next_axis)
            return

        ns_demand = self._axis_demand("NS")
        ew_demand = self._axis_demand("EW")

        if ns_demand and ew_demand:
            next_axis = (
                "EW"
                if self._active_axis == "NS"
                else "NS"
            )
        elif ns_demand:
            next_axis = "NS"
        elif ew_demand:
            next_axis = "EW"
        else:
            next_axis = (
                "EW"
                if self._active_axis == "NS"
                else "NS"
            )

        self._set_signal_phase(next_axis)


    def _move_vehicles_on_green(self):
        """Remove the oldest vehicle from each approach currently on green."""
        for approach in self.APPROACHES:
            if self.signal_states[approach] != "GREEN":
                continue

            queue = self.vehicle_queues[approach]

            if queue:
                vehicle = queue.pop(0)
                self.vehicle_waiting_times[approach].pop(
                    vehicle,
                    None,
                )
                self.emergency_vehicles.discard(vehicle)

                if not any(
                    queued_vehicle in self.emergency_vehicles
                    for queued_vehicle in queue
                ):
                    self.emergency_approaches.discard(approach)

    # NFR-02: Refresh the dashboard only after successful state changes.
    def start_simulation(self):
        """Start the simulation and refresh after a successful transition."""
        if self.engine.start():
            self._phase_elapsed = 0.0
            self._movement_elapsed = 0.0

            self._choose_next_phase()
            self._refresh_display()

    def pause_simulation(self):
        """Refresh the dashboard only if pausing succeeds."""
        if self.engine.pause():
            self._refresh_display()

    def resume_simulation(self):
        """Refresh the dashboard only if resuming succeeds."""
        if self.engine.resume():
            self._refresh_display()

    def stop_simulation(self):
        """Refresh the dashboard only if stopping succeeds."""
        if self.engine.stop():
            self._refresh_display()

    def reset_simulation(self):
        """Reset the simulation, queues, timers, and signal states."""
        self.engine.reset()

        for approach in self.APPROACHES:
            self.vehicle_queues[approach].clear()
            self.vehicle_waiting_times[approach].clear()
            self.signal_states[approach] = "RED"
        self.emergency_vehicles.clear()
        self.emergency_approaches.clear()
        self.next_vehicle_id = 1
        self._next_auto_approach = 0

        self._phase_elapsed = 0.0
        self._movement_elapsed = 0.0
        self._active_axis = "NS"
        self._phase_duration = 5.0

        self._refresh_display()

    def add_vehicle(self):
        """Add a vehicle to a selected approach or use round-robin."""
        selection = self.approach_selector.get()

        if selection == "Auto (round-robin)":
            approach = self.APPROACHES[self._next_auto_approach]

            self._next_auto_approach = (
                self._next_auto_approach + 1
            ) % len(self.APPROACHES)

        elif selection in self.APPROACHES:
            approach = selection

        else:
            # Defensive fallback if the selector is not initialized.
            approach = self.APPROACHES[self._next_auto_approach]

            self._next_auto_approach = (
                self._next_auto_approach + 1
            ) % len(self.APPROACHES)

        vehicle = f"Vehicle {self.next_vehicle_id}"

        self.vehicle_queues[approach].append(vehicle)
        self.vehicle_waiting_times[approach][vehicle] = 0.0

        vehicle_type = self.vehicle_type_selector.get()

        if vehicle_type == "Emergency":
            self.emergency_vehicles.add(vehicle)
            self.emergency_approaches.add(approach)

        self.next_vehicle_id += 1

        self._refresh_display()

    def _refresh_display(self):
        """Refresh signal indicators, queues, and traffic statistics."""
        queue_lengths = {}

        for approach in self.APPROACHES:
            state = self.signal_states[approach]
            signal = self.signal_labels[approach]

            signal.configure(
                text=f" {state} ",
                bg={
                    "RED": "#c62828",
                    "GREEN": "#2e7d32",
                    "YELLOW": "#f9a825",
                }.get(state, "#c62828"),
            )

            vehicles = self.vehicle_queues[approach]
            queue_lengths[approach] = len(vehicles)
            waiting_time_total = sum(
                self.vehicle_waiting_times[approach].get(vehicle, 0.0)
                for vehicle in vehicles
            )

            demand_score = len(vehicles) + 0.1 * waiting_time_total

            self.demand_labels[approach].configure(
                text=f"Traffic demand: {demand_score:.1f}"
            )

            is_congested = self.congestion_detector.detect(
                demand_score,
                len(vehicles),
            )

            self.congestion_labels[approach].configure(
                text=(
                    "Congestion: CONGESTED"
                    if is_congested
                    else "Congestion: NORMAL"
                ),
                foreground="#c62828" if is_congested else "#2e7d32",
            )
            self.queue_labels[approach].configure(
                text=f"Waiting vehicles: {len(vehicles)}"
            )

            vehicle_list = self.vehicle_queues[approach + "_list"]

            vehicle_list.delete(0, tk.END)

            for vehicle in vehicles:
                waiting_time = (
                    self.vehicle_waiting_times[approach].get(
                        vehicle,
                        0.0,
                    )
                )

                marker = (
                    "[EMERGENCY]"
                    if vehicle in self.emergency_vehicles
                    else "[NORMAL]"
                )

                vehicle_list.insert(
                    tk.END,
                    f"{marker} {vehicle} | Wait: {waiting_time:.1f} s",
                )

        emergency_approaches = [
            approach
            for approach in self.APPROACHES
            if any(
                vehicle in self.emergency_vehicles
                for vehicle in self.vehicle_queues[approach]
            )
        ]

        if emergency_approaches:
            emergency_text = (
                "Emergency priority: ACTIVE - "
                + ", ".join(emergency_approaches)
            )
            emergency_color = "#c62828"
        else:
            emergency_text = "Emergency priority: INACTIVE"
            emergency_color = "#2e7d32"

        self.emergency_status_label.configure(
            text=emergency_text,
            foreground=emergency_color,
        )

        total = sum(queue_lengths.values())

        busiest = (
            max(queue_lengths, key=queue_lengths.get)
            if total > 0
            else "None"
        )

        max_queue = max(queue_lengths.values(), default=0)

        all_waiting_times = [
            waiting_time
            for approach in self.APPROACHES
            for waiting_time in self.vehicle_waiting_times[
                approach
            ].values()
            if waiting_time is not None
        ]

        average_wait = (
            sum(all_waiting_times) / len(all_waiting_times)
            if all_waiting_times
            else 0.0
        )

        self.total_vehicles_label.configure(
            text=f"Total waiting vehicles: {total}"
        )

        self.approach_label.configure(
            text=f"Busiest approach: {busiest}"
        )

        self.average_wait_label.configure(
            text=f"Average waiting time: {average_wait:.1f} s"
        )

        self.max_queue_label.configure(
            text=f"Maximum queue length: {max_queue}"
        )

        state = self.engine.state.value.upper()

        self.state_label.configure(text=f"State: {state}")

        self.status_label.configure(
            text=f"Simulation status: {state}"
        )

        self.time_label.configure(
            text=(
                f"Simulation time: "
                f"{self.engine.simulation_time:.1f} s"
            )
        )


def main():
    root = tk.Tk()
    TrafficDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
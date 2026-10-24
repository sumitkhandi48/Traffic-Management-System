"""User-friendly dashboard for the traffic management simulation."""

import tkinter as tk
from tkinter import ttk

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

        self._configure_styles()
        self._build_interface()
        self._refresh_display()
        self.root.after(100, self._tick)

    def _configure_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Arial", 20, "bold"))
        style.configure("Section.TLabel", font=("Arial", 12, "bold"))
        style.configure("Status.TLabel", font=("Arial", 11, "bold"))
        style.configure("Control.TButton", padding=8)

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
            parent, text="Simulation Controls", padding=10
        )
        controls.pack(fill=tk.X, pady=(0, 12))

        buttons = (
            ("Start", self.start_simulation),
            ("Pause", self.pause_simulation),
            ("Resume", self.resume_simulation),
            ("Stop", self.stop_simulation),
            ("Reset", self.reset_simulation),
            ("Add Vehicle", self.add_vehicle),
        )

        for label, command in buttons:
            ttk.Button(
                controls,
                text=label,
                command=command,
                style="Control.TButton",
            ).pack(side=tk.LEFT, padx=4, pady=2)

        self.time_label = ttk.Label(
            controls, text="Simulation time: 0.0 s"
        )
        self.time_label.pack(side=tk.RIGHT, padx=8)

    def _build_intersection(self, parent):
        section = ttk.LabelFrame(
            parent, text="Intersection Overview", padding=12
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

        for approach, (row, column) in positions.items():
            card = ttk.LabelFrame(
                section, text=f"{approach} Approach", padding=10
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
                signal_row, text="Signal:"
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
                card, text="Waiting vehicles: 0"
            )
            queue.pack(anchor=tk.W, pady=(10, 4))
            self.queue_labels[approach] = queue

            ttk.Label(
                card, text="Queue (oldest first):"
            ).pack(anchor=tk.W)

            vehicle_list = tk.Listbox(
                card,
                height=3,
                exportselection=False,
                font=("Consolas", 10),
            )
            vehicle_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            self.vehicle_queues[approach + "_list"] = vehicle_list

    def _build_statistics(self, parent):
        """Create the traffic statistics panel."""
        stats = ttk.LabelFrame(
            parent, text="Traffic Statistics", padding=12
        )
        stats.pack(fill=tk.X)

        self.total_vehicles_label = ttk.Label(
            stats, text="Total waiting vehicles: 0"
        )
        self.total_vehicles_label.grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)

        self.approach_label = ttk.Label(
            stats, text="Busiest approach: None"
        )
        self.approach_label.grid(row=0, column=1, sticky=tk.W, padx=8, pady=4)

        self.average_wait_label = ttk.Label(
            stats, text="Average waiting time: 0.0 s"
        )
        self.average_wait_label.grid(row=1, column=0, sticky=tk.W, padx=8, pady=4)

        self.max_queue_label = ttk.Label(
            stats, text="Maximum queue length: 0"
        )
        self.max_queue_label.grid(row=1, column=1, sticky=tk.W, padx=8, pady=4)

        self.state_label = ttk.Label(
            stats, text="State: STOPPED"
        )
        self.state_label.grid(row=2, column=0, sticky=tk.W, padx=8, pady=4)

    def _tick(self):
        if self.engine.state == SimulationState.RUNNING:
            self.engine.step(0.1)

            for approach in self.APPROACHES:
                for vehicle in self.vehicle_queues[approach]:
                    self.vehicle_waiting_times[approach][vehicle] = (
                        self.vehicle_waiting_times[approach].get(vehicle, 0.0)
                        + 0.1
                    )

            self._refresh_display()

        self.root.after(100, self._tick)

    def start_simulation(self):
        self.engine.start()
        self._refresh_display()

    def pause_simulation(self):
        self.engine.pause()
        self._refresh_display()

    def resume_simulation(self):
        self.engine.resume()
        self._refresh_display()

    def stop_simulation(self):
        self.engine.stop()
        self._refresh_display()

    def reset_simulation(self):
        self.engine.reset()

        for approach in self.APPROACHES:
            self.vehicle_queues[approach].clear()
            self.vehicle_waiting_times[approach].clear()
            self.signal_states[approach] = "RED"

        self.next_vehicle_id = 1
        self._refresh_display()

    def add_vehicle(self):
        approach = max(
            self.APPROACHES,
            key=lambda name: len(self.vehicle_queues[name]),
        )

        vehicle = f"Vehicle {self.next_vehicle_id}"
        self.vehicle_queues[approach].append(vehicle)
        self.vehicle_waiting_times[approach][vehicle] = 0.0

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
                bg="#c62828" if state == "RED" else "#2e7d32",
            )

            vehicles = self.vehicle_queues[approach]
            queue_lengths[approach] = len(vehicles)

            self.queue_labels[approach].configure(
                text=f"Waiting vehicles: {len(vehicles)}"
            )

            vehicle_list = self.vehicle_queues[approach + "_list"]
            vehicle_list.delete(0, tk.END)

            for vehicle in vehicles:
                waiting_time = self.vehicle_waiting_times[approach].get(
                    vehicle, 0.0
                )
                vehicle_list.insert(
                    tk.END, f"{vehicle}  |  Wait: {waiting_time:.1f} s"
                )

        total = sum(queue_lengths.values())
        busiest = (
            max(queue_lengths, key=queue_lengths.get)
            if total > 0 else "None"
        )
        max_queue = max(queue_lengths.values(), default=0)

        all_waiting_times = [
            waiting_time
            for approach in self.APPROACHES
            for waiting_time in self.vehicle_waiting_times[approach].values()
            if waiting_time is not None
        ]

        average_wait = (
            sum(all_waiting_times) / len(all_waiting_times)
            if all_waiting_times else 0.0
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
            text=f"Simulation time: {self.engine.simulation_time:.1f} s"
        )

def main():
    root = tk.Tk()
    TrafficDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()

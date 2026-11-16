"""Unified domain controller for the traffic simulation system.

Single source of truth for:
- Simulation execution lifecycle (start, pause, resume, stop, reset)
- Traffic queues and deterministic arrival generation
- Signal phase transitions and emergency preemption
- Queue clearance and gap-out signal extensions
- Real-time and cumulative statistics tracking
"""

from typing import Any, Mapping, Sequence

from simulation.congestion import CongestionDetector
from simulation.engine import SimulationEngine, SimulationState
from simulation.phases import SignalPhaseController
from simulation.traffic.demand_monitor import DemandMeasurement, DemandMonitor
from simulation.traffic.lane_queue import LaneQueue
from simulation.traffic.statistics import TrafficStatistics
from simulation.traffic.vehicle_arrivals import VehicleArrivalGenerator
from simulation.vehicles.vehicle import Vehicle


class SimulationController:
    """Coordinating controller that orchestrates all domain models."""

    APPROACHES: tuple[str, ...] = ("North", "South", "East", "West")
    MIN_GREEN: float = SignalPhaseController.MIN_GREEN
    MAX_GREEN: float = SignalPhaseController.MAX_GREEN
    GAP_OUT_TIME: float = SignalPhaseController.GAP_OUT_TIME
    YELLOW_TIME: float = SignalPhaseController.YELLOW_TIME
    ALL_RED_TIME: float = SignalPhaseController.ALL_RED_TIME
    DEFAULT_ARRIVAL_INTERVAL: float = 2.0
    MAX_QUEUE_SIZE: int = 100

    def __init__(
        self,
        engine: SimulationEngine | None = None,
        phase_controller: SignalPhaseController | None = None,
        demand_monitor: DemandMonitor | None = None,
        congestion_detector: CongestionDetector | None = None,
        statistics: TrafficStatistics | None = None,
        movement_interval: float = 1.0,
        arrival_interval: float = 2.0,
        max_queue_size: int = 100,
    ) -> None:
        self.engine = engine if engine is not None else SimulationEngine()
        self.phase_controller = (
            phase_controller
            if phase_controller is not None
            else SignalPhaseController()
        )
        self.demand_monitor = (
            demand_monitor
            if demand_monitor is not None
            else DemandMonitor()
        )
        self.congestion_detector = (
            congestion_detector
            if congestion_detector is not None
            else CongestionDetector()
        )
        self.statistics = (
            statistics
            if statistics is not None
            else TrafficStatistics(self.congestion_detector)
        )
        self.vehicle_movement_interval = float(movement_interval)
        self._arrival_interval = float(arrival_interval)
        self._max_queue_size = int(max_queue_size)

        # Dual-lane architecture: 2 independent FIFO queues per approach
        self._lane_queues: dict[str, list[LaneQueue[Vehicle]]] = {
            approach: [LaneQueue[Vehicle](), LaneQueue[Vehicle]()]
            for approach in self.APPROACHES
        }
        self._lane_mapping: dict[str, Sequence[LaneQueue[Vehicle]]] = {
            approach: self._lane_queues[approach]
            for approach in self.APPROACHES
        }
        self.arrival_generator = VehicleArrivalGenerator(
            self._lane_mapping,
            max_queue_size=self._max_queue_size,
        )
        self._arrival_mode: str = "Manual"

        self._movement_elapsed: float = 0.0
        self._arrival_elapsed: float = 0.0
        self._active_queue_empty_elapsed: float = 0.0
        self._next_auto_approach: int = 0

    @property
    def _queues(self) -> dict[str, LaneQueue[Vehicle]]:
        """Backward-compatibility property exposing Lane 1 queues."""
        return {approach: self._lane_queues[approach][0] for approach in self.APPROACHES}

    @property
    def arrival_mode(self) -> str:
        """Current vehicle arrival mode ('Manual', 'Auto (round-robin)', 'Random')."""
        return self._arrival_mode

    @arrival_mode.setter
    def arrival_mode(self, mode: str) -> None:
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError("arrival_mode must be a non-empty string")
        self._arrival_mode = mode
        self.arrival_generator.mode = mode

    @property
    def arrival_interval(self) -> float:
        """Interval in seconds between automatic vehicle arrivals in Random/Auto modes."""
        return self._arrival_interval

    @arrival_interval.setter
    def arrival_interval(self, value: float) -> None:
        val = float(value)
        if val <= 0:
            raise ValueError("arrival_interval must be positive")
        self._arrival_interval = val

    @property
    def max_queue_size(self) -> int:
        """Maximum allowed queue length per lane."""
        return self._max_queue_size

    @max_queue_size.setter
    def max_queue_size(self, value: int) -> None:
        val = int(value)
        if val <= 0:
            raise ValueError("max_queue_size must be positive")
        self._max_queue_size = val
        if hasattr(self, "arrival_generator"):
            self.arrival_generator.max_queue_size = val

    @property
    def state(self) -> SimulationState:
        """Current lifecycle state of the simulation."""
        return self.engine.state

    @property
    def simulation_time(self) -> float:
        """Elapsed simulation time in seconds."""
        return self.engine.simulation_time

    @property
    def active_axis(self) -> str:
        """Currently active axis ('NS' or 'EW')."""
        return self.phase_controller.active_axis

    @property
    def signal_states(self) -> dict[str, str]:
        """Current signal colors for all four approaches."""
        return self.phase_controller.signal_states

    @property
    def transition_state_name(self) -> str | None:
        """Name of the clearance state ('YELLOW', 'ALL_RED') or None."""
        return self.phase_controller.transition_state_name

    @property
    def is_in_clearance(self) -> bool:
        """True if the controller is in yellow or all-red clearance."""
        return self.phase_controller.is_in_clearance

    @property
    def phase_duration(self) -> float:
        """Duration allocated for the active green phase."""
        return self.phase_controller.phase_duration

    @property
    def phase_elapsed(self) -> float:
        """Elapsed time within the active green phase."""
        return self.phase_controller.phase_elapsed

    @property
    def absolute_max_green_duration(self) -> float:
        """Absolute maximum limit for green light before forcing switch."""
        return self.phase_controller.absolute_max_green_duration

    @property
    def gap_duration(self) -> float:
        """Required empty queue duration before gap-out occurs."""
        return self.phase_controller.gap_duration

    def start(self, initial_axis: str | None = None) -> bool:
        """Start simulation execution."""
        if not self.engine.start():
            return False

        self._movement_elapsed = 0.0
        self._active_queue_empty_elapsed = 0.0

        if initial_axis is not None:
            chosen_axis = initial_axis
        else:
            emergency_axis = self._find_emergency_axis()
            if emergency_axis is not None:
                chosen_axis = emergency_axis
            else:
                measurements = self.demand_monitor.measure(self._lane_mapping)
                ns_score = (
                    measurements["North"].demand_score
                    + measurements["South"].demand_score
                )
                ew_score = (
                    measurements["East"].demand_score
                    + measurements["West"].demand_score
                )
                if ns_score > ew_score:
                    chosen_axis = "NS"
                elif ew_score > ns_score:
                    chosen_axis = "EW"
                else:
                    chosen_axis = "NS"

        duration = self.calculate_phase_duration(chosen_axis)
        self.phase_controller.start(chosen_axis, duration=duration)

        measurements = self.demand_monitor.measure(self._lane_mapping)
        self.statistics.update(self._lane_mapping, measurements)
        return True

    def pause(self) -> bool:
        """Pause a running simulation."""
        return self.engine.pause()

    def resume(self) -> bool:
        """Resume a paused simulation."""
        return self.engine.resume()

    def stop(self) -> bool:
        """Stop a running or paused simulation."""
        return self.engine.stop()

    def reset(self) -> None:
        """Reset the simulation, queues, signals, and statistics."""
        self.engine.reset()
        for queues in self._lane_queues.values():
            for queue in queues:
                while not queue.is_empty():
                    queue.dequeue()

        self.phase_controller.reset()
        self.statistics.reset()
        self._movement_elapsed = 0.0
        self._arrival_elapsed = 0.0
        self._active_queue_empty_elapsed = 0.0
        self._next_auto_approach = 0

    def add_vehicle(
        self,
        approach: str | None = None,
        vehicle_type: str = "normal",
        is_emergency: bool | None = None,
        lane: int | None = None,
        lane_index: int | None = None,
    ) -> Vehicle | None:
        """Generate a vehicle and enqueue it into an approach lane.

        Returns None if the target lane (or all lanes in Random mode) is at capacity.
        """
        if (
            approach is not None
            and approach.strip().lower() == "random"
        ) or (
            approach is None
            and self._arrival_mode.strip().lower() == "random"
        ):
            vehicle = self.arrival_generator.generate_random_vehicle(
                arrival_time=self.engine.simulation_time
            )
            if vehicle is None:
                return None

            measurements = self.demand_monitor.measure(self._lane_mapping)
            self.statistics.update(self._lane_mapping, measurements)

            if vehicle.is_emergency and self.engine.state == SimulationState.RUNNING:
                for app in self.APPROACHES:
                    for q in self._lane_queues[app]:
                        if vehicle in q:
                            emerg_axis = "NS" if app in ("North", "South") else "EW"
                            if (
                                emerg_axis != self.phase_controller.active_axis
                                and self.phase_controller.has_met_min_green
                            ):
                                duration = self.calculate_phase_duration(emerg_axis)
                                self.phase_controller.request_phase_switch(
                                    emerg_axis,
                                    target_green_duration=duration,
                                )
                            break
            return vehicle

        if approach is None or approach.startswith("Auto"):
            selected_approach = self.APPROACHES[self._next_auto_approach]
            self._next_auto_approach = (
                self._next_auto_approach + 1
            ) % len(self.APPROACHES)
        elif approach in self.APPROACHES:
            selected_approach = approach
        else:
            for valid_name in self.APPROACHES:
                if approach.strip().lower() == valid_name.lower():
                    selected_approach = valid_name
                    break
            else:
                raise ValueError(f"Unknown approach: {approach}")

        if lane is not None:
            resolved_lane_index = lane - 1 if lane in (1, 2) else lane
        elif lane_index is not None:
            resolved_lane_index = lane_index
        else:
            resolved_lane_index = 0

        # Hard cap check: if lane has reached max_queue_size, do not spawn
        if self.get_lane_queue_length(selected_approach, resolved_lane_index) >= self._max_queue_size:
            return None

        norm_type = (
            vehicle_type.strip().lower()
            if isinstance(vehicle_type, str)
            else "normal"
        )
        if is_emergency is True or norm_type == "emergency":
            norm_type = "emergency"
            emergency_flag = True
        else:
            emergency_flag = False

        vehicle = self.arrival_generator.generate_vehicle(
            approach=selected_approach,
            arrival_time=self.engine.simulation_time,
            vehicle_type=norm_type,
            is_emergency=emergency_flag,
            lane_index=resolved_lane_index,
        )
        if vehicle is None:
            return None

        # Update statistics immediately to capture new queue length
        measurements = self.demand_monitor.measure(self._lane_mapping)
        self.statistics.update(self._lane_mapping, measurements)

        if emergency_flag and self.engine.state == SimulationState.RUNNING:
            emergency_axis = (
                "NS" if selected_approach in ("North", "South") else "EW"
            )
            if (
                emergency_axis != self.phase_controller.active_axis
                and self.phase_controller.has_met_min_green
            ):
                duration = self.calculate_phase_duration(emergency_axis)
                self.phase_controller.request_phase_switch(
                    emergency_axis,
                    target_green_duration=duration,
                )

        return vehicle

    def _find_emergency_axis(self) -> str | None:
        """Return the axis of the oldest waiting emergency vehicle, if any."""
        oldest_emergency_vehicle: Vehicle | None = None
        emergency_approach: str | None = None

        for approach in self.APPROACHES:
            for queue in self._lane_queues[approach]:
                for vehicle in queue:
                    is_emerg = (
                        getattr(vehicle, "is_emergency", False)
                        or getattr(vehicle, "vehicle_type", "").lower() == "emergency"
                    )
                    if is_emerg:
                        if (
                            oldest_emergency_vehicle is None
                            or vehicle.waiting_time > oldest_emergency_vehicle.waiting_time
                        ):
                            oldest_emergency_vehicle = vehicle
                            emergency_approach = approach

        if emergency_approach is not None:
            return "NS" if emergency_approach in ("North", "South") else "EW"
        return None

    def is_emergency_active(self) -> bool:
        """True if an emergency vehicle is waiting in any approach queue."""
        return any(
            any(
                getattr(v, "is_emergency", False)
                or getattr(v, "vehicle_type", "").lower() == "emergency"
                for v in q
            )
            for queues in self._lane_queues.values()
            for q in queues
        )

    def get_emergency_approaches(self) -> list[str]:
        """Approaches that currently contain at least one emergency vehicle."""
        return [
            approach
            for approach in self.APPROACHES
            if any(
                any(
                    getattr(v, "is_emergency", False)
                    or getattr(v, "vehicle_type", "").lower() == "emergency"
                    for v in q
                )
                for q in self._lane_queues[approach]
            )
        ]

    def calculate_phase_duration(self, axis: str) -> float:
        """Compute green light duration (min 10.0s, max 60.0s) from measured demand."""
        measurements = self.demand_monitor.measure(self._lane_mapping)
        axis_approaches = self.phase_controller.AXIS_APPROACHES[axis]
        axis_demand = sum(
            measurements[app].demand_score for app in axis_approaches
        )
        return min(
            self.phase_controller.max_green_duration,
            max(
                self.phase_controller.min_green_duration,
                self.phase_controller.min_green_duration + axis_demand,
            ),
        )

    def select_next_axis(self) -> str:
        """Determine next signal axis using emergency priority and weighted demand."""
        emergency_axis = self._find_emergency_axis()
        if emergency_axis is not None:
            return emergency_axis

        measurements = self.demand_monitor.measure(self._lane_mapping)
        ns_score = (
            measurements["North"].demand_score
            + measurements["South"].demand_score
        )
        ew_score = (
            measurements["East"].demand_score
            + measurements["West"].demand_score
        )

        if ns_score > ew_score:
            return "NS"
        elif ew_score > ns_score:
            return "EW"
        else:
            return self.phase_controller.other_axis(
                self.phase_controller.active_axis
            )

    def step(self, delta_time: float) -> None:
        """Advance deterministic simulation time and process traffic movements."""
        if self.engine.state != SimulationState.RUNNING:
            return

        self.engine.step(delta_time)

        # 1. Update waiting time for all queued vehicles across both lanes
        for queues in self._lane_queues.values():
            for queue in queues:
                for vehicle in queue:
                    vehicle.waiting_time += delta_time

        # 2. Throttled automatic vehicle generation in Random / Auto modes
        norm_mode = self._arrival_mode.strip().lower()
        if "random" in norm_mode or "auto" in norm_mode or "round" in norm_mode:
            self._arrival_elapsed += delta_time
            while self._arrival_elapsed >= self._arrival_interval:
                self._arrival_elapsed -= self._arrival_interval
                if "random" in norm_mode:
                    self.add_vehicle(approach="Random")
                else:
                    self.add_vehicle(approach="Auto")

        # 3. Advance phase clearance state machine
        transition_completed, new_axis = self.phase_controller.step(delta_time)
        if transition_completed:
            self._active_queue_empty_elapsed = 0.0
            self._movement_elapsed = 0.0

        # 4. Emergency preemption check (Vehicle-Actuated Control):
        # Scan RED (non-active) axes for emergency vehicles across both lanes.
        emergency_axis = self._find_emergency_axis()
        if (
            emergency_axis is not None
            and emergency_axis != self.phase_controller.active_axis
            and self.phase_controller.has_met_min_green
        ):
            if (
                not self.phase_controller.is_in_clearance
                or self.phase_controller.pending_axis != emergency_axis
            ):
                target_duration = self.calculate_phase_duration(emergency_axis)
                self.phase_controller.request_phase_switch(
                    emergency_axis,
                    target_green_duration=target_duration,
                )

        # 5. Move vehicles on green using simultaneous dual-lane FIFO dispatch
        had_vehicles_at_start = False
        vehicle_dispatched_this_step = False
        if not self.phase_controller.is_in_clearance:
            had_vehicles_at_start = any(
                any(not q.is_empty() for q in self._lane_queues[app])
                for app in self.phase_controller.active_approaches
            )
            self._movement_elapsed += delta_time
            while self._movement_elapsed >= self.vehicle_movement_interval:
                self._movement_elapsed -= self.vehicle_movement_interval
                for approach in self.phase_controller.active_approaches:
                    for queue in self._lane_queues[approach]:
                        if not queue.is_empty():
                            vehicle = queue.dequeue()
                            self.statistics.record_processed(vehicle, approach=approach)
                            vehicle_dispatched_this_step = True
        else:
            self._movement_elapsed = 0.0

        # 6. Dynamic green extension, gap-out, and MAX_GREEN limit check
        if not self.phase_controller.is_in_clearance:
            active_has_vehicles_now = any(
                any(not q.is_empty() for q in self._lane_queues[app])
                for app in self.phase_controller.active_approaches
            )
            max_green_limit = min(
                self.phase_controller.max_green_duration,
                self.phase_controller.absolute_max_green_duration,
            )

            if active_has_vehicles_now:
                self._active_queue_empty_elapsed = 0.0
                max_queue_len = max(
                    max(q.size() for q in self._lane_queues[app])
                    for app in self.phase_controller.active_approaches
                )
                needed_duration = (
                    self.phase_controller.phase_elapsed
                    + max_queue_len * self.vehicle_movement_interval
                )
                extended_duration = min(
                    max_green_limit,
                    max(self.phase_controller.phase_duration, needed_duration),
                )
                self.phase_controller.request_phase_switch(
                    self.phase_controller.active_axis,
                    target_green_duration=extended_duration,
                )
                if self.phase_controller.phase_elapsed >= max_green_limit:
                    other = self.phase_controller.other_axis(
                        self.phase_controller.active_axis
                    )
                    target_duration = self.calculate_phase_duration(other)
                    self.phase_controller.request_phase_switch(
                        other,
                        target_green_duration=target_duration,
                    )
            elif had_vehicles_at_start or vehicle_dispatched_this_step:
                # Vehicle crossed or queue just emptied during this step: reset gap timer to 0
                self._active_queue_empty_elapsed = 0.0
                if (
                    self.phase_controller.has_met_min_green
                    and self.phase_controller.phase_elapsed
                    >= self.phase_controller.phase_duration
                    and self.phase_controller.gap_duration <= 0.0
                ):
                    next_axis = self.select_next_axis()
                    target_duration = self.calculate_phase_duration(next_axis)
                    self.phase_controller.request_phase_switch(
                        next_axis,
                        target_green_duration=target_duration,
                    )
            else:
                # All lanes of active approaches were empty for this entire step: accumulate gap time
                self._active_queue_empty_elapsed += delta_time
                gap_out_ready = (
                    self._active_queue_empty_elapsed
                    >= self.phase_controller.gap_duration
                    or self.phase_controller.phase_elapsed >= max_green_limit
                )
                if self.phase_controller.has_met_min_green and gap_out_ready:
                    next_axis = self.select_next_axis()
                    target_duration = self.calculate_phase_duration(next_axis)
                    self.phase_controller.request_phase_switch(
                        next_axis,
                        target_green_duration=target_duration,
                    )

        # 7. Refresh traffic statistics
        measurements = self.demand_monitor.measure(self._lane_mapping)
        self.statistics.update(self._lane_mapping, measurements)

    def get_approach_vehicles(
        self,
        approach: str,
        lane: int | None = None,
    ) -> tuple[Vehicle, ...]:
        """Return a tuple of vehicles currently waiting at an approach."""
        if approach not in self._lane_queues:
            raise ValueError(f"Unknown approach: {approach}")
        if lane is not None:
            lane_idx = lane - 1 if lane in (1, 2) else lane
            if lane_idx < 0 or lane_idx >= len(self._lane_queues[approach]):
                raise ValueError(f"Invalid lane: {lane}")
            return tuple(self._lane_queues[approach][lane_idx])
        vehicles: list[Vehicle] = []
        for queue in self._lane_queues[approach]:
            vehicles.extend(queue)
        return tuple(vehicles)

    def get_lane_vehicles(self, approach: str, lane_index: int) -> tuple[Vehicle, ...]:
        """Return vehicles currently waiting in a specific lane (0-indexed)."""
        if approach not in self._lane_queues:
            raise ValueError(f"Unknown approach: {approach}")
        if lane_index < 0 or lane_index >= len(self._lane_queues[approach]):
            raise ValueError(f"Invalid lane_index: {lane_index}")
        return tuple(self._lane_queues[approach][lane_index])

    def get_approach_queue_length(self, approach: str) -> int:
        """Return the total number of vehicles queued across all lanes at an approach."""
        if approach not in self._lane_queues:
            raise ValueError(f"Unknown approach: {approach}")
        return sum(q.size() for q in self._lane_queues[approach])

    def get_lane_queue_length(self, approach: str, lane_index: int) -> int:
        """Return the number of vehicles queued in a specific lane (0-indexed)."""
        if approach not in self._lane_queues:
            raise ValueError(f"Unknown approach: {approach}")
        if lane_index < 0 or lane_index >= len(self._lane_queues[approach]):
            raise ValueError(f"Invalid lane_index: {lane_index}")
        return self._lane_queues[approach][lane_index].size()

    def get_approach_demand(self, approach: str) -> float:
        """Return the measured demand score for an approach summing all lanes."""
        measurements = self.demand_monitor.measure(self._lane_mapping)
        return measurements[approach].demand_score

    def is_approach_congested(self, approach: str) -> bool:
        """Return True if an approach is currently classified as congested."""
        measurements = self.demand_monitor.measure(self._lane_mapping)
        demand = measurements[approach].demand_score
        queue_len = self.get_approach_queue_length(approach)
        return self.congestion_detector.detect(demand, queue_len)

    def get_summary_statistics(self) -> dict[str, Any]:
        """Compile a comprehensive snapshot of instant and cumulative metrics."""
        queue_lengths = {
            app: sum(q.size() for q in self._lane_queues[app])
            for app in self.APPROACHES
        }
        total_waiting = sum(queue_lengths.values())

        current_wait_sum = sum(
            v.waiting_time
            for queues in self._lane_queues.values()
            for q in queues
            for v in q
        )
        avg_current_wait = (
            (current_wait_sum / total_waiting) if total_waiting else 0.0
        )

        busiest_instant = (
            max(queue_lengths, key=queue_lengths.get)
            if total_waiting > 0
            else "None"
        )

        base_stats = self.statistics.get_statistics()

        return {
            "total_waiting_vehicles": total_waiting,
            "busiest_approach_instant": busiest_instant,
            "busiest_approach_overall": self.statistics.busiest_approach_overall,
            "average_waiting_time_current": avg_current_wait,
            "average_waiting_time_cumulative": self.statistics.average_wait_all_time,
            "maximum_waiting_time_cumulative": base_stats["maximum_waiting_time"],
            "maximum_queue_length_instant": max(queue_lengths.values(), default=0),
            "maximum_queue_length_cumulative": self.statistics.peak_queue_length_ever,
            "vehicles_processed_cumulative": self.statistics.total_processed,
            "congestion_events_cumulative": self.statistics.congestion_event_count,
            "simulation_state": self.engine.state.value.upper(),
            "simulation_time": self.engine.simulation_time,
        }

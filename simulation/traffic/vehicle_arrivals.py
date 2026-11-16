"""Generate incoming vehicles and assign them to traffic lanes."""

from itertools import count
from math import isfinite
from numbers import Real
import random
from typing import Mapping, Sequence

from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


class VehicleArrivalGenerator:
    """Generate vehicles and enqueue them in valid traffic lanes."""

    MODES: tuple[str, ...] = ("manual", "round_robin", "random")
    MAX_QUEUE_SIZE: int = 100

    def __init__(
        self,
        approaches: Mapping[str, Sequence[LaneQueue[Vehicle]]],
        starting_vehicle_id: int = 1,
        mode: str = "manual",
        emergency_probability: float = 0.1,
        seed: int | None = None,
        max_queue_size: int = 100,
    ) -> None:
        """Initialize the generator with available approaches and lanes."""
        if not approaches:
            raise ValueError("at least one approach must be configured")

        if (
            isinstance(starting_vehicle_id, bool)
            or not isinstance(starting_vehicle_id, int)
        ):
            raise TypeError("starting_vehicle_id must be an integer")

        if starting_vehicle_id < 0:
            raise ValueError("starting_vehicle_id cannot be negative")

        self._approaches = {}

        for approach, lanes in approaches.items():
            if not isinstance(approach, str) or not approach.strip():
                raise ValueError("approach names must be non-empty strings")

            if not lanes:
                raise ValueError(
                    f"approach '{approach}' must have at least one lane"
                )

            for lane in lanes:
                if not isinstance(lane, LaneQueue):
                    raise TypeError(
                        "each lane must be a LaneQueue instance"
                    )

            self._approaches[approach] = tuple(lanes)

        self._vehicle_ids = count(starting_vehicle_id)
        self._random = random.Random(seed)
        self.mode = mode
        self.emergency_probability = emergency_probability
        self.max_queue_size = max_queue_size

    @property
    def max_queue_size(self) -> int:
        """Maximum allowed queue length per lane."""
        return self._max_queue_size

    @max_queue_size.setter
    def max_queue_size(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("max_queue_size must be a positive integer")
        self._max_queue_size = value

    @property
    def mode(self) -> str:
        """Current vehicle arrival generation mode."""
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("mode must be a non-empty string")
        norm = value.strip().lower()
        if "round" in norm or "auto" in norm:
            self._mode = "round_robin"
        elif "random" in norm:
            self._mode = "random"
        else:
            self._mode = "manual"

    @property
    def emergency_probability(self) -> float:
        """Probability of generating an emergency vehicle in random mode."""
        return self._emergency_probability

    @emergency_probability.setter
    def emergency_probability(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("emergency_probability must be a number")
        val = float(value)
        if not (0.0 <= val <= 1.0):
            raise ValueError("emergency_probability must be between 0.0 and 1.0")
        self._emergency_probability = val

    def generate_random_vehicle(
        self,
        arrival_time: float = 0.0,
        emergency_probability: float | None = None,
    ) -> Vehicle | None:
        """Randomly select approach, lane, and vehicle type, then enqueue.

        Returns None if all lanes across all approaches have reached maximum capacity.
        """
        prob = (
            self._emergency_probability
            if emergency_probability is None
            else float(emergency_probability)
        )
        if not (0.0 <= prob <= 1.0):
            raise ValueError("emergency_probability must be between 0.0 and 1.0")

        # Collect available candidate lanes that have not reached maximum capacity
        candidate_lanes: list[tuple[str, int]] = []
        for app, lanes in self._approaches.items():
            for idx, lane_q in enumerate(lanes):
                if lane_q.size() < self._max_queue_size:
                    candidate_lanes.append((app, idx))

        if not candidate_lanes:
            return None

        selected_approach, selected_lane_idx = self._random.choice(candidate_lanes)
        is_emerg = self._random.random() < prob
        selected_type = "emergency" if is_emerg else "normal"

        return self.generate_vehicle(
            approach=selected_approach,
            arrival_time=arrival_time,
            vehicle_type=selected_type,
            lane_index=selected_lane_idx,
            is_emergency=is_emerg,
        )

    def generate_vehicle(
        self,
        approach: str,
        arrival_time: float = 0.0,
        vehicle_type: str = "normal",
        lane_index: int = 0,
        is_emergency: bool = False,
        lane: int | None = None,
    ) -> Vehicle | None:
        """Create a vehicle and add it to a lane in the selected approach.

        Returns None if the target lane has reached maximum capacity.
        """
        if approach not in self._approaches:
            raise ValueError(f"unknown approach: {approach}")

        if lane is not None:
            if isinstance(lane, bool) or not isinstance(lane, int):
                raise TypeError("lane must be an integer")
            if lane in (1, 2):
                lane_index = lane - 1
            else:
                lane_index = lane

        if (
            isinstance(lane_index, bool)
            or not isinstance(lane_index, int)
        ):
            raise TypeError("lane_index must be an integer")

        lanes = self._approaches[approach]

        if lane_index < 0 or lane_index >= len(lanes):
            raise ValueError("lane_index is not valid for this approach")

        # Hard cap check: if lane is at capacity, do not spawn a new vehicle
        if lanes[lane_index].size() >= self._max_queue_size:
            return None

        if isinstance(arrival_time, bool) or not isinstance(
            arrival_time, Real
        ):
            raise TypeError("arrival_time must be a number")

        if not isfinite(arrival_time):
            raise ValueError("arrival_time must be finite")

        if arrival_time < 0:
            raise ValueError("arrival_time cannot be negative")

        vehicle = Vehicle(
            vehicle_id=next(self._vehicle_ids),
            vehicle_type=vehicle_type,
            arrival_time=float(arrival_time),
            is_emergency=is_emergency,
            lane=lane_index + 1,
        )

        lanes[lane_index].enqueue(vehicle)
        return vehicle

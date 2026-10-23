"""Generate incoming vehicles and assign them to traffic lanes."""

from itertools import count
from math import isfinite
from numbers import Real
from typing import Mapping, Sequence

from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


class VehicleArrivalGenerator:
    """Generate vehicles and enqueue them in valid traffic lanes."""

    def __init__(
        self,
        approaches: Mapping[str, Sequence[LaneQueue[Vehicle]]],
        starting_vehicle_id: int = 1,
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

    def generate_vehicle(
        self,
        approach: str,
        arrival_time: float = 0.0,
        vehicle_type: str = "normal",
        lane_index: int = 0,
    ) -> Vehicle:
        """Create a vehicle and add it to a lane in the selected approach."""
        if approach not in self._approaches:
            raise ValueError(f"unknown approach: {approach}")

        if (
            isinstance(lane_index, bool)
            or not isinstance(lane_index, int)
        ):
            raise TypeError("lane_index must be an integer")

        lanes = self._approaches[approach]

        if lane_index < 0 or lane_index >= len(lanes):
            raise ValueError("lane_index is not valid for this approach")

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
        )

        lanes[lane_index].enqueue(vehicle)
        return vehicle
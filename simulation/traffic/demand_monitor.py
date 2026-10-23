
"""Measure traffic demand for individual approaches."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Iterable, Mapping

from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


@dataclass(frozen=True)
class DemandMeasurement:
    """Traffic-demand measurement for one approach."""

    approach: str
    waiting_vehicle_count: int
    total_waiting_time: float
    demand_score: float


class DemandMonitor:
    """Calculate updated traffic demand from approach lane queues."""

    def __init__(self, waiting_time_weight: float = 0.1) -> None:
        if (
            isinstance(waiting_time_weight, bool)
            or not isinstance(waiting_time_weight, Real)
        ):
            raise TypeError("waiting_time_weight must be a number")

        if not isfinite(waiting_time_weight):
            raise ValueError("waiting_time_weight must be finite")

        if waiting_time_weight < 0:
            raise ValueError("waiting_time_weight cannot be negative")

        self.waiting_time_weight = float(waiting_time_weight)

    def measure(
        self,
        approaches: Mapping[str, Iterable[LaneQueue[Vehicle]]],
    ) -> dict[str, DemandMeasurement]:
        """Measure current waiting vehicles and demand per approach."""
        measurements: dict[str, DemandMeasurement] = {}

        for approach, lane_queues in approaches.items():
            if not isinstance(approach, str) or not approach.strip():
                raise ValueError("approach names must be non-empty strings")

            vehicle_count = 0
            total_waiting_time = 0.0

            for lane_queue in lane_queues:
                if not isinstance(lane_queue, LaneQueue):
                    raise TypeError(
                        "each lane queue must be a LaneQueue instance"
                    )

                for vehicle in lane_queue:
                    if not isinstance(vehicle, Vehicle):
                        raise TypeError(
                            "lane queues must contain Vehicle instances"
                        )

                    vehicle_count += 1
                    total_waiting_time += vehicle.waiting_time

            demand_score = (
                vehicle_count
                + self.waiting_time_weight * total_waiting_time
            )

            measurements[approach] = DemandMeasurement(
                approach=approach,
                waiting_vehicle_count=vehicle_count,
                total_waiting_time=total_waiting_time,
                demand_score=demand_score,
            )

        return measurements

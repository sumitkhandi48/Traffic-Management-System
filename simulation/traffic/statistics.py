
"""Track traffic statistics as the simulation progresses."""

from math import isfinite
from numbers import Real
from typing import Iterable, Mapping

from simulation.congestion import CongestionDetector
from simulation.traffic.demand_monitor import DemandMeasurement
from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


class TrafficStatistics:
    """Collect processed-vehicle, queue, and congestion statistics."""

    def __init__(
        self,
        congestion_detector: CongestionDetector | None = None,
    ) -> None:
        self._congestion_detector = (
            congestion_detector
            if congestion_detector is not None
            else CongestionDetector()
        )
        self._vehicles_processed = 0
        self._total_waiting_time = 0.0
        self._maximum_waiting_time = 0.0
        self._queue_length = 0
        self._congestion_events = 0
        self._congested_approaches: set[str] = set()

    def record_processed(self, vehicle: Vehicle) -> None:
        """Record a vehicle that has completed processing."""
        if not isinstance(vehicle, Vehicle):
            raise TypeError("vehicle must be a Vehicle instance")

        waiting_time = vehicle.waiting_time

        if isinstance(waiting_time, bool) or not isinstance(waiting_time, Real):
            raise TypeError("waiting_time must be a number")

        if not isfinite(waiting_time) or waiting_time < 0:
            raise ValueError("waiting_time must be finite and non-negative")

        self._vehicles_processed += 1
        self._total_waiting_time += waiting_time
        self._maximum_waiting_time = max(
            self._maximum_waiting_time,
            float(waiting_time),
        )

    def update(
        self,
        approaches: Mapping[str, Iterable[LaneQueue[Vehicle]]],
        demand_measurements: Mapping[str, DemandMeasurement],
    ) -> dict[str, int | float]:
        """Refresh queue length and detect new congestion events."""
        queue_length = 0
        currently_congested: set[str] = set()

        for approach, lane_queues in approaches.items():
            if not isinstance(approach, str) or not approach.strip():
                raise ValueError("approach names must be non-empty strings")

            approach_queue_length = 0

            for lane_queue in lane_queues:
                if not isinstance(lane_queue, LaneQueue):
                    raise TypeError("each lane queue must be a LaneQueue")

                for vehicle in lane_queue:
                    if not isinstance(vehicle, Vehicle):
                        raise TypeError(
                            "lane queues must contain Vehicle instances"
                        )
                    approach_queue_length += 1

            queue_length += approach_queue_length
            measurement = demand_measurements.get(approach)

            if measurement is not None:
                if not isinstance(measurement, DemandMeasurement):
                    raise TypeError(
                        "each measurement must be a DemandMeasurement"
                    )
                demand = measurement.demand_score
            else:
                demand = float(approach_queue_length)

            if self._congestion_detector.detect(
                demand,
                approach_queue_length,
            ):
                currently_congested.add(approach)

        self._congestion_events += len(
            currently_congested - self._congested_approaches
        )
        self._congested_approaches = currently_congested
        self._queue_length = queue_length

        return self.get_statistics()

    def get_statistics(self) -> dict[str, int | float]:
        """Return the latest statistics snapshot."""
        average_waiting_time = (
            self._total_waiting_time / self._vehicles_processed
            if self._vehicles_processed
            else 0.0
        )

        return {
            "vehicles_processed": self._vehicles_processed,
            "average_waiting_time": average_waiting_time,
            "maximum_waiting_time": self._maximum_waiting_time,
            "queue_length": self._queue_length,
            "congestion_events": self._congestion_events,
        }

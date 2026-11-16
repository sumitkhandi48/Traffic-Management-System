"""Track traffic statistics as the simulation progresses."""

from math import isfinite
from numbers import Real
from typing import Any, Iterable, Mapping

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
        self._peak_queue_length_ever = 0
        self._congestion_events = 0
        self._congested_approaches: set[str] = set()
        self._approach_processed_counts: dict[str, int] = {}
        self._approach_volume_counts: dict[str, int] = {}

    @property
    def total_processed(self) -> int:
        """Total number of vehicles that completed traversal through the intersection."""
        return self._vehicles_processed

    @property
    def average_wait_all_time(self) -> float:
        """Cumulative average waiting time across all completed vehicles."""
        return (
            self._total_waiting_time / self._vehicles_processed
            if self._vehicles_processed
            else 0.0
        )

    @property
    def peak_queue_length_ever(self) -> int:
        """Maximum simultaneous queue length observed across the entire run."""
        return self._peak_queue_length_ever

    @property
    def congestion_event_count(self) -> int:
        """Total number of congestion events detected across the entire run."""
        return self._congestion_events

    @property
    def busiest_approach_overall(self) -> str:
        """The approach with the highest cumulative vehicle volume, or 'None'."""
        all_approaches = set(self._approach_processed_counts) | set(self._approach_volume_counts)
        totals = {
            app: self._approach_processed_counts.get(app, 0) + self._approach_volume_counts.get(app, 0)
            for app in all_approaches
        }
        if not totals or max(totals.values(), default=0) == 0:
            return "None"
        return max(totals, key=totals.get)

    def reset(self) -> None:
        """Reset all statistics counters to zero."""
        self._vehicles_processed = 0
        self._total_waiting_time = 0.0
        self._maximum_waiting_time = 0.0
        self._queue_length = 0
        self._peak_queue_length_ever = 0
        self._congestion_events = 0
        self._congested_approaches.clear()
        self._approach_processed_counts.clear()
        self._approach_volume_counts.clear()

    def record_processed(
        self,
        vehicle: Vehicle,
        approach: str | None = None,
    ) -> None:
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

        if approach is not None:
            if not isinstance(approach, str) or not approach.strip():
                raise ValueError("approach must be a non-empty string")
            self._approach_processed_counts[approach] = (
                self._approach_processed_counts.get(approach, 0) + 1
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
            self._approach_volume_counts[approach] = (
                self._approach_volume_counts.get(approach, 0) + approach_queue_length
            )

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
        self._peak_queue_length_ever = max(self._peak_queue_length_ever, queue_length)

        return self.get_statistics()

    def get_statistics(self, include_cumulative: bool = False) -> dict[str, Any]:
        """Return the latest statistics snapshot."""
        average_waiting_time = (
            self._total_waiting_time / self._vehicles_processed
            if self._vehicles_processed
            else 0.0
        )

        base_stats = {
            "vehicles_processed": self._vehicles_processed,
            "average_waiting_time": average_waiting_time,
            "maximum_waiting_time": self._maximum_waiting_time,
            "queue_length": self._queue_length,
            "congestion_events": self._congestion_events,
        }

        if include_cumulative:
            base_stats.update({
                "total_processed": self.total_processed,
                "average_wait_all_time": self.average_wait_all_time,
                "peak_queue_length_ever": self.peak_queue_length_ever,
                "congestion_event_count": self.congestion_event_count,
                "busiest_approach_overall": self.busiest_approach_overall,
            })

        return base_stats

    def get_cumulative_statistics(self) -> dict[str, Any]:
        """Return the statistics snapshot including cumulative metrics."""
        return self.get_statistics(include_cumulative=True)

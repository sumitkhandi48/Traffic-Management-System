
"""Traffic congestion detection using extensible congestion rules."""

from numbers import Real
from typing import Protocol


class CongestionRule(Protocol):
    """Interface for pluggable congestion detection rules."""

    def is_congested(
        self,
        traffic_demand: Real,
        queue_length: int,
        demand_threshold: Real,
        queue_length_threshold: int,
    ) -> bool:
        """Return whether the supplied traffic conditions indicate congestion."""
        ...


class AnyThresholdExceeded:
    """Detect congestion when either threshold is exceeded."""

    def is_congested(
        self,
        traffic_demand: Real,
        queue_length: int,
        demand_threshold: Real,
        queue_length_threshold: int,
    ) -> bool:
        return (
            traffic_demand > demand_threshold
            or queue_length > queue_length_threshold
        )


class BothThresholdsExceeded:
    """Detect congestion only when both thresholds are exceeded."""

    def is_congested(
        self,
        traffic_demand: Real,
        queue_length: int,
        demand_threshold: Real,
        queue_length_threshold: int,
    ) -> bool:
        return (
            traffic_demand > demand_threshold
            and queue_length > queue_length_threshold
        )


class CongestionDetector:
    """Detect congestion using configurable thresholds and rules."""

    def __init__(
        self,
        demand_threshold: Real = 10,
        queue_length_threshold: int = 10,
        rule: CongestionRule | None = None,
    ) -> None:
        self.demand_threshold = self._validate_threshold(
            demand_threshold, "demand_threshold"
        )
        self.queue_length_threshold = self._validate_threshold(
            queue_length_threshold, "queue_length_threshold"
        )
        self.rule = rule if rule is not None else AnyThresholdExceeded()

    @staticmethod
    def _validate_threshold(value: Real, name: str) -> Real:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a number")
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
        return value

    def detect(
        self,
        traffic_demand: Real,
        queue_length: int,
    ) -> bool:
        """Return whether traffic conditions indicate congestion."""
        self._validate_threshold(traffic_demand, "traffic_demand")
        self._validate_threshold(queue_length, "queue_length")

        return self.rule.is_congested(
            traffic_demand,
            queue_length,
            self.demand_threshold,
            self.queue_length_threshold,
        )

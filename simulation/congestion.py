
"""Traffic congestion detection based on demand and queue length."""

from numbers import Real


class CongestionDetector:
    """Detect congestion using configurable demand and queue thresholds."""

    def __init__(
        self,
        demand_threshold: Real = 10,
        queue_length_threshold: int = 10,
    ) -> None:
        self.demand_threshold = self._validate_threshold(
            demand_threshold, "demand_threshold"
        )
        self.queue_length_threshold = self._validate_threshold(
            queue_length_threshold, "queue_length_threshold"
        )

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
        """Return True when demand OR queue length exceeds its threshold."""
        self._validate_threshold(traffic_demand, "traffic_demand")
        self._validate_threshold(queue_length, "queue_length")

        return (
            traffic_demand > self.demand_threshold
            or queue_length > self.queue_length_threshold
        )

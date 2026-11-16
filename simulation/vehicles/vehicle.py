"""Vehicle representation for the traffic simulation."""

from dataclasses import dataclass


@dataclass(slots=True)
class Vehicle:
    """Represent a vehicle participating in the traffic simulation."""

    vehicle_id: int
    vehicle_type: str = "normal"
    arrival_time: float = 0.0
    waiting_time: float = 0.0
    is_emergency: bool = False
    lane: int = 1

    def __post_init__(self) -> None:
        """Validate the vehicle's initial state."""
        if self.vehicle_id < 0:
            raise ValueError("vehicle_id cannot be negative")

        if self.arrival_time < 0:
            raise ValueError("arrival_time cannot be negative")

        if self.waiting_time < 0:
            raise ValueError("waiting_time cannot be negative")

        if (
            not isinstance(self.vehicle_type, str)
            or not self.vehicle_type.strip()
        ):
            raise ValueError(
                "vehicle_type must be a non-empty string"
            )

        if (
            isinstance(self.lane, bool)
            or not isinstance(self.lane, int)
            or self.lane <= 0
        ):
            raise ValueError("lane must be a positive integer")

        norm_type = self.vehicle_type.strip().lower()
        if norm_type == "emergency" or self.is_emergency:
            self.vehicle_type = "emergency"
            self.is_emergency = True
        else:
            self.vehicle_type = norm_type
            self.is_emergency = False

    @property
    def lane_index(self) -> int:
        """Zero-based lane index."""
        return self.lane - 1

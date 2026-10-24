
from dataclasses import dataclass


@dataclass
class Vehicle:
    """Represent a vehicle participating in the traffic simulation."""

    vehicle_id: int
    vehicle_type: str = "normal"
    arrival_time: float = 0.0
    waiting_time: float = 0.0

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

        self.vehicle_type = self.vehicle_type.strip().lower()

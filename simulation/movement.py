
"""Vehicle movement rules based on the current traffic signal state."""

from typing import Protocol, TypeVar


VehicleType = TypeVar("VehicleType")


class LaneQueue(Protocol[VehicleType]):
    """Interface required by the movement module."""

    def is_empty(self) -> bool:
        """Return whether the lane queue is empty."""
        ...

    def dequeue(self) -> VehicleType:
        """Remove and return the oldest queued vehicle."""
        ...


def _is_green_signal(signal_state: object) -> bool:
    """Return True only when the signal state represents GREEN."""
    candidates = {
        str(signal_state).strip().upper(),
        str(getattr(signal_state, "name", "")).strip().upper(),
        str(getattr(signal_state, "value", "")).strip().upper(),
    }
    return "GREEN" in candidates


def move_vehicles(
    lane_queue: LaneQueue[VehicleType],
    signal_state: object,
    max_vehicles: int = 1,
) -> list[VehicleType]:
    """
    Remove vehicles from a lane queue when its signal is GREEN.

    RED, YELLOW, and unknown signal states leave the queue unchanged.
    Vehicles are removed in FIFO order.

    Args:
        lane_queue: An object implementing is_empty() and dequeue().
        signal_state: The current signal state, passed in by the caller.
        max_vehicles: Maximum vehicles to move during this call.

    Returns:
        The vehicles removed from the queue, in FIFO order.

    Raises:
        TypeError: If max_vehicles is not an integer.
        ValueError: If max_vehicles is negative.
    """
    if isinstance(max_vehicles, bool) or not isinstance(max_vehicles, int):
        raise TypeError("max_vehicles must be an integer")

    if max_vehicles < 0:
        raise ValueError("max_vehicles cannot be negative")

    if max_vehicles == 0 or not _is_green_signal(signal_state):
        return []

    moved_vehicles: list[VehicleType] = []

    for _ in range(max_vehicles):
        if lane_queue.is_empty():
            break

        moved_vehicles.append(lane_queue.dequeue())

    return moved_vehicles

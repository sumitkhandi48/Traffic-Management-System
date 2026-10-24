
"""Extensible vehicle movement rules for traffic signals."""

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


class SignalStrategy(Protocol):
    """Interface for deciding whether vehicles may move."""

    def allows_movement(self, signal_state: object) -> bool:
        """Return whether the current signal permits movement."""
        ...


class GreenSignalStrategy:
    """Allow movement only when the signal state is GREEN."""

    def allows_movement(self, signal_state: object) -> bool:
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
    strategy: SignalStrategy | None = None,
) -> list[VehicleType]:
    """
    Move vehicles according to a configurable signal strategy.

    Defaults to GreenSignalStrategy to preserve existing behaviour.
    """
    if isinstance(max_vehicles, bool) or not isinstance(max_vehicles, int):
        raise TypeError("max_vehicles must be an integer")

    if max_vehicles < 0:
        raise ValueError("max_vehicles cannot be negative")

    if max_vehicles == 0:
        return []

    if strategy is None:
        strategy = GreenSignalStrategy()

    if not strategy.allows_movement(signal_state):
        return []

    moved_vehicles: list[VehicleType] = []

    for _ in range(max_vehicles):
        if lane_queue.is_empty():
            break

        moved_vehicles.append(lane_queue.dequeue())

    return moved_vehicles

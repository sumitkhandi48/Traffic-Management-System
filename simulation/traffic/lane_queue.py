"""FIFO queue implementation for an individual traffic lane."""

from collections import deque
from typing import Deque, Generic, TypeVar


T = TypeVar("T")


class LaneQueue(Generic[T]):
    """Maintain vehicles in arrival order for a single lane."""

    def __init__(self) -> None:
        """Initialize an empty lane queue."""
        self._vehicles: Deque[T] = deque()

    def enqueue(self, vehicle: T) -> None:
        """Add a vehicle to the back of the queue."""
        self._vehicles.append(vehicle)

    def peek(self) -> T:
        """Return the oldest vehicle without removing it."""
        if self.is_empty():
            raise IndexError("cannot peek at an empty lane queue")

        return self._vehicles[0]

    def dequeue(self) -> T:
        """Remove and return the oldest vehicle."""
        if self.is_empty():
            raise IndexError("cannot dequeue from an empty lane queue")

        return self._vehicles.popleft()

    def size(self) -> int:
        """Return the number of vehicles waiting in the lane."""
        return len(self._vehicles)

    def is_empty(self) -> bool:
        """Return whether the lane queue contains no vehicles."""
        return not self._vehicles

from collections import deque
from enum import Enum

import pytest

from simulation.movement import move_vehicles


class SignalState(Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class FakeLaneQueue:
    """Simple queue for testing movement without other modules."""

    def __init__(self, vehicles=()):
        self._vehicles = deque(vehicles)

    def is_empty(self):
        return not self._vehicles

    def peek(self):
        return self._vehicles[0] if self._vehicles else None

    def dequeue(self):
        if self.is_empty():
            raise IndexError("Cannot dequeue an empty queue")
        return self._vehicles.popleft()

    def enqueue(self, vehicle):
        self._vehicles.append(vehicle)

    def size(self):
        return len(self._vehicles)


def test_red_signal_keeps_vehicles_queued():
    queue = FakeLaneQueue(["V1", "V2"])

    moved = move_vehicles(queue, SignalState.RED)

    assert moved == []
    assert queue.size() == 2
    assert queue.peek() == "V1"


def test_yellow_signal_keeps_vehicles_queued():
    queue = FakeLaneQueue(["V1", "V2"])

    moved = move_vehicles(queue, SignalState.YELLOW)

    assert moved == []
    assert queue.size() == 2


def test_green_signal_moves_one_vehicle_by_default():
    queue = FakeLaneQueue(["V1", "V2"])

    moved = move_vehicles(queue, SignalState.GREEN)

    assert moved == ["V1"]
    assert queue.size() == 1
    assert queue.peek() == "V2"


def test_green_signal_preserves_fifo_order():
    queue = FakeLaneQueue(["V1", "V2", "V3"])

    moved = move_vehicles(queue, SignalState.GREEN, max_vehicles=2)

    assert moved == ["V1", "V2"]
    assert queue.size() == 1
    assert queue.peek() == "V3"


def test_empty_queue_returns_empty_list():
    queue = FakeLaneQueue()

    moved = move_vehicles(queue, SignalState.GREEN)

    assert moved == []
    assert queue.is_empty()


def test_zero_movement_limit_keeps_queue_unchanged():
    queue = FakeLaneQueue(["V1"])

    moved = move_vehicles(queue, SignalState.GREEN, max_vehicles=0)

    assert moved == []
    assert queue.size() == 1


def test_negative_movement_limit_raises_error():
    queue = FakeLaneQueue(["V1"])

    with pytest.raises(ValueError):
        move_vehicles(queue, SignalState.GREEN, max_vehicles=-1)


def test_non_integer_movement_limit_raises_error():
    queue = FakeLaneQueue(["V1"])

    with pytest.raises(TypeError):
        move_vehicles(queue, SignalState.GREEN, max_vehicles=1.5)


def test_string_green_signal_allows_movement():
    queue = FakeLaneQueue(["V1"])

    moved = move_vehicles(queue, "GREEN")

    assert moved == ["V1"]
    assert queue.is_empty()

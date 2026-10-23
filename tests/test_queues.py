import pytest

from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


def test_new_queue_is_empty() -> None:
    queue = LaneQueue[Vehicle]()

    assert queue.is_empty()
    assert queue.size() == 0


def test_enqueue_adds_vehicle() -> None:
    queue = LaneQueue[Vehicle]()
    vehicle = Vehicle(vehicle_id=1)

    queue.enqueue(vehicle)

    assert not queue.is_empty()
    assert queue.size() == 1


def test_peek_returns_oldest_without_removing_it() -> None:
    queue = LaneQueue[Vehicle]()
    first = Vehicle(vehicle_id=1)
    second = Vehicle(vehicle_id=2)

    queue.enqueue(first)
    queue.enqueue(second)

    assert queue.peek() is first
    assert queue.size() == 2


def test_dequeue_maintains_fifo_order() -> None:
    queue = LaneQueue[Vehicle]()
    first = Vehicle(vehicle_id=1)
    second = Vehicle(vehicle_id=2)
    third = Vehicle(vehicle_id=3)

    queue.enqueue(first)
    queue.enqueue(second)
    queue.enqueue(third)

    assert queue.dequeue() is first
    assert queue.dequeue() is second
    assert queue.dequeue() is third
    assert queue.is_empty()


def test_separate_lane_queues_are_independent() -> None:
    lane_one = LaneQueue[Vehicle]()
    lane_two = LaneQueue[Vehicle]()
    vehicle_one = Vehicle(vehicle_id=1)
    vehicle_two = Vehicle(vehicle_id=2)

    lane_one.enqueue(vehicle_one)
    lane_two.enqueue(vehicle_two)

    assert lane_one.peek() is vehicle_one
    assert lane_two.peek() is vehicle_two
    assert lane_one.size() == 1
    assert lane_two.size() == 1

    lane_one.dequeue()

    assert lane_one.is_empty()
    assert lane_two.peek() is vehicle_two


def test_peek_on_empty_queue_raises_error() -> None:
    queue = LaneQueue[Vehicle]()

    with pytest.raises(IndexError):
        queue.peek()


def test_dequeue_on_empty_queue_raises_error() -> None:
    queue = LaneQueue[Vehicle]()

    with pytest.raises(IndexError):
        queue.dequeue()
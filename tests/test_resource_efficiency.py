"""Tests for NFR-06: Memory and processing efficiency."""

import sys
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle
from ui.traffic_dashboard import TrafficDashboard


LOAD_SIZE = 10_000


@dataclass
class UnslottedVehicle:
    """Reference vehicle representation without slots."""

    vehicle_id: int
    vehicle_type: str = "normal"
    arrival_time: float = 0.0
    waiting_time: float = 0.0


def test_vehicle_uses_slots_to_reduce_instance_overhead():
    """Vehicle instances should not allocate a per-instance dictionary."""
    vehicle = Vehicle(vehicle_id=1)
    reference = UnslottedVehicle(vehicle_id=1)

    assert not hasattr(vehicle, "__dict__")

    optimized_size = sys.getsizeof(vehicle)

    reference_size = (
        sys.getsizeof(reference)
        + sys.getsizeof(reference.__dict__)
    )

    assert optimized_size < reference_size


def test_lane_queue_handles_large_vehicle_load():
    """A lane queue must efficiently retain and iterate over 10,000 items."""
    queue = LaneQueue[int]()

    for vehicle_id in range(LOAD_SIZE):
        queue.enqueue(vehicle_id)

    assert queue.size() == LOAD_SIZE
    assert queue.peek() == 0

    assert sum(queue) == sum(range(LOAD_SIZE))

    assert queue.size() == LOAD_SIZE
    assert queue.peek() == 0


def test_lane_queue_preserves_fifo_order_under_large_load():
    """Large queue operations must preserve FIFO ordering."""
    queue = LaneQueue[int]()

    for vehicle_id in range(LOAD_SIZE):
        queue.enqueue(vehicle_id)

    for expected_id in range(LOAD_SIZE):
        assert queue.dequeue() == expected_id

    assert queue.is_empty()
    assert queue.size() == 0


def make_dashboard_for_refresh_test(vehicle_count):
    """Create a dashboard without opening a graphical window."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.APPROACHES = ("North", "South", "East", "West")

    app.MAX_DISPLAYED_VEHICLES = (
        TrafficDashboard.MAX_DISPLAYED_VEHICLES
    )

    app.vehicle_queues = {
        approach: [] for approach in app.APPROACHES
    }

    app.vehicle_waiting_times = {
        approach: {} for approach in app.APPROACHES
    }

    app.signal_states = {
        approach: "RED" for approach in app.APPROACHES
    }

    app.emergency_vehicles = set()
    app.emergency_approaches = set()

    app.signal_labels = {
        approach: Mock() for approach in app.APPROACHES
    }

    app.demand_labels = {
        approach: Mock() for approach in app.APPROACHES
    }

    app.congestion_labels = {
        approach: Mock() for approach in app.APPROACHES
    }

    app.queue_labels = {
        approach: Mock() for approach in app.APPROACHES
    }

    app.vehicle_lists = {
        approach: Mock() for approach in app.APPROACHES
    }

    for approach in app.APPROACHES:
        app.vehicle_queues[approach + "_list"] = (
            app.vehicle_lists[approach]
        )

    # Simulate a large queue at North.
    app.vehicle_queues["North"] = [
        f"Vehicle {vehicle_id}"
        for vehicle_id in range(vehicle_count)
    ]

    app.vehicle_waiting_times["North"] = {
        vehicle: 0.0
        for vehicle in app.vehicle_queues["North"]
    }

    app.congestion_detector = Mock()
    app.congestion_detector.detect.return_value = False

    app.emergency_status_label = Mock()
    app.total_vehicles_label = Mock()
    app.approach_label = Mock()
    app.average_wait_label = Mock()
    app.max_queue_label = Mock()
    app.state_label = Mock()
    app.status_label = Mock()
    app.time_label = Mock()

    app.engine = SimpleNamespace(
        state=SimpleNamespace(value="running"),
        simulation_time=1.0,
    )

    return app


def test_dashboard_limits_rendering_for_large_queues():
    """Large queues retain all vehicles but render only three entries."""
    app = make_dashboard_for_refresh_test(LOAD_SIZE)

    original_queue = list(app.vehicle_queues["North"])

    app._refresh_display()

    displayed_list = app.vehicle_lists["North"]

    assert displayed_list.delete.call_count == 1
    assert displayed_list.insert.call_count == 3

    # The underlying queue is not truncated.
    assert app.vehicle_queues["North"] == original_queue
    assert len(app.vehicle_queues["North"]) == LOAD_SIZE

    # Statistics continue to report the complete queue.
    assert app.total_vehicles_label.configure.call_args.kwargs[
        "text"
    ] == f"Total waiting vehicles: {LOAD_SIZE}"

    assert app.queue_labels["North"].configure.call_args.kwargs[
        "text"
    ] == f"Waiting vehicles: {LOAD_SIZE}"
"""Tests for NFR-06: Memory and processing efficiency."""

import sys
import time
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle
from ui.traffic_dashboard import TrafficDashboard


LOAD_SIZE = 10_000

# Performance budget thresholds in seconds (NFR-06)
MAX_QUEUE_LOAD_TIME_SEC = 0.100  # 100 ms for 10,000 enqueues + iteration
MAX_QUEUE_FIFO_TIME_SEC = 0.100  # 100 ms for 10,000 enqueues + dequeues
MAX_VEHICLE_LOAD_TIME_SEC = 0.150  # 150 ms for 10,000 Vehicle creations and dequeues
MAX_DASHBOARD_REFRESH_TIME_SEC = 0.100  # 100 ms to render bounded view under 10k vehicles


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
    """A lane queue must efficiently retain and iterate over 10,000 items under performance budget."""
    start_time = time.perf_counter()
    queue = LaneQueue[int]()

    for vehicle_id in range(LOAD_SIZE):
        queue.enqueue(vehicle_id)

    assert queue.size() == LOAD_SIZE
    assert queue.peek() == 0

    assert sum(queue) == sum(range(LOAD_SIZE))

    assert queue.size() == LOAD_SIZE
    assert queue.peek() == 0

    elapsed = time.perf_counter() - start_time
    assert elapsed < MAX_QUEUE_LOAD_TIME_SEC


def test_lane_queue_preserves_fifo_order_under_large_load():
    """Large queue operations must preserve FIFO ordering under performance budget."""
    start_time = time.perf_counter()
    queue = LaneQueue[int]()

    for vehicle_id in range(LOAD_SIZE):
        queue.enqueue(vehicle_id)

    for expected_id in range(LOAD_SIZE):
        assert queue.dequeue() == expected_id

    assert queue.is_empty()
    assert queue.size() == 0

    elapsed = time.perf_counter() - start_time
    assert elapsed < MAX_QUEUE_FIFO_TIME_SEC


def test_lane_queue_vehicle_operations_benchmark():
    """10,000 domain Vehicle instances in LaneQueue operate within strict performance budget."""
    start_time = time.perf_counter()
    queue = LaneQueue[Vehicle]()

    for i in range(LOAD_SIZE):
        queue.enqueue(Vehicle(vehicle_id=i))

    assert queue.size() == LOAD_SIZE
    first_vehicle = queue.peek()
    assert first_vehicle is not None
    assert first_vehicle.vehicle_id == 0

    for expected_id in range(LOAD_SIZE):
        v = queue.dequeue()
        assert v.vehicle_id == expected_id

    assert queue.is_empty()
    elapsed = time.perf_counter() - start_time
    assert elapsed < MAX_VEHICLE_LOAD_TIME_SEC


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

    start_time = time.perf_counter()
    app._refresh_display()
    render_elapsed = time.perf_counter() - start_time
    assert render_elapsed < MAX_DASHBOARD_REFRESH_TIME_SEC

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
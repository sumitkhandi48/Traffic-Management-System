
import pytest

from simulation.congestion import CongestionDetector
from simulation.traffic.demand_monitor import DemandMonitor
from simulation.traffic.lane_queue import LaneQueue
from simulation.traffic.statistics import TrafficStatistics
from simulation.vehicles.vehicle import Vehicle


def test_statistics_start_at_zero():
    stats = TrafficStatistics()

    assert stats.get_statistics() == {
        "vehicles_processed": 0,
        "average_waiting_time": 0.0,
        "maximum_waiting_time": 0.0,
        "queue_length": 0,
        "congestion_events": 0,
    }


def test_processed_vehicle_waiting_time_statistics():
    stats = TrafficStatistics()
    stats.record_processed(Vehicle(1, waiting_time=4))
    stats.record_processed(Vehicle(2, waiting_time=8))
    stats.record_processed(Vehicle(3, waiting_time=6))

    result = stats.get_statistics()

    assert result["vehicles_processed"] == 3
    assert result["average_waiting_time"] == pytest.approx(6.0)
    assert result["maximum_waiting_time"] == 8


def test_queue_length_updates_without_removing_vehicles():
    stats = TrafficStatistics()
    queue = LaneQueue[Vehicle]()
    queue.enqueue(Vehicle(1))
    queue.enqueue(Vehicle(2))

    stats.update(
        {"North": [queue]},
        DemandMonitor().measure({"North": [queue]}),
    )

    assert stats.get_statistics()["queue_length"] == 2
    assert queue.size() == 2


def test_queue_length_updates_after_vehicle_moves():
    stats = TrafficStatistics()
    queue = LaneQueue[Vehicle]()
    queue.enqueue(Vehicle(1))
    queue.enqueue(Vehicle(2))

    demand = DemandMonitor()
    stats.update({"North": [queue]}, demand.measure({"North": [queue]}))

    queue.dequeue()
    result = stats.update(
        {"North": [queue]},
        demand.measure({"North": [queue]}),
    )

    assert result["queue_length"] == 1


def test_congestion_event_is_counted_once_until_cleared():
    detector = CongestionDetector(
        demand_threshold=1,
        queue_length_threshold=1,
    )
    stats = TrafficStatistics(detector)
    queue = LaneQueue[Vehicle]()
    demand = DemandMonitor()

    queue.enqueue(Vehicle(1))
    queue.enqueue(Vehicle(2))

    for _ in range(3):
        measurements = demand.measure({"North": [queue]})
        stats.update({"North": [queue]}, measurements)

    assert stats.get_statistics()["congestion_events"] == 1

    queue.dequeue()
    measurements = demand.measure({"North": [queue]})
    stats.update({"North": [queue]}, measurements)

    queue.enqueue(Vehicle(3))
    measurements = demand.measure({"North": [queue]})
    result = stats.update({"North": [queue]}, measurements)

    assert result["congestion_events"] == 2


def test_invalid_processed_vehicle_is_rejected():
    stats = TrafficStatistics()

    with pytest.raises(TypeError):
        stats.record_processed("not a vehicle")


def test_negative_waiting_time_is_rejected():
    stats = TrafficStatistics()

    vehicle = Vehicle(1)
    vehicle.waiting_time = -1

    with pytest.raises(ValueError):
        stats.record_processed(vehicle)

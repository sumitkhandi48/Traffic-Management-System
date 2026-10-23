
import pytest

from simulation.traffic.demand_monitor import DemandMonitor
from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


def test_counts_waiting_vehicles_at_each_approach():
    north = LaneQueue[Vehicle]()
    south = LaneQueue[Vehicle]()

    north.enqueue(Vehicle(vehicle_id=1))
    north.enqueue(Vehicle(vehicle_id=2))
    south.enqueue(Vehicle(vehicle_id=3))

    results = DemandMonitor().measure({
        "North": [north],
        "South": [south],
    })

    assert results["North"].waiting_vehicle_count == 2
    assert results["South"].waiting_vehicle_count == 1


def test_waiting_time_contributes_to_demand():
    queue = LaneQueue[Vehicle]()
    queue.enqueue(Vehicle(vehicle_id=1, waiting_time=10))

    result = DemandMonitor(waiting_time_weight=0.1).measure({
        "North": [queue],
    })["North"]

    assert result.total_waiting_time == 10
    assert result.demand_score == pytest.approx(2.0)


def test_demand_increases_when_more_vehicles_wait():
    queue = LaneQueue[Vehicle]()
    monitor = DemandMonitor()

    queue.enqueue(Vehicle(vehicle_id=1))
    first = monitor.measure({"North": [queue]})["North"]

    queue.enqueue(Vehicle(vehicle_id=2))
    second = monitor.measure({"North": [queue]})["North"]

    assert second.waiting_vehicle_count > first.waiting_vehicle_count
    assert second.demand_score > first.demand_score


def test_demand_updates_when_waiting_time_increases():
    queue = LaneQueue[Vehicle]()
    vehicle = Vehicle(vehicle_id=1, waiting_time=2)
    queue.enqueue(vehicle)
    monitor = DemandMonitor()

    first = monitor.measure({"North": [queue]})["North"]
    vehicle.waiting_time = 12
    second = monitor.measure({"North": [queue]})["North"]

    assert second.total_waiting_time > first.total_waiting_time
    assert second.demand_score > first.demand_score


def test_empty_approach_has_zero_demand():
    queue = LaneQueue[Vehicle]()

    result = DemandMonitor().measure({
        "North": [queue],
    })["North"]

    assert result.waiting_vehicle_count == 0
    assert result.total_waiting_time == 0
    assert result.demand_score == 0


def test_multiple_lanes_are_counted_for_one_approach():
    lane_one = LaneQueue[Vehicle]()
    lane_two = LaneQueue[Vehicle]()

    lane_one.enqueue(Vehicle(vehicle_id=1, waiting_time=3))
    lane_two.enqueue(Vehicle(vehicle_id=2, waiting_time=7))

    result = DemandMonitor().measure({
        "East": [lane_one, lane_two],
    })["East"]

    assert result.waiting_vehicle_count == 2
    assert result.total_waiting_time == 10
    assert result.demand_score == pytest.approx(3.0)


def test_measurement_does_not_remove_vehicles():
    queue = LaneQueue[Vehicle]()
    queue.enqueue(Vehicle(vehicle_id=1))
    queue.enqueue(Vehicle(vehicle_id=2))

    DemandMonitor().measure({"West": [queue]})

    assert queue.size() == 2


def test_negative_waiting_time_weight_is_rejected():
    with pytest.raises(ValueError):
        DemandMonitor(waiting_time_weight=-0.1)


def test_invalid_queue_type_is_rejected():
    with pytest.raises(TypeError):
        DemandMonitor().measure({"North": [object()]})

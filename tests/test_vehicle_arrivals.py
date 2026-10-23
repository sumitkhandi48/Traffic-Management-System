"""Tests for dynamic vehicle arrivals and lane assignment."""

import pytest

from simulation.traffic.lane_queue import LaneQueue
from simulation.traffic.vehicle_arrivals import VehicleArrivalGenerator
from simulation.vehicles.vehicle import Vehicle


@pytest.fixture
def traffic_setup():
    """Create approaches with two lanes each."""
    north_lane_1 = LaneQueue[Vehicle]()
    north_lane_2 = LaneQueue[Vehicle]()
    south_lane_1 = LaneQueue[Vehicle]()

    approaches = {
        "North": [north_lane_1, north_lane_2],
        "South": [south_lane_1],
    }

    generator = VehicleArrivalGenerator(approaches)

    return generator, north_lane_1, north_lane_2, south_lane_1


def test_generates_vehicle_and_adds_it_to_lane(traffic_setup):
    generator, north_lane_1, _, _ = traffic_setup

    vehicle = generator.generate_vehicle("North")

    assert isinstance(vehicle, Vehicle)
    assert north_lane_1.size() == 1
    assert north_lane_1.peek() == vehicle


def test_generated_vehicle_ids_are_unique(traffic_setup):
    generator, _, _, _ = traffic_setup

    first = generator.generate_vehicle("North")
    second = generator.generate_vehicle("South")

    assert first.vehicle_id != second.vehicle_id


def test_assigns_vehicle_to_selected_lane(traffic_setup):
    generator, north_lane_1, north_lane_2, _ = traffic_setup

    vehicle = generator.generate_vehicle("North", lane_index=1)

    assert north_lane_1.is_empty()
    assert north_lane_2.peek() == vehicle


def test_preserves_vehicle_type_and_arrival_time(traffic_setup):
    generator, _, _, south_lane_1 = traffic_setup

    vehicle = generator.generate_vehicle(
        "South",
        arrival_time=12.5,
        vehicle_type="emergency",
    )

    assert vehicle.vehicle_type == "emergency"
    assert vehicle.arrival_time == 12.5
    assert south_lane_1.peek() == vehicle


def test_rejects_unknown_approach(traffic_setup):
    generator, north_lane_1, _, _ = traffic_setup

    with pytest.raises(ValueError, match="unknown approach"):
        generator.generate_vehicle("West")

    assert north_lane_1.is_empty()


def test_rejects_invalid_lane_index(traffic_setup):
    generator, north_lane_1, _, _ = traffic_setup

    with pytest.raises(ValueError, match="lane_index"):
        generator.generate_vehicle("North", lane_index=2)

    assert north_lane_1.is_empty()


def test_rejects_negative_arrival_time(traffic_setup):
    generator, _, _, south_lane_1 = traffic_setup

    with pytest.raises(ValueError, match="arrival_time"):
        generator.generate_vehicle("South", arrival_time=-1)

    assert south_lane_1.is_empty()


def test_rejects_invalid_vehicle_type(traffic_setup):
    generator, _, _, south_lane_1 = traffic_setup

    with pytest.raises(ValueError, match="vehicle_type"):
        generator.generate_vehicle(
            "South",
            vehicle_type="bus",
        )

    assert south_lane_1.is_empty()


def test_rejects_empty_approach_configuration():
    with pytest.raises(ValueError, match="at least one approach"):
        VehicleArrivalGenerator({})
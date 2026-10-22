
import pytest

from simulation.vehicles.classification import classify_vehicle
from simulation.vehicles.vehicle import Vehicle


def test_vehicle_defaults_to_normal() -> None:
    vehicle = Vehicle(vehicle_id=1)

    assert vehicle.vehicle_type == "normal"
    assert classify_vehicle(vehicle) == "normal"


def test_emergency_vehicle_is_classified_correctly() -> None:
    vehicle = Vehicle(vehicle_id=2, vehicle_type="emergency")

    assert classify_vehicle(vehicle) == "emergency"


@pytest.mark.parametrize(
    "vehicle_id,arrival_time,waiting_time",
    [
        (-1, 0.0, 0.0),
        (1, -1.0, 0.0),
        (1, 0.0, -1.0),
    ],
)
def test_negative_values_are_rejected(
    vehicle_id: int,
    arrival_time: float,
    waiting_time: float,
) -> None:
    with pytest.raises(ValueError):
        Vehicle(
            vehicle_id=vehicle_id,
            arrival_time=arrival_time,
            waiting_time=waiting_time,
        )


def test_invalid_vehicle_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        Vehicle(vehicle_id=1, vehicle_type="bus")


def test_classification_rejects_non_vehicle_input() -> None:
    with pytest.raises(TypeError):
        classify_vehicle("emergency")  # type: ignore[arg-type]

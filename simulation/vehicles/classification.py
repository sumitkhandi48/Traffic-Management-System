
from simulation.vehicles.vehicle import Vehicle


def classify_vehicle(vehicle: Vehicle) -> str:
    """Return the classification of a vehicle."""
    if not isinstance(vehicle, Vehicle):
        raise TypeError("vehicle must be a Vehicle instance")

    return vehicle.vehicle_type

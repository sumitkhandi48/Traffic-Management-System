import pytest

from ui.traffic_dashboard import TrafficDashboard


def make_dashboard():
    """Create a dashboard instance without launching the GUI."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.APPROACHES = ("North", "South", "East", "West")
    app.vehicle_queues = {
        "North": [],
        "South": [],
        "East": [],
        "West": [],
    }
    app.emergency_vehicles = set()
    app.emergency_approaches = set()
    app.signal_states = {
        approach: "RED" for approach in app.APPROACHES
    }
    app._active_axis = "NS"
    app._phase_duration = 5.0

    return app


def test_higher_north_south_demand_selects_ns():
    app = make_dashboard()
    app.vehicle_queues["North"] = ["N1", "N2", "N3"]
    app.vehicle_queues["East"] = ["E1"]

    app._choose_next_phase()

    assert app._active_axis == "NS"


def test_higher_east_west_demand_selects_ew():
    app = make_dashboard()
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = ["E1", "E2", "E3"]

    app._choose_next_phase()

    assert app._active_axis == "EW"


def test_only_axis_with_traffic_is_selected():
    app = make_dashboard()
    app.vehicle_queues["East"] = ["E1"]

    app._choose_next_phase()

    assert app._active_axis == "EW"


def test_equal_demand_alternates_axes():
    app = make_dashboard()
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = ["E1"]

    app._choose_next_phase()

    assert app._active_axis == "EW"


def test_equal_demand_alternates_from_ew_to_ns():
    app = make_dashboard()
    app._active_axis = "EW"
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = ["E1"]

    app._choose_next_phase()

    assert app._active_axis == "NS"


def test_empty_queues_use_alternating_fallback():
    app = make_dashboard()

    app._choose_next_phase()

    assert app._active_axis == "EW"


def test_emergency_vehicle_receives_axis_priority():
    app = make_dashboard()
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = ["E1", "E2", "E3"]
    app.emergency_vehicles.add("N1")

    app._choose_next_phase()

    assert app._active_axis == "NS"


@pytest.mark.parametrize(
    ("axis", "green_approaches", "red_approaches"),
    [
        ("NS", ("North", "South"), ("East", "West")),
        ("EW", ("East", "West"), ("North", "South")),
    ],
)
def test_selected_phase_keeps_crossing_axis_red(
    axis, green_approaches, red_approaches
):
    app = make_dashboard()

    app._set_signal_phase(axis)

    for approach in green_approaches:
        assert app.signal_states[approach] == "GREEN"

    for approach in red_approaches:
        assert app.signal_states[approach] == "RED"
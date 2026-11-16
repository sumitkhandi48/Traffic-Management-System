import pytest

from ui.traffic_dashboard import TrafficDashboard


def make_dashboard():
    """Create a dashboard instance without launching the GUI."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.APPROACHES = ("North", "East", "South", "West")
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
    app._active_axis = "North"
    app._phase_duration = 5.0

    return app


def test_higher_north_south_demand_selects_ns():
    app = make_dashboard()
    app._active_axis = "West"
    app.vehicle_queues["North"] = ["N1", "N2", "N3"]
    app.vehicle_queues["East"] = ["E1"]

    app._choose_next_phase()

    assert app._active_axis == "North"


def test_higher_east_west_demand_selects_ew():
    app = make_dashboard()
    app._active_axis = "North"
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = ["E1", "E2", "E3"]

    app._choose_next_phase()

    assert app._active_axis == "East"


def test_only_axis_with_traffic_is_selected():
    app = make_dashboard()
    app._active_axis = "North"
    app.vehicle_queues["East"] = ["E1"]

    app._choose_next_phase()

    assert app._active_axis == "East"


def test_equal_demand_alternates_axes():
    app = make_dashboard()
    app._active_axis = "North"
    app.vehicle_queues["East"] = ["E1"]
    app.vehicle_queues["South"] = ["S1"]

    app._choose_next_phase()

    # Clockwise default from North is East when counts are equal
    assert app._active_axis == "East"


def test_equal_demand_alternates_from_ew_to_ns():
    app = make_dashboard()
    app._active_axis = "East"
    app.vehicle_queues["South"] = ["S1"]
    app.vehicle_queues["West"] = ["W1"]

    app._choose_next_phase()

    # Clockwise default from East is South when counts are equal
    assert app._active_axis == "South"


def test_empty_queues_use_alternating_fallback():
    app = make_dashboard()
    app._active_axis = "North"

    app._choose_next_phase()

    # Clockwise default from North is East
    assert app._active_axis == "East"


def test_emergency_vehicle_receives_axis_priority():
    app = make_dashboard()
    app._active_axis = "East"
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = ["E1", "E2", "E3"]
    app.emergency_vehicles.add("N1")

    app._choose_next_phase()

    assert app._active_axis == "North"


@pytest.mark.parametrize(
    ("approach", "green_approaches", "red_approaches"),
    [
        ("North", ("North",), ("East", "South", "West")),
        ("East", ("East",), ("North", "South", "West")),
        ("South", ("South",), ("North", "East", "West")),
        ("West", ("West",), ("North", "East", "South")),
    ],
)
def test_selected_phase_keeps_crossing_axis_red(
    approach, green_approaches, red_approaches
):
    app = make_dashboard()

    app._set_signal_phase(approach)

    for app_name in green_approaches:
        assert app.signal_states[app_name] == "GREEN"

    for app_name in red_approaches:
        assert app.signal_states[app_name] == "RED"
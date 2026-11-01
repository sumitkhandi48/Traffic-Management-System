"""Tests for the traffic dashboard."""

from unittest.mock import Mock

import pytest

from ui.traffic_dashboard import TrafficDashboard


@pytest.fixture
def dashboard():
    """Create a dashboard instance for testing."""
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("A graphical display is required for Tkinter tests.")

    root.withdraw()
    app = TrafficDashboard(root)
    yield app
    root.destroy()


def test_dashboard_initial_state(dashboard):
    """The dashboard starts with empty queues and a stopped engine."""
    assert dashboard.engine.state.value == "stopped"

    for approach in dashboard.APPROACHES:
        assert dashboard.vehicle_queues[approach] == []
        assert dashboard.signal_states[approach] == "RED"


def test_add_vehicle_updates_queue(dashboard):
    """Adding a vehicle creates one entry in a queue."""
    dashboard.add_vehicle()

    total = sum(
        len(dashboard.vehicle_queues[approach])
        for approach in dashboard.APPROACHES
    )

    assert total == 1


def test_add_vehicle_updates_statistics(dashboard):
    """The total waiting-vehicle statistic matches the queues."""
    dashboard.add_vehicle()
    dashboard.add_vehicle()
    dashboard._refresh_display()

    assert dashboard.total_vehicles_label.cget("text") == (
        "Total waiting vehicles: 2"
    )


def test_reset_clears_queues_and_waiting_times(dashboard):
    """Reset clears vehicles and their waiting-time records."""
    dashboard.add_vehicle()
    dashboard.add_vehicle()
    dashboard.reset_simulation()

    for approach in dashboard.APPROACHES:
        assert dashboard.vehicle_queues[approach] == []
        assert dashboard.vehicle_waiting_times[approach] == {}

    assert dashboard.engine.state.value == "stopped"
    assert dashboard.total_vehicles_label.cget("text") == (
        "Total waiting vehicles: 0"
    )


# NFR-02: Control responsiveness regression tests.

CONTROL_ACTIONS = [
    ("start_simulation", "start"),
    ("pause_simulation", "pause"),
    ("resume_simulation", "resume"),
    ("stop_simulation", "stop"),
]


def make_dashboard_for_control_test():
    """Create a dashboard instance without opening a Tkinter window."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.engine = Mock()
    app._refresh_display = Mock()

    # Attributes used by start_simulation().
    app._phase_elapsed = 1.5
    app._movement_elapsed = 0.5
    app._choose_next_phase = Mock()

    return app


@pytest.mark.parametrize(
    ("dashboard_method", "engine_method"),
    CONTROL_ACTIONS,
)
def test_control_action_refreshes_after_success(
    dashboard_method,
    engine_method,
):
    """A successful control action refreshes the display once."""
    app = make_dashboard_for_control_test()
    getattr(app.engine, engine_method).return_value = True

    getattr(app, dashboard_method)()

    app._refresh_display.assert_called_once()

    if dashboard_method == "start_simulation":
        assert app._phase_elapsed == 0.0
        assert app._movement_elapsed == 0.0
        app._choose_next_phase.assert_called_once()


@pytest.mark.parametrize(
    ("dashboard_method", "engine_method"),
    CONTROL_ACTIONS,
)
def test_control_action_does_not_refresh_after_rejection(
    dashboard_method,
    engine_method,
):
    """A rejected control action avoids an unnecessary UI refresh."""
    app = make_dashboard_for_control_test()
    getattr(app.engine, engine_method).return_value = False

    getattr(app, dashboard_method)()

    app._refresh_display.assert_not_called()

    if dashboard_method == "start_simulation":
        assert app._phase_elapsed == 1.5
        assert app._movement_elapsed == 0.5
        app._choose_next_phase.assert_not_called()

def test_start_action_avoids_unnecessary_refresh_work():
    """Start resets timing and chooses a phase before refreshing once."""
    app = make_dashboard_for_control_test()
    app.engine.start.return_value = True

    app.start_simulation()

    assert app._phase_elapsed == 0.0
    assert app._movement_elapsed == 0.0
    app._choose_next_phase.assert_called_once()
    app._refresh_display.assert_called_once()


def make_dashboard_for_emergency_test():
    """Create a dashboard without opening a Tkinter window."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.APPROACHES = ("North", "South", "East", "West")
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
    app._active_axis = "EW"

    return app


def test_emergency_vehicle_moves_before_normal_vehicle():
    """An emergency vehicle gets priority within its approach queue."""
    app = make_dashboard_for_emergency_test()

    app.vehicle_queues["North"] = ["normal-1", "emergency-1"]
    app.emergency_vehicles.add("emergency-1")
    app.vehicle_waiting_times["North"] = {
        "normal-1": 5,
        "emergency-1": 10,
    }
    app.signal_states["North"] = "GREEN"

    app._move_vehicles_on_green()

    assert app.vehicle_queues["North"] == ["normal-1"]
    assert "emergency-1" not in app.emergency_vehicles
    assert "emergency-1" not in app.vehicle_waiting_times["North"]


def test_emergency_vehicle_does_not_move_on_red_signal():
    """An emergency vehicle must wait while its signal is red."""
    app = make_dashboard_for_emergency_test()

    app.vehicle_queues["East"] = ["emergency-1"]
    app.emergency_vehicles.add("emergency-1")
    app.signal_states["East"] = "RED"

    app._move_vehicles_on_green()

    assert app.vehicle_queues["East"] == ["emergency-1"]
    assert "emergency-1" in app.emergency_vehicles


def test_emergency_priority_selects_correct_axis():
    """An emergency vehicle determines the selected signal axis."""
    app = make_dashboard_for_emergency_test()

    app.vehicle_queues["North"] = ["emergency-1"]
    app.emergency_vehicles.add("emergency-1")
    app._set_signal_phase = Mock()

    app._choose_next_phase()

    app._set_signal_phase.assert_called_once_with("NS")


def test_emergency_priority_keeps_opposite_axis_red():
    """Selecting an emergency axis keeps the conflicting axis red."""
    app = make_dashboard_for_emergency_test()

    app._set_signal_phase = lambda axis: (
        app.signal_states.update({
            "North": "GREEN" if axis == "NS" else "RED",
            "South": "GREEN" if axis == "NS" else "RED",
            "East": "GREEN" if axis == "EW" else "RED",
            "West": "GREEN" if axis == "EW" else "RED",
        })
    )

    app._set_signal_phase("NS")

    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "GREEN"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"


def test_signal_transition_uses_yellow_and_all_red_clearance():
    """Signal axes must switch only after yellow and all-red clearance."""
    app = make_dashboard_for_emergency_test()

    app.YELLOW_CLEARANCE_DURATION = 1.0
    app.ALL_RED_CLEARANCE_DURATION = 1.0
    app._transition_state = None
    app._transition_elapsed = 0.0
    app._pending_axis = None
    app._emergency_override = False
    app._phase_duration = 5.0

    app._set_signal_phase = lambda axis: (
        app.signal_states.update({
            "North": "GREEN" if axis == "NS" else "RED",
            "South": "GREEN" if axis == "NS" else "RED",
            "East": "GREEN" if axis == "EW" else "RED",
            "West": "GREEN" if axis == "EW" else "RED",
        }),
        setattr(app, "_active_axis", axis),
    )

    app._set_signal_phase("NS")
    app._begin_signal_transition("EW")

    assert app.signal_states["North"] == "YELLOW"
    assert app.signal_states["South"] == "YELLOW"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

    app._advance_signal_transition(1.0)

    assert app._transition_state == "ALL_RED"
    assert all(
        state == "RED" for state in app.signal_states.values()
    )

    app._advance_signal_transition(1.0)

    assert app._transition_state is None
    assert app.signal_states["East"] == "GREEN"
    assert app.signal_states["West"] == "GREEN"
    assert app.signal_states["North"] == "RED"
    assert app.signal_states["South"] == "RED"


def test_emergency_axis_waits_for_signal_clearance():
    """Emergency priority must not bypass yellow and all-red clearance."""
    app = make_dashboard_for_emergency_test()

    app.YELLOW_CLEARANCE_DURATION = 1.0
    app.ALL_RED_CLEARANCE_DURATION = 1.0
    app._transition_state = None
    app._transition_elapsed = 0.0
    app._pending_axis = None
    app._emergency_override = False
    app._phase_duration = 5.0

    app._set_signal_phase = lambda axis: (
        app.signal_states.update({
            "North": "GREEN" if axis == "NS" else "RED",
            "South": "GREEN" if axis == "NS" else "RED",
            "East": "GREEN" if axis == "EW" else "RED",
            "West": "GREEN" if axis == "EW" else "RED",
        }),
        setattr(app, "_active_axis", axis),
    )

    app._set_signal_phase("EW")
    app.vehicle_queues["North"] = ["emergency-1"]
    app.emergency_vehicles.add("emergency-1")

    app._begin_signal_transition("NS")

    assert app.signal_states["East"] == "YELLOW"
    assert app.signal_states["West"] == "YELLOW"
    assert app.signal_states["North"] == "RED"

    app._advance_signal_transition(1.0)

    assert all(
        state == "RED" for state in app.signal_states.values()
    )

    app._advance_signal_transition(1.0)

    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "GREEN"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

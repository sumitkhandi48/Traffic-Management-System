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
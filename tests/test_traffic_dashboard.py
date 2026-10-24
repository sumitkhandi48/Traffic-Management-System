"""Tests for the traffic dashboard."""

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
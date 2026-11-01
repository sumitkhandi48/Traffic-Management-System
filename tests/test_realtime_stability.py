"""Regression tests for real-time simulation stability."""

from unittest.mock import Mock, patch
import pytest
from simulation.engine import SimulationEngine, SimulationState
from ui.traffic_dashboard import TrafficDashboard


def make_dashboard():
    """Create a dashboard without opening a Tkinter window."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.engine = SimulationEngine()
    app.APPROACHES = ("North", "South", "East", "West")
    app.vehicle_queues = {
        approach: [] for approach in app.APPROACHES
    }
    app.vehicle_waiting_times = {
        approach: {} for approach in app.APPROACHES
    }

    app._tick_interval = 100
    app._last_tick_time = 10.0
    app._phase_elapsed = 0.0
    app._movement_elapsed = 0.0
    app._phase_duration = 5.0
    app._active_axis = "NS"

    app._choose_next_phase = Mock()
    app._move_vehicles_on_green = Mock()
    app._refresh_display = Mock()

    app.root = Mock()
    app.root.after = Mock()

    return app


def test_tick_reschedules_itself_when_simulation_is_stopped():
    app = make_dashboard()

    app._tick()

    app.root.after.assert_called_once_with(
        app._tick_interval, app._tick
    )


def test_tick_advances_simulation_when_running():
    """A normal tick advances time by the measured interval."""
    app = make_dashboard()
    app.engine.start()

    with patch(
        "ui.traffic_dashboard.time.monotonic",
        return_value=10.1,
    ):
        app._tick()

    assert app.engine.simulation_time == pytest.approx(0.1)
    app._refresh_display.assert_called_once()
    app.root.after.assert_called_once_with(
        app._tick_interval, app._tick
    )


def test_tick_reschedules_after_processing_error(capsys):
    """A processing error is reported without stopping future ticks."""
    app = make_dashboard()
    app.engine.start()
    app._refresh_display.side_effect = RuntimeError("temporary UI error")

    app._tick()

    app.root.after.assert_called_once_with(
        app._tick_interval, app._tick
    )

    captured = capsys.readouterr()
    assert "Simulation update failed: temporary UI error" in captured.out


def test_tick_uses_actual_elapsed_time():
    """Delayed callbacks should account for actual elapsed time."""
    app = make_dashboard()
    app.engine.start()

    with patch(
        "ui.traffic_dashboard.time.monotonic",
        return_value=10.35,
    ):
        app._tick()

    assert app.engine.simulation_time == pytest.approx(0.35)

def test_tick_uses_updated_traffic_demand_for_next_phase():
    """The next phase must use the latest queue counts."""
    app = make_dashboard()
    app.engine.start()

    # Set up the initial traffic conditions.
    app.vehicle_queues["North"] = ["N1", "N2", "N3", "N4", "N5"]
    app.vehicle_queues["East"] = ["E1", "E2"]

    # Traffic conditions change before the current phase expires.
    app.vehicle_queues["North"] = ["N1"]
    app.vehicle_queues["East"] = [
        "E1", "E2", "E3", "E4", "E5", "E6"
    ]

    app.signal_states = {
        "North": "GREEN",
        "South": "GREEN",
        "East": "RED",
        "West": "RED",
    }

    app.emergency_vehicles = set()

    # Use the actual controller instead of the mocked method.
    app._choose_next_phase = (
        TrafficDashboard._choose_next_phase.__get__(
            app, TrafficDashboard
        )
    )

    app._phase_elapsed = 4.95

    with patch(
        "ui.traffic_dashboard.time.monotonic",
        return_value=10.1,
    ):
        app._tick()

    assert app._active_axis == "EW"
    assert app.signal_states["East"] == "GREEN"
    assert app.signal_states["West"] == "GREEN"
    assert app.signal_states["North"] == "RED"
    assert app.signal_states["South"] == "RED"
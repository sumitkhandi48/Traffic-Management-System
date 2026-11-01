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
    app.signal_states = {
        approach: (
            "GREEN" if approach in ("North", "South") else "RED"
        )
        for approach in app.APPROACHES
    }

    app.emergency_vehicles = set()
    app.emergency_approaches = set()
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

    # Initial traffic conditions.
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
    app.emergency_approaches = set()

    app.YELLOW_CLEARANCE_DURATION = 1.0
    app.ALL_RED_CLEARANCE_DURATION = 1.0
    app._transition_state = None
    app._transition_elapsed = 0.0
    app._pending_axis = None
    app._emergency_override = False

    # Use the actual controller, not the mocked method.
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

    # EW should be selected based on the updated queue demand.
    assert app._pending_axis == "EW"
    assert app._transition_state == "YELLOW"
    assert app._active_axis == "NS"

    assert app.signal_states["North"] == "YELLOW"
    assert app.signal_states["South"] == "YELLOW"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"


def test_tick_starts_clearance_when_normal_phase_expires():
    """A phase change through tick must start yellow clearance."""
    app = make_dashboard()
    app.engine.start()

    app.signal_states = {
        "North": "GREEN",
        "South": "GREEN",
        "East": "RED",
        "West": "RED",
    }

    app.emergency_vehicles = set()
    app.emergency_approaches = set()

    app.YELLOW_CLEARANCE_DURATION = 1.0
    app.ALL_RED_CLEARANCE_DURATION = 1.0
    app._transition_state = None
    app._transition_elapsed = 0.0
    app._pending_axis = None
    app._emergency_override = False

    app._phase_elapsed = 4.95

    def select_ew_phase():
        app._active_axis = "EW"
        app.signal_states.update({
            "North": "RED",
            "South": "RED",
            "East": "GREEN",
            "West": "GREEN",
        })

    app._choose_next_phase.side_effect = select_ew_phase

    with patch(
        "ui.traffic_dashboard.time.monotonic",
        return_value=10.1,
    ):
        app._tick()

    assert app._transition_state == "YELLOW"
    assert app._active_axis == "NS"

    assert app.signal_states["North"] == "YELLOW"
    assert app.signal_states["South"] == "YELLOW"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

    app._move_vehicles_on_green.assert_not_called()


def test_tick_starts_clearance_when_emergency_arrives():
    """An emergency on the opposite axis triggers yellow clearance."""
    app = make_dashboard()
    app.engine.start()

    app.signal_states = {
        "North": "GREEN",
        "South": "GREEN",
        "East": "RED",
        "West": "RED",
    }

    app._active_axis = "NS"
    app.emergency_vehicles.add("emergency-1")
    app.vehicle_queues["East"] = ["emergency-1"]

    app.YELLOW_CLEARANCE_DURATION = 1.0
    app.ALL_RED_CLEARANCE_DURATION = 1.0
    app._transition_state = None
    app._transition_elapsed = 0.0
    app._pending_axis = None
    app._emergency_override = False

    with patch(
        "ui.traffic_dashboard.time.monotonic",
        return_value=10.1,
    ):
        app._tick()

    assert app._transition_state == "YELLOW"

    assert app.signal_states["North"] == "YELLOW"
    assert app.signal_states["South"] == "YELLOW"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

    app._move_vehicles_on_green.assert_not_called()

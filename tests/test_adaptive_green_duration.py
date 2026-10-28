"""Tests for FR-07 adaptive green-light duration."""

import pytest

from ui.traffic_dashboard import TrafficDashboard


MIN_GREEN_DURATION = TrafficDashboard.MIN_GREEN_DURATION
MAX_GREEN_DURATION = TrafficDashboard.MAX_GREEN_DURATION


def make_dashboard():
    """Create a dashboard instance without opening a Tkinter window."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.APPROACHES = ("North", "South", "East", "West")
    app.vehicle_queues = {
        "North": [],
        "South": [],
        "East": [],
        "West": [],
    }
    app.signal_states = {
        approach: "RED" for approach in app.APPROACHES
    }
    app._active_axis = "NS"
    app._phase_duration = 5.0

    return app


def test_green_duration_increases_with_demand():
    """A larger queue should receive a longer green duration."""
    app = make_dashboard()

    app.vehicle_queues["North"] = ["N1"]
    app._set_signal_phase("NS")
    low_demand_duration = app._phase_duration

    app.vehicle_queues["North"] = ["N1", "N2", "N3", "N4"]
    app._set_signal_phase("NS")
    high_demand_duration = app._phase_duration

    assert high_demand_duration > low_demand_duration


def test_minimum_duration_is_used_for_empty_queue():
    """An empty axis must receive the minimum allowed green duration."""
    app = make_dashboard()

    app._set_signal_phase("NS")

    assert app._phase_duration == MIN_GREEN_DURATION


def test_maximum_duration_is_used_for_large_queue():
    """A large queue must not exceed the maximum allowed duration."""
    app = make_dashboard()
    app.vehicle_queues["North"] = [
        f"N{i}" for i in range(20)
    ]

    app._set_signal_phase("NS")

    assert app._phase_duration == MAX_GREEN_DURATION


@pytest.mark.parametrize(
    "vehicle_count",
    [0, 1, 2, 3, 5, 10, 100],
)
def test_duration_always_stays_within_limits(vehicle_count):
    """Green duration must remain within its configured limits."""
    app = make_dashboard()
    app.vehicle_queues["North"] = [
        f"N{i}" for i in range(vehicle_count)
    ]

    app._set_signal_phase("NS")

    assert (
        MIN_GREEN_DURATION
        <= app._phase_duration
        <= MAX_GREEN_DURATION
    )


def test_demand_counts_both_approaches_on_axis():
    """Demand from both approaches contributes to green duration."""
    app = make_dashboard()
    app.vehicle_queues["North"] = ["N1", "N2"]
    app.vehicle_queues["South"] = ["S1", "S2"]

    app._set_signal_phase("NS")

    assert app._phase_duration == 7.0


def test_crossing_axis_remains_red():
    """The crossing axis must remain red when an axis is green."""
    app = make_dashboard()

    app._set_signal_phase("NS")

    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "GREEN"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"
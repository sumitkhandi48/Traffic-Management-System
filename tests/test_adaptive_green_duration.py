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
    app._phase_duration = 10.0

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
        f"N{i}" for i in range(60)
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
    """Active approach demand contributes to green duration."""
    app = make_dashboard()
    app.vehicle_queues["North"] = ["N1", "N2"]
    app.vehicle_queues["South"] = ["S1", "S2"]

    app._set_signal_phase("North")

    assert app._phase_duration == 12.0


def test_ut_13_dynamic_green_duration_proportional_to_demand():
    """UT_13: Low demand (2 vehicles) vs High demand (10 vehicles) scales proportionally."""
    app = make_dashboard()

    app.vehicle_queues["North"] = ["N1", "N2"]
    app._set_signal_phase("NS")
    low_demand_duration = app._phase_duration

    app.vehicle_queues["North"] = [f"N{i}" for i in range(10)]
    app._set_signal_phase("NS")
    high_demand_duration = app._phase_duration

    assert low_demand_duration == 12.0
    assert high_demand_duration == 20.0
    assert high_demand_duration > low_demand_duration


def test_ut_14_green_duration_strictly_respects_10s_min_and_60s_max():
    """UT_14: Green-light duration never falls below 10 seconds or exceeds 60 seconds."""
    assert MIN_GREEN_DURATION == 10.0
    assert MAX_GREEN_DURATION == 60.0

    app = make_dashboard()
    app._set_signal_phase("NS")
    assert app._phase_duration == 10.0

    app.vehicle_queues["North"] = [f"N{i}" for i in range(200)]
    app._set_signal_phase("NS")
    assert app._phase_duration == 60.0


def test_crossing_axis_remains_red():
    """Only 1 approach is green at a time; all other approaches must remain red."""
    app = make_dashboard()

    app._set_signal_phase("North")

    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"
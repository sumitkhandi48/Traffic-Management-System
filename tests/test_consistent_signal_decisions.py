"""Tests for NFR-05: Consistent adaptive signal decisions."""

import pytest

from ui.traffic_dashboard import TrafficDashboard


def make_dashboard(
    active_axis="NS",
    queues=None,
    emergency_vehicles=None,
):
    """Create a dashboard with a controlled traffic configuration."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.APPROACHES = ("North", "South", "East", "West")

    app.vehicle_queues = {
        approach: [] for approach in app.APPROACHES
    }

    if queues:
        for approach, vehicles in queues.items():
            app.vehicle_queues[approach] = list(vehicles)

    app.emergency_vehicles = set(emergency_vehicles or set())
    app.emergency_approaches = set()

    app.signal_states = {
        approach: "RED" for approach in app.APPROACHES
    }

    app._active_axis = active_axis
    app._phase_duration = 5.0

    return app


def get_signal_decision(app):
    """Execute the controller and capture its resulting decision."""
    app._choose_next_phase()

    return (
        app._active_axis,
        dict(app.signal_states),
        app._phase_duration,
    )


@pytest.mark.parametrize(
    (
        "active_axis",
        "queues",
        "emergency_vehicles",
        "expected_axis",
    ),
    [
        # Higher North/South demand.
        (
            "NS",
            {"North": ["N1", "N2", "N3"], "East": ["E1"]},
            set(),
            "NS",
        ),

        # Higher East/West demand.
        (
            "NS",
            {"North": ["N1"], "East": ["E1", "E2", "E3"]},
            set(),
            "EW",
        ),

        # Equal demand with North/South currently active.
        (
            "NS",
            {"North": ["N1"], "East": ["E1"]},
            set(),
            "EW",
        ),

        # Equal demand with East/West currently active.
        (
            "EW",
            {"North": ["N1"], "East": ["E1"]},
            set(),
            "NS",
        ),

        # Emergency vehicle receives priority over normal demand.
        (
            "NS",
            {"North": ["N1"], "East": ["E1", "E2", "E3"]},
            {"N1"},
            "NS",
        ),

        # Emergency vehicle on East/West receives priority.
        (
            "NS",
            {"North": ["N1", "N2", "N3"], "West": ["W1"]},
            {"W1"},
            "EW",
        ),

        # Empty queues use the configured alternating fallback.
        (
            "NS",
            {},
            set(),
            "EW",
        ),
    ],
)
def test_identical_conditions_produce_identical_decisions(
    active_axis,
    queues,
    emergency_vehicles,
    expected_axis,
):
    """Identical controller inputs must produce identical decisions."""

    first_dashboard = make_dashboard(
        active_axis,
        queues,
        emergency_vehicles,
    )

    second_dashboard = make_dashboard(
        active_axis,
        queues,
        emergency_vehicles,
    )

    first_decision = get_signal_decision(first_dashboard)
    second_decision = get_signal_decision(second_dashboard)

    assert first_decision == second_decision
    assert first_decision[0] == expected_axis


def test_signal_decisions_are_repeatable_across_independent_runs():
    """Repeated runs with identical initial conditions remain consistent."""

    decisions = []

    for _ in range(5):
        app = make_dashboard(
            active_axis="NS",
            queues={
                "North": ["N1", "N2"],
                "East": ["E1"],
            },
        )

        decisions.append(get_signal_decision(app))

    assert all(
        decision == decisions[0]
        for decision in decisions
    )
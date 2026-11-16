"""Tests for explicit signal phase lifecycle and clearance safety."""

import pytest

from simulation.phases import PhaseTransitionState, SignalColor, SignalPhaseController


def test_initial_state_is_all_red():
    """Before starting, all approaches should display red."""
    controller = SignalPhaseController()
    assert controller.active_axis in ("North", "NS")
    assert controller.transition_state == PhaseTransitionState.NONE
    assert all(state == SignalColor.RED.value for state in controller.signal_states.values())


def test_start_sets_selected_axis_green():
    """Starting the controller activates the chosen approach and keeps others red."""
    controller = SignalPhaseController()
    controller.start("North", duration=15.0)

    states = controller.signal_states
    assert states["North"] == SignalColor.GREEN.value
    assert states["South"] == SignalColor.RED.value
    assert states["East"] == SignalColor.RED.value
    assert states["West"] == SignalColor.RED.value
    assert controller.phase_duration == 15.0


def test_clearance_lifecycle_green_yellow_allred_green():
    """A phase switch must progress through YELLOW -> ALL_RED -> target GREEN."""
    controller = SignalPhaseController(
        yellow_duration=1.0,
        all_red_duration=1.0,
    )
    controller.start("North", duration=12.0)

    # 1. Request switch to East
    transition_started = controller.request_phase_switch("East", target_green_duration=18.0)
    assert transition_started is True
    assert controller.transition_state == PhaseTransitionState.YELLOW
    assert controller.signal_states["North"] == SignalColor.YELLOW.value
    assert controller.signal_states["South"] == SignalColor.RED.value
    assert controller.signal_states["East"] == SignalColor.RED.value
    assert controller.signal_states["West"] == SignalColor.RED.value

    # 2. Advance 0.5s into Yellow (still yellow)
    done, new_axis = controller.step(0.5)
    assert done is False
    assert controller.transition_state == PhaseTransitionState.YELLOW

    # 3. Advance another 0.5s (reaches 1.0s yellow limit -> enters ALL_RED)
    done, new_axis = controller.step(0.5)
    assert done is False
    assert controller.transition_state == PhaseTransitionState.ALL_RED
    assert all(state == SignalColor.RED.value for state in controller.signal_states.values())

    # 4. Advance 0.5s into All-Red (still all red)
    done, new_axis = controller.step(0.5)
    assert done is False
    assert controller.transition_state == PhaseTransitionState.ALL_RED
    assert all(state == SignalColor.RED.value for state in controller.signal_states.values())

    # 5. Advance another 0.5s (reaches 1.0s all-red limit -> activates East GREEN)
    done, new_axis = controller.step(0.5)
    assert done is True
    assert new_axis == "East"
    assert controller.active_axis == "East"
    assert controller.transition_state == PhaseTransitionState.NONE
    assert controller.signal_states["East"] == SignalColor.GREEN.value
    assert controller.signal_states["North"] == SignalColor.RED.value
    assert controller.signal_states["South"] == SignalColor.RED.value
    assert controller.signal_states["West"] == SignalColor.RED.value
    assert controller.phase_duration == 18.0


def test_conflicting_green_is_never_emitted():
    """At every step and transition, ONLY 1 signal is ever GREEN at a time."""
    controller = SignalPhaseController(
        yellow_duration=1.0,
        all_red_duration=1.0,
    )
    controller.start("North", duration=4.0)

    # Execute multiple clockwise phase cycles in 0.1s increments
    for cycle in range(6):
        target = controller.get_clockwise_next(controller.active_axis)
        controller.request_phase_switch(target, target_green_duration=5.0)

        for step in range(80):  # 8.0 seconds total per cycle
            controller.step(0.1)
            states = controller.signal_states

            # Invariant 1: At most 1 signal is GREEN at any time
            green_count = sum(1 for s in states.values() if s == SignalColor.GREEN.value)
            assert green_count <= 1, f"Multiple GREEN signals detected at cycle {cycle}, step {step}! States: {states}"

            # Invariant 2: Yellow cannot co-exist with Green
            yellow_count = sum(1 for s in states.values() if s == SignalColor.YELLOW.value)
            assert not (green_count > 0 and yellow_count > 0), (
                f"Yellow and Green co-existing at cycle {cycle}, step {step}! States: {states}"
            )


def test_green_duration_clamped_within_limits():
    """Requested green durations must strictly adhere to MIN and MAX limits."""
    controller = SignalPhaseController(
        min_green_duration=3.0,
        max_green_duration=8.0,
    )
    controller.start("NS", duration=1.0)  # Below min
    assert controller.phase_duration == 3.0

    controller.request_phase_switch("NS", target_green_duration=20.0)  # Above max
    assert controller.phase_duration == 8.0

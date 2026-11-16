"""Tests for explicit signal phase lifecycle and clearance safety."""

import pytest

from simulation.phases import PhaseTransitionState, SignalColor, SignalPhaseController


def test_initial_state_is_all_red():
    """Before starting, all approaches should display red."""
    controller = SignalPhaseController()
    assert controller.active_axis == "NS"
    assert controller.transition_state == PhaseTransitionState.NONE
    assert all(state == SignalColor.RED.value for state in controller.signal_states.values())


def test_start_sets_selected_axis_green():
    """Starting the controller activates the chosen axis and keeps the other red."""
    controller = SignalPhaseController()
    controller.start("NS", duration=15.0)

    states = controller.signal_states
    assert states["North"] == SignalColor.GREEN.value
    assert states["South"] == SignalColor.GREEN.value
    assert states["East"] == SignalColor.RED.value
    assert states["West"] == SignalColor.RED.value
    assert controller.phase_duration == 15.0


def test_clearance_lifecycle_green_yellow_allred_green():
    """A phase switch must progress through YELLOW -> ALL_RED -> target GREEN."""
    controller = SignalPhaseController(
        yellow_duration=1.0,
        all_red_duration=1.0,
    )
    controller.start("NS", duration=12.0)

    # 1. Request switch to EW
    transition_started = controller.request_phase_switch("EW", target_green_duration=18.0)
    assert transition_started is True
    assert controller.transition_state == PhaseTransitionState.YELLOW
    assert controller.signal_states["North"] == SignalColor.YELLOW.value
    assert controller.signal_states["South"] == SignalColor.YELLOW.value
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

    # 5. Advance another 0.5s (reaches 1.0s all-red limit -> activates EW GREEN)
    done, new_axis = controller.step(0.5)
    assert done is True
    assert new_axis == "EW"
    assert controller.active_axis == "EW"
    assert controller.transition_state == PhaseTransitionState.NONE
    assert controller.signal_states["East"] == SignalColor.GREEN.value
    assert controller.signal_states["West"] == SignalColor.GREEN.value
    assert controller.signal_states["North"] == SignalColor.RED.value
    assert controller.signal_states["South"] == SignalColor.RED.value
    assert controller.phase_duration == 18.0


def test_conflicting_green_is_never_emitted():
    """At every step and transition, conflicting GREEN signals must NEVER exist."""
    controller = SignalPhaseController(
        yellow_duration=1.0,
        all_red_duration=1.0,
    )
    controller.start("NS", duration=4.0)

    # Execute multiple back-and-forth phase cycles in 0.1s increments
    for cycle in range(6):
        target = "EW" if controller.active_axis == "NS" else "NS"
        controller.request_phase_switch(target, target_green_duration=5.0)

        for step in range(80):  # 8.0 seconds total per cycle
            controller.step(0.1)
            states = controller.signal_states

            ns_green = (
                states["North"] == SignalColor.GREEN.value
                or states["South"] == SignalColor.GREEN.value
            )
            ew_green = (
                states["East"] == SignalColor.GREEN.value
                or states["West"] == SignalColor.GREEN.value
            )

            # Core invariant: NS and EW can NEVER be GREEN at the same time
            assert not (ns_green and ew_green), (
                f"Conflicting GREEN detected at cycle {cycle}, step {step}! States: {states}"
            )

            # Conflicting yellow invariant: yellow on one axis cannot co-exist with green on the other
            ns_yellow = (
                states["North"] == SignalColor.YELLOW.value
                or states["South"] == SignalColor.YELLOW.value
            )
            ew_yellow = (
                states["East"] == SignalColor.YELLOW.value
                or states["West"] == SignalColor.YELLOW.value
            )

            assert not (ns_yellow and ew_green), (
                f"Yellow on NS with Green on EW at cycle {cycle}, step {step}!"
            )
            assert not (ew_yellow and ns_green), (
                f"Yellow on EW with Green on NS at cycle {cycle}, step {step}!"
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

"""Dedicated test suite validating:
1. Only 1 signal is green at a time.
2. Default switching is clockwise unless there are more vehicles in another direction.
3. Fast switching (~1 second) when no vehicles in a green signaled direction while vehicles are waiting in other directions.
"""

import pytest
from simulation.controller import SimulationController
from simulation.phases import SignalColor, SignalPhaseController


def test_only_one_signal_green_at_any_time():
    """At any moment in the simulation, at most one signal is GREEN."""
    controller = SimulationController()
    controller.start("North")

    # Add traffic across all approaches
    for app in controller.APPROACHES:
        for _ in range(4):
            controller.add_vehicle(app)

    # Run for 200 ticks of 0.2s (40 seconds total)
    for _ in range(200):
        controller.step(0.2)
        states = controller.signal_states
        green_signals = [app for app, color in states.items() if color == SignalColor.GREEN.value]
        assert len(green_signals) <= 1, f"More than 1 green signal detected: {green_signals} in {states}"


def test_default_switching_is_clockwise():
    """When vehicle counts are equal or zero, switching strictly follows clockwise order."""
    controller = SimulationController()
    controller.start("North")

    # Order must be North -> East -> South -> West -> North
    assert controller.phase_controller.normalize_axis("North") == "North"

    # From North, clockwise default is East
    next_from_north = controller.select_next_axis()
    assert next_from_north == "East"

    # From East, clockwise default is South
    controller.phase_controller.start("East")
    next_from_east = controller.select_next_axis()
    assert next_from_east == "South"

    # From South, clockwise default is West
    controller.phase_controller.start("South")
    next_from_south = controller.select_next_axis()
    assert next_from_south == "West"

    # From West, clockwise default is North
    controller.phase_controller.start("West")
    next_from_west = controller.select_next_axis()
    assert next_from_west == "North"


def test_switching_diverts_from_clockwise_when_another_direction_has_more_vehicles():
    """If another direction has strictly more vehicles than clockwise default, it is selected."""
    controller = SimulationController()
    controller.start("North")

    # Clockwise default from North is East.
    # East has 1 vehicle, South has 5 vehicles, West has 2 vehicles.
    controller.add_vehicle("East")
    for _ in range(5):
        controller.add_vehicle("South")
    for _ in range(2):
        controller.add_vehicle("West")

    # South has 5 > 1 (East), so South MUST be selected
    chosen = controller.select_next_axis()
    assert chosen == "South"


def test_switching_stays_clockwise_when_counts_are_tied_with_default():
    """When clockwise default has equal count to another direction, clockwise takes precedence."""
    controller = SimulationController()
    controller.start("North")

    # East has 3, South has 3, West has 1
    for _ in range(3):
        controller.add_vehicle("East")
        controller.add_vehicle("South")
    controller.add_vehicle("West")

    # South does NOT have more than East (3 is not > 3), so default clockwise (East) is chosen
    chosen = controller.select_next_axis()
    assert chosen == "East"


def test_fast_switching_when_active_direction_has_no_vehicles():
    """When the active green direction has no vehicles, it switches to waiting directions in ~1 second."""
    controller = SimulationController()
    controller.start("North")

    # North has 0 vehicles. East has 4 vehicles waiting.
    for _ in range(4):
        controller.add_vehicle("East")

    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert controller.get_approach_queue_length("North") == 0
    assert not controller.is_in_clearance

    # Step 0.5s: less than 1 second, still green on North
    controller.step(0.5)
    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert not controller.is_in_clearance

    # Step another 0.6s (total 1.1s empty): around 1 second has elapsed -> triggers clearance switch!
    controller.step(0.6)
    assert controller.is_in_clearance is True
    assert controller.transition_state_name == "YELLOW"
    assert controller.phase_controller.pending_axis == "East"


def test_fast_switching_after_all_vehicles_in_green_direction_depart():
    """Once all queued vehicles cross, the signal switches to other waiting vehicles in ~1 second."""
    controller = SimulationController()
    controller.start("North")

    # North has 2 vehicles (clearing at 1.0s and 2.0s)
    controller.add_vehicle("North")
    controller.add_vehicle("North")

    # West has 3 vehicles waiting
    for _ in range(3):
        controller.add_vehicle("West")

    # First vehicle departs at 1.0s
    controller.step(1.0)
    assert controller.get_approach_queue_length("North") == 1
    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert not controller.is_in_clearance

    # Second vehicle departs at 2.0s (queue is now empty)
    controller.step(1.0)
    assert controller.get_approach_queue_length("North") == 0
    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert not controller.is_in_clearance

    # Step 0.5s into empty gap (queue empty for 0.5s): still green
    controller.step(0.5)
    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert not controller.is_in_clearance

    # Step another 0.6s (queue empty for 1.1s -> ~1 second threshold reached):
    # Triggers clearance switch to West (which has the waiting vehicles)!
    controller.step(0.6)
    assert controller.is_in_clearance is True
    assert controller.transition_state_name == "YELLOW"
    assert controller.phase_controller.pending_axis == "West"

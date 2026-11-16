"""Tests for 2-Lane per direction simulation, Random arrival mode, and safety invariants."""

import pytest

from simulation.controller import SimulationController
from simulation.phases import PhaseTransitionState, SignalColor
from simulation.vehicles.vehicle import Vehicle


def test_vehicle_tracks_lane_attribute():
    """Vehicle dataclass tracks lane (1-indexed) and lane_index (0-indexed)."""
    v1 = Vehicle(vehicle_id=1, lane=1)
    assert v1.lane == 1
    assert v1.lane_index == 0

    v2 = Vehicle(vehicle_id=2, lane=2)
    assert v2.lane == 2
    assert v2.lane_index == 1

    with pytest.raises(ValueError, match="lane must be a positive integer"):
        Vehicle(vehicle_id=3, lane=0)

    with pytest.raises(ValueError, match="lane must be a positive integer"):
        Vehicle(vehicle_id=4, lane=-1)


def test_dual_lane_simultaneous_dispatch():
    """When an approach is green, vehicles from BOTH lanes depart simultaneously."""
    controller = SimulationController()
    controller.start("NS")  # North is GREEN

    # Enqueue 3 vehicles in North Lane 1, and 3 vehicles in North Lane 2
    for _ in range(3):
        controller.add_vehicle("North", vehicle_type="normal", lane=1)
        controller.add_vehicle("North", vehicle_type="normal", lane=2)

    assert controller.get_lane_queue_length("North", 0) == 3
    assert controller.get_lane_queue_length("North", 1) == 3
    assert controller.get_approach_queue_length("North") == 6

    # Tick 1 movement interval (1.0s): 1 vehicle from Lane 1 and 1 vehicle from Lane 2 depart
    controller.step(1.0)
    assert controller.get_lane_queue_length("North", 0) == 2
    assert controller.get_lane_queue_length("North", 1) == 2
    assert controller.get_approach_queue_length("North") == 4
    assert controller.statistics.total_processed == 2

    # Tick 2 movement interval (1.0s): next vehicle from each lane departs
    controller.step(1.0)
    assert controller.get_lane_queue_length("North", 0) == 1
    assert controller.get_lane_queue_length("North", 1) == 1
    assert controller.get_approach_queue_length("North") == 2
    assert controller.statistics.total_processed == 4

    # Tick 3 movement interval (1.0s): final vehicles depart
    controller.step(1.0)
    assert controller.get_lane_queue_length("North", 0) == 0
    assert controller.get_lane_queue_length("North", 1) == 0
    assert controller.get_approach_queue_length("North") == 0
    assert controller.statistics.total_processed == 6


def test_random_generation_distribution_across_lanes():
    """Simulate 100 ticks in Random mode and assert vehicles distribute across multiple lanes."""
    controller = SimulationController()
    controller.arrival_interval = 0.1
    controller.arrival_generator.emergency_probability = 0.15
    controller.start("NS")
    controller.arrival_mode = "Random"

    for _ in range(100):
        controller.step(0.1)

    # Across 100 random additions across 8 lanes (4 approaches * 2 lanes),
    # verify both Lane 1 and Lane 2 receive vehicles
    lane1_total = sum(
        controller.get_lane_queue_length(app, 0)
        for app in controller.APPROACHES
    )
    lane2_total = sum(
        controller.get_lane_queue_length(app, 1)
        for app in controller.APPROACHES
    )
    total_processed = controller.statistics.total_processed

    # Total vehicles generated is 100
    total_vehicles = lane1_total + lane2_total + total_processed
    assert total_vehicles == 100
    assert lane1_total > 0, "Lane 1 should have received vehicles"
    assert lane2_total > 0, "Lane 2 should have received vehicles"

    # Multiple approaches should have non-empty queues
    approaches_with_vehicles = [
        app for app in controller.APPROACHES
        if controller.get_approach_queue_length(app) > 0
    ]
    assert len(approaches_with_vehicles) >= 2


def test_emergency_preemption_from_lane_2():
    """An emergency vehicle in Lane 2 of a RED approach triggers preemption."""
    controller = SimulationController()
    controller.start("NS")

    # Add normal vehicles to North (active axis)
    for _ in range(5):
        controller.add_vehicle("North", vehicle_type="normal", lane=1)
        controller.add_vehicle("North", vehicle_type="normal", lane=2)

    # Force emergency vehicle specifically in East Lane 2 (crossing axis)
    ev = controller.add_vehicle("East", vehicle_type="emergency", lane=2)
    assert ev.lane == 2
    assert ev.lane_index == 1
    assert controller.get_lane_queue_length("East", 0) == 0
    assert controller.get_lane_queue_length("East", 1) == 1
    assert controller.is_emergency_active() is True
    assert controller.get_emergency_approaches() == ["East"]

    # Step through MIN_GREEN (10.0s): North remains green until MIN_GREEN expires
    controller.step(10.0)
    assert controller.is_in_clearance is True
    assert controller.transition_state_name == "YELLOW"
    assert controller.phase_controller.pending_axis in ("East", "EW")

    # Step through YELLOW (1.0s) and ALL_RED (1.0s)
    controller.step(1.0)
    assert controller.transition_state_name == "ALL_RED"
    controller.step(1.0)

    # East is now GREEN
    assert controller.active_axis in ("East", "EW")
    assert controller.signal_states["East"] == SignalColor.GREEN.value
    assert controller.signal_states["North"] == SignalColor.RED.value

    # On next movement tick, the emergency vehicle from East Lane 2 departs
    controller.step(1.0)
    assert controller.get_lane_queue_length("East", 1) == 0


def test_gap_out_resets_when_vehicle_crosses_either_lane():
    """The gap-out timer resets if a vehicle crosses from EITHER lane of an active approach."""
    controller = SimulationController()
    controller.start("NS")

    # North Lane 1 has 1 vehicle, North Lane 2 has 3 vehicles
    controller.add_vehicle("North", "normal", lane=1)
    controller.add_vehicle("North", "normal", lane=2)
    controller.add_vehicle("North", "normal", lane=2)
    controller.add_vehicle("North", "normal", lane=2)

    # Conflicting demand on East
    controller.add_vehicle("East", "normal", lane=1)

    # Meet MIN_GREEN (10.0s)
    controller.step(10.0)
    # At this point, vehicles have been crossing and Lane 2 still has vehicles
    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert not controller.is_in_clearance

    # Wait until Lane 2 also finishes emptying
    while controller.get_approach_queue_length("North") > 0:
        controller.step(1.0)
        assert controller.signal_states["North"] == SignalColor.GREEN.value

    # Queue is now empty on North across both lanes.
    # 1.0s gap period: 1.0s into gap -> gap-out triggers clearance in ~1 second
    controller.step(1.0)
    assert controller.is_in_clearance is True
    assert controller.phase_controller.pending_axis in ("East", "EW")


def test_nema_phase_invariant_dual_lane_5000_ticks():
    """Mathematical verification: 5,000 ticks with dual-lane traffic never emit conflicting green signals."""
    controller = SimulationController()
    controller.arrival_generator.emergency_probability = 0.20
    controller.arrival_mode = "Random"
    controller.start("NS")

    for tick in range(5000):
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

        # 1. No conflicting GREEN: NS and EW can NEVER be GREEN at the same time
        assert not (ns_green and ew_green), f"Conflicting GREEN at tick {tick}! {states}"

        # 2. No conflicting YELLOW with opposite GREEN
        ns_yellow = (
            states["North"] == SignalColor.YELLOW.value
            or states["South"] == SignalColor.YELLOW.value
        )
        ew_yellow = (
            states["East"] == SignalColor.YELLOW.value
            or states["West"] == SignalColor.YELLOW.value
        )
        assert not (ns_yellow and ew_green), f"NS Yellow with EW Green at tick {tick}!"
        assert not (ew_yellow and ns_green), f"EW Yellow with NS Green at tick {tick}!"

        # 3. In ALL_RED clearance, all approaches must be RED
        if controller.transition_state_name == "ALL_RED":
            assert all(
                c == SignalColor.RED.value for c in states.values()
            ), f"Non-red signal during ALL_RED at tick {tick}: {states}"


def test_random_mode_throttled_and_stabilized_1000_ticks():
    """Regression test: 1,000 ticks in Random mode stabilizes queue, respects hard cap, and processes departures."""
    controller = SimulationController(arrival_interval=2.0, max_queue_size=50)
    controller.arrival_mode = "Random"
    controller.arrival_generator.emergency_probability = 0.10
    controller.start("NS")

    max_waiting_observed = 0

    for tick in range(1000):
        controller.step(0.1)

        total_waiting = sum(
            controller.get_approach_queue_length(app)
            for app in controller.APPROACHES
        )
        max_waiting_observed = max(max_waiting_observed, total_waiting)

        # 1. Total waiting vehicles must NEVER exceed capacity (100 vehicles across all lanes)
        assert total_waiting <= 100, f"Queue exploded to {total_waiting} at tick {tick}!"

        # 2. Individual lanes must never exceed max_queue_size (50 vehicles)
        for app in controller.APPROACHES:
            for lane_idx in (0, 1):
                assert (
                    controller.get_lane_queue_length(app, lane_idx) <= controller.max_queue_size
                )

    # 3. Vehicles must successfully depart during green phases (Total Processed > 0)
    assert controller.statistics.total_processed > 0
    # Over 100s with 2.0s interval, ~50 vehicles arrived; most must have been dispatched
    assert controller.statistics.total_processed >= 25

    # 4. Final queue is stabilized and within a tight operational bound (not runaway)
    final_waiting = sum(
        controller.get_approach_queue_length(app)
        for app in controller.APPROACHES
    )
    assert final_waiting < 30
    assert max_waiting_observed < 50


def test_state_awareness_no_arrivals_when_paused_or_stopped():
    """Arrival generator MUST ONLY run when SimulationState is RUNNING."""
    controller = SimulationController(arrival_interval=0.2)
    controller.arrival_mode = "Random"

    # 1. When STOPPED: zero arrivals spawn
    assert controller.state.value == "stopped"
    for _ in range(50):
        controller.step(0.1)
    assert sum(controller.get_approach_queue_length(app) for app in controller.APPROACHES) == 0

    # 2. When PAUSED: zero arrivals spawn
    controller.start("NS")
    controller.pause()
    assert controller.state.value == "paused"
    for _ in range(50):
        controller.step(0.1)
    assert sum(controller.get_approach_queue_length(app) for app in controller.APPROACHES) == 0

    # 3. When RESUMED: arrivals resume
    controller.resume()
    assert controller.state.value == "running"
    for _ in range(10):
        controller.step(0.1)
    # With 0.2s arrival interval, at least 1 vehicle should spawn over 1.0s (10 ticks)
    assert (
        sum(controller.get_approach_queue_length(app) for app in controller.APPROACHES)
        + controller.statistics.total_processed
    ) > 0


def test_lane_max_queue_size_hard_cap():
    """Enforce MAX_QUEUE_SIZE hard cap: a full lane rejects new vehicle arrivals."""
    controller = SimulationController(max_queue_size=5)

    # Fill North Lane 1 to capacity (5 vehicles)
    for _ in range(5):
        v = controller.add_vehicle("North", lane=1)
        assert v is not None
    assert controller.get_lane_queue_length("North", 0) == 5

    # 6th attempt to North Lane 1 must be rejected (returns None, queue unchanged)
    overflow_v = controller.add_vehicle("North", lane=1)
    assert overflow_v is None
    assert controller.get_lane_queue_length("North", 0) == 5

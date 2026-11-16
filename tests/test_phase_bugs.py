"""Unit tests reproducing and verifying Phase 7 simulation logic fixes.

Bug 1: Premature Phase Termination (Signal cuts to RED while queue is active).
Bug 2: Emergency Preemption Overridden by Normal Demand.
"""

import pytest

from simulation.controller import SimulationController
from simulation.phases import PhaseTransitionState, SignalColor
from simulation.traffic.demand_monitor import DemandMonitor
from simulation.traffic.lane_queue import LaneQueue
from simulation.vehicles.vehicle import Vehicle


def test_bug1_queue_clearance_extends_green_until_queue_clear():
    """Test A: Active queue of 12 vehicles; signal must not turn red until queue clears + gap-out.

    Movement interval is 1.0s and MIN_GREEN is 10.0s. With 12 vehicles, the
    signal extends past MIN_GREEN and must remain GREEN while vehicles are waiting,
    then gap out after GAP_OUT_TIME (2.0s) of empty queue.
    """
    controller = SimulationController()
    controller.start()  # Starts with active_axis="NS", North is GREEN

    # Active approach North has 12 vehicles (> MIN_GREEN of 10s)
    for _ in range(12):
        controller.add_vehicle("North", "normal")

    # Crossing approach East has vehicles waiting to create conflicting demand
    controller.add_vehicle("East", "normal")
    controller.add_vehicle("East", "normal")

    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert controller.get_approach_queue_length("North") == 12

    # Step 1..11: 1 vehicle departs each second, at least 1 vehicle still waiting
    for expected_remaining in range(11, 0, -1):
        controller.step(1.0)
        assert controller.get_approach_queue_length("North") == expected_remaining
        assert controller.signal_states["North"] == SignalColor.GREEN.value
        assert not controller.is_in_clearance

    # Step 12: 12th vehicle departs, queue is now clear (0 waiting)
    controller.step(1.0)
    assert controller.get_approach_queue_length("North") == 0
    assert controller.signal_states["North"] == SignalColor.GREEN.value
    assert not controller.is_in_clearance

    # Gap period is ~1.0s: after 1.0s of empty queue with vehicles waiting, it gaps out to serve East
    controller.step(1.0)  # 1.0s into gap -> initiates clearance switch in ~1 second
    assert controller.is_in_clearance
    assert controller.phase_controller.pending_axis in ("East", "EW")


def test_bug1_queue_clearance_respects_absolute_maximum_green():
    """Test A (extension): Huge queue must terminate at MAX_GREEN (60.0s)."""
    controller = SimulationController()
    controller.start()  # NS green

    # Add 80 vehicles to North (exceeds 60s max green)
    for _ in range(80):
        controller.add_vehicle("North", "normal")

    # Add vehicles to East to create cross demand
    controller.add_vehicle("East", "normal")

    # Advance simulation for 59 seconds (59 steps of 1.0s): stays GREEN
    for _ in range(59):
        controller.step(1.0)
        assert controller.signal_states["North"] == SignalColor.GREEN.value
        assert not controller.is_in_clearance

    # At 60.0s, MAX_GREEN limit is reached -> must transition to clearance
    controller.step(1.0)
    assert controller.is_in_clearance or controller.signal_states["North"] != SignalColor.GREEN.value


def test_bug2_emergency_preemption_overrides_high_normal_demand():
    """Test B: North has 12 normal vehicles; West has 3 emergency + 14 normal vehicles.

    Emergency vehicles must have absolute priority over normal demand once
    MIN_GREEN (10.0s) is met, transitioning safely via YELLOW -> ALL_RED -> EW GREEN.
    """
    controller = SimulationController()
    controller.start("NS")  # North is GREEN

    # North approach has 12 normal vehicles
    for _ in range(12):
        controller.add_vehicle("North", vehicle_type="normal")

    # West approach has 3 emergency vehicles at the front and 14 normal vehicles
    for _ in range(3):
        controller.add_vehicle("West", vehicle_type="emergency", is_emergency=True)
    for _ in range(14):
        controller.add_vehicle("West", vehicle_type="normal")

    # Verify queue setup
    assert controller.get_approach_queue_length("North") == 12
    assert controller.get_approach_queue_length("West") == 17

    # Phase selection MUST prioritize the approach containing emergency vehicles
    next_axis = controller.select_next_axis()
    assert next_axis in ("West", "EW")

    # Before MIN_GREEN (10.0s), North remains GREEN safely
    controller.step(9.0)
    assert controller.is_in_clearance is False
    assert controller.signal_states["North"] == SignalColor.GREEN.value

    # Once MIN_GREEN (10.0s) is reached, controller MUST immediately preempt to West via YELLOW
    controller.step(1.0)
    assert controller.is_in_clearance is True
    assert controller.phase_controller.pending_axis in ("West", "EW")
    assert controller.signal_states["North"] == SignalColor.YELLOW.value
    assert controller.signal_states["West"] == SignalColor.RED.value

    # Complete yellow clearance (1.0s) + all-red clearance (1.0s)
    controller.step(1.0)  # enters all-red
    assert controller.transition_state_name == "ALL_RED"
    controller.step(1.0)  # clearance finishes

    # West is now GREEN!
    assert controller.active_axis in ("West", "EW")
    assert controller.signal_states["West"] == SignalColor.GREEN.value
    assert controller.signal_states["North"] == SignalColor.RED.value


def test_it_17_emergency_vehicle_priority_over_normal_traffic():
    """IT_17: Normal vehicles (5) + Emergency vehicle (1) -> emergency gets priority safely."""
    controller = SimulationController()
    controller.start("NS")

    for _ in range(5):
        controller.add_vehicle("North", vehicle_type="normal")
    controller.add_vehicle("East", vehicle_type="emergency", is_emergency=True)

    # Meet MIN_GREEN (10.0s), then complete clearance (1.0s YELLOW + 1.0s ALL_RED)
    controller.step(10.0)
    assert controller.transition_state_name == "YELLOW"
    assert controller.phase_controller.pending_axis in ("East", "EW")

    controller.step(1.0)
    assert controller.transition_state_name == "ALL_RED"
    controller.step(1.0)

    assert controller.active_axis in ("East", "EW")
    assert controller.signal_states["East"] == SignalColor.GREEN.value
    assert controller.signal_states["North"] == SignalColor.RED.value

    # Emergency vehicle departs on next 1.0s movement interval
    controller.step(1.0)
    assert controller.get_approach_queue_length("East") == 0


def test_st_18_emergency_preemption_safe_under_conflicting_traffic():
    """ST_18: Conflicting traffic + emergency vehicle transitions safely without conflict."""
    controller = SimulationController()
    controller.start("NS")

    # Populate heavy conflicting normal traffic on NS and normal + emergency on EW
    for _ in range(15):
        controller.add_vehicle("North", vehicle_type="normal")
        controller.add_vehicle("South", vehicle_type="normal")
    controller.add_vehicle("East", vehicle_type="emergency", is_emergency=True)

    # Step in 0.5s increments and verify no conflicting GREEN/YELLOW ever occurs
    seen_yellow = False
    seen_all_red = False
    switched_to_ew = False

    for _ in range(30):  # 15.0s total
        controller.step(0.5)
        states = controller.signal_states
        ns_green = states["North"] == "GREEN" or states["South"] == "GREEN"
        ew_green = states["East"] == "GREEN" or states["West"] == "GREEN"
        assert not (ns_green and ew_green)

        if controller.transition_state_name == "YELLOW":
            seen_yellow = True
            assert not ew_green
        if controller.transition_state_name == "ALL_RED":
            seen_all_red = True
            assert all(color == "RED" for color in states.values())
        if controller.active_axis in ("East", "EW") and ew_green:
            switched_to_ew = True
            break

    assert seen_yellow is True
    assert seen_all_red is True
    assert switched_to_ew is True


def test_bug2_emergency_preemption_when_added_before_start():
    """Emergency vehicles queued while stopped must win initial green over higher normal demand."""
    controller = SimulationController()

    # Add 15 normal vehicles to North
    for _ in range(15):
        controller.add_vehicle("North", "normal")

    # Add 1 emergency vehicle to West
    controller.add_vehicle("West", "emergency", is_emergency=True)

    # Controller starts without explicit initial_axis -> must select West (EW)
    controller.start()
    assert controller.active_axis in ("West", "EW")
    assert controller.signal_states["West"] == SignalColor.GREEN.value
    assert controller.signal_states["North"] == SignalColor.RED.value


def test_bug2_vehicle_is_emergency_flag_support():
    """Vehicle class supports is_emergency constructor argument and attribute."""
    v1 = Vehicle(vehicle_id=1, is_emergency=True)
    assert v1.is_emergency is True
    assert v1.vehicle_type == "emergency"

    v2 = Vehicle(vehicle_id=2, vehicle_type="emergency")
    assert v2.is_emergency is True

    v3 = Vehicle(vehicle_id=3, vehicle_type="normal")
    assert v3.is_emergency is False

    v3.is_emergency = True
    assert v3.is_emergency is True


def test_bug2_demand_monitor_measures_emergency_counts():
    """DemandMonitor detects and reports emergency vehicles in its measurements."""
    north_queue = LaneQueue[Vehicle]()
    north_queue.enqueue(Vehicle(vehicle_id=1, vehicle_type="normal"))
    north_queue.enqueue(Vehicle(vehicle_id=2, is_emergency=True))

    monitor = DemandMonitor()
    results = monitor.measure({"North": [north_queue]})

    assert results["North"].waiting_vehicle_count == 2
    assert results["North"].emergency_vehicle_count == 1
    assert results["North"].has_emergency is True

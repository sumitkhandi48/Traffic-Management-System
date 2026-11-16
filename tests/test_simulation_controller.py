"""Tests for the unified SimulationController."""

import pytest

from simulation.controller import SimulationController
from simulation.engine import SimulationState


def test_controller_initial_and_reset_state():
    """Controller initializes in stopped state and resets cleanly."""
    controller = SimulationController()
    assert controller.state == SimulationState.STOPPED
    assert controller.simulation_time == 0.0

    controller.start()
    controller.add_vehicle("North")
    assert controller.get_approach_queue_length("North") == 1

    # Movement interval is 1.0s, so vehicle has not departed at 0.5s:
    controller.step(0.5)
    assert controller.simulation_time == 0.5
    assert controller.get_approach_queue_length("North") == 1

    controller.reset()
    assert controller.state == SimulationState.STOPPED
    assert controller.simulation_time == 0.0
    assert controller.get_approach_queue_length("North") == 0


def test_emergency_preemption_schedules_safe_transition():
    """Emergency vehicle on cross axis triggers safe clearance once MIN_GREEN is met."""
    controller = SimulationController()
    controller.start()

    # Active axis is NS
    assert controller.active_axis == "NS"
    assert controller.signal_states["North"] == "GREEN"

    # Add emergency vehicle to East (cross axis)
    controller.add_vehicle("East", vehicle_type="emergency")

    # Respect MIN_GREEN (10.0s): NS remains GREEN until MIN_GREEN elapses
    controller.step(9.0)
    assert controller.is_in_clearance is False
    assert controller.signal_states["North"] == "GREEN"
    assert controller.signal_states["East"] == "RED"

    # Reaching MIN_GREEN (10.0s) immediately initiates YELLOW clearance
    controller.step(1.0)
    assert controller.is_in_clearance is True
    assert controller.transition_state_name == "YELLOW"
    assert controller.signal_states["North"] == "YELLOW"
    assert controller.signal_states["East"] == "RED"

    # Advance 1.0s: enters ALL_RED
    controller.step(1.0)
    assert controller.transition_state_name == "ALL_RED"
    assert controller.signal_states["North"] == "RED"
    assert controller.signal_states["East"] == "RED"

    # Advance 1.0s: clearance finishes, East-West is now GREEN
    controller.step(1.0)
    assert controller.is_in_clearance is False
    assert controller.active_axis == "EW"
    assert controller.signal_states["East"] == "GREEN"


def test_emergency_vehicle_respects_single_lane_fifo():
    """Emergency vehicles must NOT teleport; physical single-lane FIFO is strictly preserved."""
    controller = SimulationController()
    controller.start()

    # Add a normal vehicle first, then an emergency vehicle second to North approach
    normal_v = controller.add_vehicle("North", vehicle_type="normal")
    emergency_v = controller.add_vehicle("North", vehicle_type="emergency")

    queue = controller.get_approach_vehicles("North")
    assert len(queue) == 2
    assert queue[0].vehicle_id == normal_v.vehicle_id
    assert queue[1].vehicle_id == emergency_v.vehicle_id

    # Advance simulation time until 1 vehicle departs (movement interval = 1.0s)
    # The normal vehicle at the head of the queue MUST depart first
    controller.step(1.0)
    remaining_queue = controller.get_approach_vehicles("North")
    assert len(remaining_queue) == 1
    assert remaining_queue[0].vehicle_id == emergency_v.vehicle_id

    # The emergency vehicle is now at the front and departs on the next movement tick
    controller.step(1.0)
    final_queue = controller.get_approach_vehicles("North")
    assert len(final_queue) == 0
    assert controller.statistics.total_processed == 2


def test_cumulative_statistics_survive_queue_discharge():
    """Historical averages and totals must not vanish when queues empty."""
    controller = SimulationController()
    controller.start()

    # Enqueue 3 vehicles at North
    for _ in range(3):
        controller.add_vehicle("North")

    # Initial peak queue should record 3
    assert controller.statistics.peak_queue_length_ever == 3

    # Advance time while they wait and discharge (movement interval = 1.0s)
    controller.step(1.0)
    controller.step(1.0)
    controller.step(1.0)

    # Queues are now completely empty
    summary = controller.get_summary_statistics()
    assert summary["total_waiting_vehicles"] == 0
    assert summary["average_waiting_time_current"] == 0.0

    # CUMULATIVE metrics must survive queue discharge:
    assert summary["vehicles_processed_cumulative"] == 3
    assert summary["average_waiting_time_cumulative"] > 0.0
    assert summary["maximum_queue_length_cumulative"] == 3
    assert summary["busiest_approach_overall"] == "North"


def test_starvation_prevention_weighted_waiting_time():
    """Minor approach with high waiting time must beat a busier recently-served approach."""
    controller = SimulationController()
    controller.start()

    # North (major approach) has 5 vehicles that just arrived (wait time = 0.5s)
    for _ in range(5):
        v = controller.add_vehicle("North")
        v.waiting_time = 0.5

    # East (minor approach) has only 2 vehicles, but they have been waiting 100s
    for _ in range(2):
        v = controller.add_vehicle("East")
        v.waiting_time = 100.0

    # Demand score comparison:
    # North: 5 + 0.1 * (5 * 0.5) = 5.25
    # East:  2 + 0.1 * (2 * 100.0) = 22.0
    # East-West MUST be selected next to prevent starvation
    chosen_axis = controller.select_next_axis()
    assert chosen_axis == "EW"

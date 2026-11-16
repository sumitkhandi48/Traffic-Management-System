"""End-to-end smoke test for the Traffic Management System."""

import time
import tkinter as tk
import pytest

from simulation.controller import SimulationController
from simulation.engine import SimulationState
from simulation.phases import SignalColor
from ui.traffic_dashboard import TrafficDashboard


def test_e2e_traffic_dashboard_smoke(session_tk_root):
    """Launch dashboard against real controller, tick N times with load, and assert on TrafficStatistics."""
    if session_tk_root is None:
        pytest.skip("A graphical display is required for Tkinter smoke test.")

    window = tk.Toplevel(session_tk_root)
    window.withdraw()

    controller = SimulationController()
    dashboard = TrafficDashboard(window, controller=controller)

    # Cancel automatic tick job so the test drives deterministic clock advances
    if hasattr(dashboard, "_tick_job") and dashboard._tick_job is not None:
        try:
            window.after_cancel(dashboard._tick_job)
        except tk.TclError:
            pass
        dashboard._tick_job = None

    try:
        # 1. Start simulation through UI command
        dashboard.start_simulation()
        assert dashboard.engine.state == SimulationState.RUNNING

        # 2. Add vehicle load across multiple approaches using UI controls
        # North: 1 normal, 1 emergency
        dashboard.approach_selector.set("North")
        dashboard.vehicle_type_selector.set("Normal")
        dashboard.add_vehicle()

        dashboard.approach_selector.set("North")
        dashboard.vehicle_type_selector.set("Emergency")
        dashboard.add_vehicle()

        # East: 2 normal vehicles
        dashboard.approach_selector.set("East")
        dashboard.vehicle_type_selector.set("Normal")
        dashboard.add_vehicle()
        dashboard.add_vehicle()

        # South: 1 normal vehicle
        dashboard.approach_selector.set("South")
        dashboard.vehicle_type_selector.set("Normal")
        dashboard.add_vehicle()

        # Verify initial queues in domain controller
        initial_total = sum(
            len(dashboard.controller.get_approach_vehicles(app))
            for app in dashboard.APPROACHES
        )
        assert initial_total == 5

        # 3. Drive simulation forward with 35 ticks of 0.2s (= 7.0s simulated time)
        num_ticks = 35
        tick_delta = 0.2
        for _ in range(num_ticks):
            dashboard._last_tick_time = time.monotonic() - tick_delta
            dashboard._tick()

        # 4. Assert on domain TrafficStatistics
        stats = dashboard.controller.statistics.get_cumulative_statistics()
        base_stats = dashboard.controller.statistics.get_statistics()

        assert stats["total_processed"] > 0
        assert stats["peak_queue_length_ever"] >= 2
        assert stats["average_wait_all_time"] > 0.0
        assert base_stats["maximum_waiting_time"] > 0.0

        # 5. Assert on UI observer display widgets
        assert "Simulation time:" in dashboard.time_label.cget("text")
        assert "Total waiting vehicles:" in dashboard.total_vehicles_label.cget("text")
        assert "Average waiting time:" in dashboard.average_wait_label.cget("text")
        assert "0.00 s" not in dashboard.average_wait_label.cget("text")
        assert "Maximum queue length:" in dashboard.max_queue_label.cget("text")
        assert "Simulation status: RUNNING" in dashboard.status_label.cget("text")

        # Invariant: Conflicting green state is never emitted
        signal_states = dashboard.controller.signal_states
        green_axes = [
            axis
            for axis, approaches in [
                ("NS", ("North", "South")),
                ("EW", ("East", "West")),
            ]
            if any(signal_states[a] == SignalColor.GREEN.value for a in approaches)
        ]
        assert len(green_axes) <= 1

        # 6. Verify pause, resume, and stop controls
        dashboard.pause_simulation()
        assert dashboard.engine.state == SimulationState.PAUSED

        dashboard.resume_simulation()
        assert dashboard.engine.state == SimulationState.RUNNING

        dashboard.stop_simulation()
        assert dashboard.engine.state == SimulationState.STOPPED

    finally:
        dashboard._on_close()


def test_e2e_controller_headless_smoke():
    """Headless end-to-end smoke test driving controller pipeline without graphical window."""
    controller = SimulationController()
    assert controller.start()

    controller.add_vehicle("North", "normal")
    controller.add_vehicle("North", "emergency")
    controller.add_vehicle("East", "normal")
    controller.add_vehicle("South", "normal")

    # Advance 30 steps of 0.2s (= 6.0s simulated time)
    for _ in range(30):
        controller.step(0.2)

    stats = controller.statistics.get_cumulative_statistics()
    assert stats["total_processed"] > 0
    assert stats["peak_queue_length_ever"] >= 2
    assert stats["average_wait_all_time"] > 0.0

    summary = controller.get_summary_statistics()
    assert summary["simulation_state"] == "RUNNING"
    assert summary["simulation_time"] >= 5.0
    assert summary["vehicles_processed_cumulative"] == stats["total_processed"]

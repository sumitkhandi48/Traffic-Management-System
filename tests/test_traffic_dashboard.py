"""Tests for the traffic dashboard."""

from unittest.mock import Mock

import pytest

from auth import UserSession
from simulation.controller import SimulationController
from simulation.vehicles.vehicle import Vehicle
from ui.traffic_dashboard import TrafficDashboard, VehicleQueuesProxy


@pytest.fixture
def dashboard(session_tk_root):
    """Create a dashboard instance on a Toplevel window for testing."""
    if session_tk_root is None:
        pytest.skip("A graphical display is required for Tkinter tests.")
    import tkinter as tk
    window = tk.Toplevel(session_tk_root)
    window.withdraw()
    app = TrafficDashboard(window)
    yield app
    app._on_close()


def test_dashboard_initial_state(dashboard):
    """The dashboard starts with empty queues and a stopped engine."""
    assert dashboard.engine.state.value == "stopped"

    for approach in dashboard.APPROACHES:
        assert dashboard.vehicle_queues[approach] == []
        assert dashboard.signal_states[approach] == "RED"


def test_add_vehicle_updates_queue(dashboard):
    """Adding a vehicle creates one entry in a queue."""
    dashboard.add_vehicle()

    total = sum(
        len(dashboard.vehicle_queues[approach])
        for approach in dashboard.APPROACHES
    )

    assert total == 1


def test_add_vehicle_updates_statistics(dashboard):
    """The total waiting-vehicle statistic matches the queues."""
    dashboard.add_vehicle()
    dashboard.add_vehicle()
    dashboard._refresh_display()

    assert dashboard.total_vehicles_label.cget("text") == (
        "Total waiting vehicles: 2"
    )


def test_reset_clears_queues_and_waiting_times(dashboard):
    """Reset clears vehicles and their waiting-time records."""
    dashboard.add_vehicle()
    dashboard.add_vehicle()
    dashboard.reset_simulation()

    for approach in dashboard.APPROACHES:
        assert dashboard.vehicle_queues[approach] == []
        assert dashboard.vehicle_waiting_times[approach] == {}

    assert dashboard.engine.state.value == "stopped"
    assert dashboard.total_vehicles_label.cget("text") == (
        "Total waiting vehicles: 0"
    )


# NFR-02: Control responsiveness regression tests.

CONTROL_ACTIONS = [
    ("start_simulation", "start"),
    ("pause_simulation", "pause"),
    ("resume_simulation", "resume"),
    ("stop_simulation", "stop"),
]


def make_dashboard_for_control_test():
    """Create a dashboard instance without opening a Tkinter window."""
    app = TrafficDashboard.__new__(TrafficDashboard)

    app.engine = Mock()
    app._refresh_display = Mock()

    # Attributes used by start_simulation().
    app._phase_elapsed = 1.5
    app._movement_elapsed = 0.5
    app._choose_next_phase = Mock()

    return app


@pytest.mark.parametrize(
    ("dashboard_method", "engine_method"),
    CONTROL_ACTIONS,
)
def test_control_action_refreshes_after_success(
    dashboard_method,
    engine_method,
):
    """A successful control action refreshes the display once."""
    app = make_dashboard_for_control_test()
    getattr(app.engine, engine_method).return_value = True

    getattr(app, dashboard_method)()

    app._refresh_display.assert_called_once()

    if dashboard_method == "start_simulation":
        assert app._phase_elapsed == 0.0
        assert app._movement_elapsed == 0.0
        app._choose_next_phase.assert_called_once()


@pytest.mark.parametrize(
    ("dashboard_method", "engine_method"),
    CONTROL_ACTIONS,
)
def test_control_action_does_not_refresh_after_rejection(
    dashboard_method,
    engine_method,
):
    """A rejected control action avoids an unnecessary UI refresh."""
    app = make_dashboard_for_control_test()
    getattr(app.engine, engine_method).return_value = False

    getattr(app, dashboard_method)()

    app._refresh_display.assert_not_called()

    if dashboard_method == "start_simulation":
        assert app._phase_elapsed == 1.5
        assert app._movement_elapsed == 0.5
        app._choose_next_phase.assert_not_called()

def test_start_action_avoids_unnecessary_refresh_work():
    """Start resets timing and chooses a phase before refreshing once."""
    app = make_dashboard_for_control_test()
    app.engine.start.return_value = True

    app.start_simulation()

    assert app._phase_elapsed == 0.0
    assert app._movement_elapsed == 0.0
    app._choose_next_phase.assert_called_once()
    app._refresh_display.assert_called_once()


def make_dashboard_for_emergency_test():
    """Create a dashboard backed by a real SimulationController for integration tests."""
    app = TrafficDashboard.__new__(TrafficDashboard)
    app.APPROACHES = ("North", "South", "East", "West")
    app.MAX_DISPLAYED_VEHICLES = 3
    app.controller = SimulationController()
    app._emergency_vehicles_set = set()
    app._vehicle_queues_proxy = VehicleQueuesProxy(app)
    app.vehicle_waiting_times = {
        approach: {} for approach in app.APPROACHES
    }
    app.signal_labels = {approach: Mock() for approach in app.APPROACHES}
    app.queue_labels = {approach: Mock() for approach in app.APPROACHES}
    app.demand_labels = {approach: Mock() for approach in app.APPROACHES}
    app.congestion_labels = {approach: Mock() for approach in app.APPROACHES}
    app.vehicle_listboxes = {approach: Mock() for approach in app.APPROACHES}
    app.emergency_status_label = Mock()
    app.total_vehicles_label = Mock()
    app.approach_label = Mock()
    app.average_wait_label = Mock()
    app.max_queue_label = Mock()
    app.state_label = Mock()
    app.status_label = Mock()
    app.time_label = Mock()
    return app


def test_emergency_vehicle_moves_with_fifo_order_not_teleportation():
    """Single-lane FIFO order is preserved: normal vehicle in front moves before emergency vehicle."""
    app = make_dashboard_for_emergency_test()
    app.controller.start()

    # Add normal vehicle first, then emergency vehicle behind it
    v1 = app.controller.add_vehicle("North", "normal")
    v2 = app.controller.add_vehicle("North", "emergency")

    north_vehicles = app.controller.get_approach_vehicles("North")
    assert [v.vehicle_id for v in north_vehicles] == [v1.vehicle_id, v2.vehicle_id]

    # Advance 1 movement interval (1.0s)
    app.controller.step(1.0)

    # Lead normal vehicle departed; emergency vehicle is now at front of queue
    north_vehicles_after = app.controller.get_approach_vehicles("North")
    assert len(north_vehicles_after) == 1
    assert north_vehicles_after[0].vehicle_id == v2.vehicle_id

    # Next movement interval: emergency vehicle departs
    app.controller.step(1.0)
    assert len(app.controller.get_approach_vehicles("North")) == 0


def test_emergency_vehicle_does_not_move_on_red_signal():
    """An emergency vehicle must wait while its signal is red."""
    app = make_dashboard_for_emergency_test()
    app.controller.start()

    # Add emergency vehicle on East (EW is RED)
    v_emergency = app.controller.add_vehicle("East", "emergency")
    assert app.signal_states["East"] == "RED"

    # Step less than clearance duration (0.5s): East remains RED and vehicle does not move
    app.controller.step(0.5)
    assert app.signal_states["East"] in ("RED", "YELLOW")
    east_vehicles = app.controller.get_approach_vehicles("East")
    assert len(east_vehicles) == 1
    assert east_vehicles[0].vehicle_id == v_emergency.vehicle_id


def test_emergency_priority_selects_correct_axis():
    """An emergency vehicle triggers transition to its approach once MIN_GREEN is met when active approach has traffic."""
    app = make_dashboard_for_emergency_test()
    app.controller.start()

    # Active traffic on North
    for _ in range(15):
        app.controller.add_vehicle("North", "normal")

    # Emergency vehicle arrives on East
    app.controller.add_vehicle("East", "emergency")

    # Step through MIN_GREEN (10.0s), then complete yellow (1.0s) + all-red (1.0s) clearance
    app.controller.step(5.0)
    assert not app.controller.phase_controller.is_in_clearance
    app.controller.step(5.0)  # reaches MIN_GREEN -> initiates YELLOW
    assert app.controller.phase_controller.is_in_clearance
    app.controller.step(1.0)  # through yellow into all-red
    app.controller.step(1.0)  # through all-red into East green

    assert app.controller.active_axis in ("East", "EW")
    assert app.signal_states["East"] == "GREEN"
    assert app.signal_states["North"] == "RED"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["West"] == "RED"


def test_emergency_priority_keeps_opposite_axis_red():
    """Selecting an emergency approach keeps all other approaches strictly red."""
    app = make_dashboard_for_emergency_test()
    app._set_signal_phase("North")

    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

    # Emergency on East triggers switch to East via real controller phase selection
    app.vehicle_queues["East"] = ["emergency-1"]
    app.emergency_vehicles.add("emergency-1")
    app._choose_next_phase()

    assert app.signal_states["East"] == "GREEN"
    assert app.signal_states["North"] == "RED"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["West"] == "RED"


def test_signal_transition_uses_yellow_and_all_red_clearance():
    """Signal approaches switch only after yellow and all-red clearance intervals."""
    app = make_dashboard_for_emergency_test()
    app._set_signal_phase("North")

    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

    # Initiate clearance transition to East via real dashboard method
    app._begin_signal_transition("East")

    # Immediately on transition start, departing approach is YELLOW
    assert app.signal_states["North"] == "YELLOW"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"

    # Advance 1.0s -> enters ALL_RED clearance
    app._advance_signal_transition(1.0)
    assert all(state == "RED" for state in app.signal_states.values())

    # Advance another 1.0s -> clearance finishes, East becomes GREEN
    app._advance_signal_transition(1.0)
    assert app.signal_states["East"] == "GREEN"
    assert app.signal_states["North"] == "RED"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["West"] == "RED"


def test_emergency_axis_waits_for_signal_clearance():
    """Emergency priority must not bypass yellow and all-red clearance."""
    app = make_dashboard_for_emergency_test()
    app._set_signal_phase("East")

    # Emergency arrives on North
    app.vehicle_queues["North"] = ["emergency-1"]
    app.emergency_vehicles.add("emergency-1")

    # Transition to emergency approach North via real dashboard method
    app._begin_signal_transition("North")

    # Departing approach East must show YELLOW, others are still RED
    assert app.signal_states["East"] == "YELLOW"
    assert app.signal_states["West"] == "RED"
    assert app.signal_states["North"] == "RED"
    assert app.signal_states["South"] == "RED"

    # Step through yellow into all-red
    app._advance_signal_transition(1.0)
    assert all(state == "RED" for state in app.signal_states.values())

    # Step through all-red into North green
    app._advance_signal_transition(1.0)
    assert app.signal_states["North"] == "GREEN"
    assert app.signal_states["South"] == "RED"
    assert app.signal_states["East"] == "RED"
    assert app.signal_states["West"] == "RED"


def test_dashboard_statistics_survive_queue_discharge():
    """Waiting time and throughput statistics survive queue discharge instead of collapsing."""
    app = make_dashboard_for_emergency_test()
    app.controller.start()

    # Add vehicle at North
    app.controller.add_vehicle("North", "normal")
    assert len(app.controller.get_approach_vehicles("North")) == 1

    # Step controller by 0.5s: vehicle accumulates waiting time
    app.controller.step(0.5)

    # Step controller by 0.5s: total 1.0s movement interval triggers departure
    app.controller.step(0.5)

    # Queue is now discharged to 0
    assert len(app.controller.get_approach_vehicles("North")) == 0

    # Refresh display
    app._refresh_display()

    # Domain statistics preserved cumulative records
    stats = app.controller.get_summary_statistics()
    assert stats["vehicles_processed_cumulative"] == 1
    assert stats["maximum_queue_length_cumulative"] >= 1
    assert stats["average_waiting_time_cumulative"] == pytest.approx(1.0, rel=0.1)

    # Label reflects cumulative average wait, not 0.0 s
    assert app.average_wait_label.configure.called
    wait_text = app.average_wait_label.configure.call_args[1]["text"]
    assert "0.0 s" not in wait_text
    assert "1.0 s" in wait_text



def test_dashboard_with_session_displays_username_and_logout_button(session_tk_root):
    """When a UserSession is provided, display user identity and the logout button."""
    import tkinter as tk
    window = tk.Toplevel(session_tk_root)
    window.withdraw()
    session = UserSession(user_id=42, username="supervisor_amy", role="Admin")
    mock_logout = Mock()

    app = TrafficDashboard(window, session=session, on_logout=mock_logout)
    try:
        assert hasattr(app, "session_label")
        assert "Logged in as: supervisor_amy (Admin)" in app.session_label.cget("text")
        assert hasattr(app, "logout_button")
        assert app.logout_button.cget("text") == "Logout"
    finally:
        app._on_close()


def test_dashboard_without_session_hides_banner_and_logout(session_tk_root):
    """Standalone/test dashboard without session hides the user banner and logout button."""
    import tkinter as tk
    window = tk.Toplevel(session_tk_root)
    window.withdraw()
    app = TrafficDashboard(window, session=None)
    try:
        assert not hasattr(app, "session_label")
        assert not hasattr(app, "logout_button")
    finally:
        app._on_close()


def test_dashboard_logout_invokes_callback_and_stops_simulation(session_tk_root):
    """Invoking logout stops simulation, closes window, and invokes on_logout callback."""
    import tkinter as tk
    window = tk.Toplevel(session_tk_root)
    window.withdraw()
    session = UserSession(user_id=1, username="test_op", role="Operator")
    mock_logout = Mock()

    app = TrafficDashboard(window, session=session, on_logout=mock_logout)
    app.start_simulation()
    assert app.engine.state.value == "running"

    app.logout()
    assert app.engine.state.value == "stopped"
    mock_logout.assert_called_once()


def test_dashboard_statistics_section_fully_visible(session_tk_root):
    """Traffic Statistics section and all metric labels fit within window bounds."""
    import tkinter as tk

    window = tk.Toplevel(session_tk_root)
    app = TrafficDashboard(window, session=None)
    try:
        window.update_idletasks()
        window.update()

        win_w = window.winfo_width()
        win_h = window.winfo_height()
        stats_frame = app.total_vehicles_label.master
        sf_y = stats_frame.winfo_rooty() - window.winfo_rooty()
        sf_h = stats_frame.winfo_height()

        assert win_w >= 960
        assert win_h >= 680
        assert sf_y + sf_h <= win_h

        for widget in (
            app.total_vehicles_label,
            app.approach_label,
            app.average_wait_label,
            app.max_queue_label,
            app.state_label,
            app.status_label,
        ):
            x = widget.winfo_rootx() - window.winfo_rootx()
            y = widget.winfo_rooty() - window.winfo_rooty()
            assert widget.winfo_ismapped()
            assert widget.winfo_width() >= widget.winfo_reqwidth()
            assert widget.winfo_height() >= widget.winfo_reqheight()
            assert x + widget.winfo_width() <= win_w
            assert y + widget.winfo_height() <= win_h
    finally:
        app._on_close()


def test_dashboard_dual_lane_ui_and_arrival_mode_controls(session_tk_root):
    """Dashboard UI supports dual-lane listbox rendering, lane selector, and arrival modes."""
    import tkinter as tk

    window = tk.Toplevel(session_tk_root)
    app = TrafficDashboard(window, session=None)
    try:
        window.update_idletasks()
        window.update()

        # 1. Assert Arrival Mode combobox contains Manual, Auto (round-robin), and Random
        assert hasattr(app, "arrival_mode_selector")
        mode_values = app.arrival_mode_selector.cget("values")
        assert "Manual" in mode_values
        assert "Auto (round-robin)" in mode_values
        assert "Random" in mode_values

        # 2. Assert Lane selector contains Lane 1 and Lane 2
        assert hasattr(app, "lane_selector")
        lane_values = app.lane_selector.cget("values")
        assert "Lane 1" in lane_values
        assert "Lane 2" in lane_values

        # 3. Assert dual lane listboxes exist and are mapped for each approach
        assert hasattr(app, "lane_listboxes")
        for approach in app.APPROACHES:
            assert approach in app.lane_listboxes
            l1_box, l2_box = app.lane_listboxes[approach]
            assert l1_box.winfo_ismapped()
            assert l2_box.winfo_ismapped()

        # 4. Add vehicle to North Lane 2 via UI controls
        app.approach_selector.set("North")
        app.lane_selector.set("Lane 2")
        app.vehicle_type_selector.set("Normal")
        app.arrival_mode_selector.set("Manual")
        v = app.add_vehicle()
        assert v.lane == 2

        # Verify North Lane 2 listbox received the vehicle while Lane 1 is empty
        l1_box, l2_box = app.lane_listboxes["North"]
        assert l1_box.size() == 0
        assert l2_box.size() == 1

        # 5. Switch to Random mode and add vehicle
        app.arrival_mode_selector.set("Random")
        v_rand = app.add_vehicle()
        assert isinstance(v_rand, Vehicle)
        assert app.controller.arrival_mode == "Random"
    finally:
        app._on_close()

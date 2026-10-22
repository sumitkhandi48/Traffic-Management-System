
"""Tests for simulation lifecycle controls."""

import pytest

from simulation.engine import SimulationEngine, SimulationState


def test_initial_state():
    engine = SimulationEngine()

    assert engine.state == SimulationState.STOPPED
    assert engine.simulation_time == 0.0


def test_start_simulation():
    engine = SimulationEngine()

    assert engine.start() is True
    assert engine.state == SimulationState.RUNNING


def test_pause_and_resume():
    engine = SimulationEngine()
    engine.start()

    assert engine.pause() is True
    assert engine.state == SimulationState.PAUSED

    assert engine.resume() is True
    assert engine.state == SimulationState.RUNNING


def test_stop_simulation():
    engine = SimulationEngine()
    engine.start()
    engine.step(5.0)

    assert engine.stop() is True
    assert engine.state == SimulationState.STOPPED
    assert engine.simulation_time == 5.0


def test_reset_simulation():
    engine = SimulationEngine()
    engine.start()
    engine.step(5.0)
    engine.pause()

    engine.reset()

    assert engine.state == SimulationState.STOPPED
    assert engine.simulation_time == 0.0


def test_step_advances_time_when_running():
    engine = SimulationEngine()
    engine.start()

    engine.step(2.5)
    engine.step(1.5)

    assert engine.simulation_time == pytest.approx(4.0)


def test_step_does_not_advance_when_paused():
    engine = SimulationEngine()
    engine.start()
    engine.step(3.0)
    engine.pause()

    engine.step(5.0)

    assert engine.simulation_time == 3.0


def test_step_does_not_advance_when_stopped():
    engine = SimulationEngine()

    engine.step(5.0)

    assert engine.simulation_time == 0.0


def test_negative_delta_time_is_rejected():
    engine = SimulationEngine()
    engine.start()

    with pytest.raises(ValueError):
        engine.step(-1.0)


def test_non_numeric_delta_time_is_rejected():
    engine = SimulationEngine()
    engine.start()

    with pytest.raises(TypeError):
        engine.step("1.0")


def test_invalid_state_transitions():
    engine = SimulationEngine()

    assert engine.pause() is False
    assert engine.resume() is False
    assert engine.stop() is False

    engine.start()

    assert engine.start() is False
    assert engine.resume() is False


"""Core lifecycle and clock for the traffic simulation."""

from enum import Enum


class SimulationState(Enum):
    """Possible lifecycle states of the simulation."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class SimulationEngine:
    """Manage simulation lifecycle and deterministic time advancement."""

    def __init__(self):
        self._state = SimulationState.STOPPED
        self._simulation_time = 0.0

    @property
    def state(self) -> SimulationState:
        """Return the current simulation state."""
        return self._state

    @property
    def simulation_time(self) -> float:
        """Return elapsed simulation time in seconds."""
        return self._simulation_time

    def start(self) -> bool:
        """Start a stopped simulation."""
        if self._state != SimulationState.STOPPED:
            return False

        self._state = SimulationState.RUNNING
        return True

    def pause(self) -> bool:
        """Pause a running simulation."""
        if self._state != SimulationState.RUNNING:
            return False

        self._state = SimulationState.PAUSED
        return True

    def resume(self) -> bool:
        """Resume a paused simulation."""
        if self._state != SimulationState.PAUSED:
            return False

        self._state = SimulationState.RUNNING
        return True

    def stop(self) -> bool:
        """Stop a running or paused simulation."""
        if self._state == SimulationState.STOPPED:
            return False

        self._state = SimulationState.STOPPED
        return True

    def reset(self) -> None:
        """Restore the initial stopped state and reset the clock."""
        self._state = SimulationState.STOPPED
        self._simulation_time = 0.0

    def step(self, delta_time: float) -> None:
        """Advance simulation time when running."""
        if isinstance(delta_time, bool) or not isinstance(
            delta_time, (int, float)
        ):
            raise TypeError("delta_time must be a number")

        if delta_time < 0:
            raise ValueError("delta_time cannot be negative")

        if self._state == SimulationState.RUNNING:
            self._simulation_time += delta_time

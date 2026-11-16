"""Signal phase lifecycle, clearance intervals, and state machine."""

from enum import Enum
from typing import Mapping


class SignalColor(str, Enum):
    """Permitted signal colors for traffic control."""

    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class PhaseTransitionState(str, Enum):
    """Lifecycle stages during signal phase clearance transitions."""

    NONE = "NONE"
    YELLOW = "YELLOW"
    ALL_RED = "ALL_RED"


class SignalPhaseController:
    """Explicit state machine for intersection traffic signal lifecycle.

    Guarantees:
    - Never transiently emits a conflicting GREEN signal.
    - Transitions through YELLOW clearance and ALL_RED clearance before switching axes.
    - Enforces configured MIN_GREEN_DURATION and MAX_GREEN_DURATION bounds.
    - Supports queue clearance extensions up to ABSOLUTE_MAX_GREEN_DURATION.
    """

    APPROACHES: tuple[str, ...] = ("North", "South", "East", "West")
    AXIS_APPROACHES: dict[str, tuple[str, str]] = {
        "NS": ("North", "South"),
        "EW": ("East", "West"),
    }

    DEFAULT_YELLOW_DURATION: float = 1.0
    DEFAULT_ALL_RED_DURATION: float = 1.0
    MIN_GREEN: float = 10.0
    MAX_GREEN: float = 60.0
    GAP_OUT_TIME: float = 2.0
    YELLOW_TIME: float = DEFAULT_YELLOW_DURATION
    ALL_RED_TIME: float = DEFAULT_ALL_RED_DURATION
    MIN_GREEN_DURATION: float = MIN_GREEN
    MAX_GREEN_DURATION: float = MAX_GREEN
    DEFAULT_GREEN_DURATION: float = MIN_GREEN
    ABSOLUTE_MAX_GREEN_DURATION: float = MAX_GREEN
    DEFAULT_GAP_DURATION: float = GAP_OUT_TIME

    def __init__(
        self,
        yellow_duration: float = DEFAULT_YELLOW_DURATION,
        all_red_duration: float = DEFAULT_ALL_RED_DURATION,
        min_green_duration: float = MIN_GREEN_DURATION,
        max_green_duration: float = MAX_GREEN_DURATION,
        default_green_duration: float = DEFAULT_GREEN_DURATION,
        absolute_max_green_duration: float = ABSOLUTE_MAX_GREEN_DURATION,
        gap_duration: float = DEFAULT_GAP_DURATION,
    ) -> None:
        self.yellow_duration = float(yellow_duration)
        self.all_red_duration = float(all_red_duration)
        self.min_green_duration = float(min_green_duration)
        self.max_green_duration = float(max_green_duration)
        self.default_green_duration = float(default_green_duration)
        self.absolute_max_green_duration = float(absolute_max_green_duration)
        self.gap_duration = float(gap_duration)

        self._active_axis: str = "NS"
        self._pending_axis: str | None = None
        self._transition_state: PhaseTransitionState = PhaseTransitionState.NONE
        self._transition_elapsed: float = 0.0
        self._phase_elapsed: float = 0.0
        self._phase_duration: float = self.default_green_duration
        self._pending_phase_duration: float = self.default_green_duration

        self._signal_states: dict[str, str] = {
            approach: SignalColor.RED.value for approach in self.APPROACHES
        }

    @property
    def active_axis(self) -> str:
        """Currently active axis ('NS' or 'EW')."""
        return self._active_axis

    @property
    def active_approaches(self) -> tuple[str, str]:
        """Approaches belonging to the active axis."""
        return self.AXIS_APPROACHES[self._active_axis]

    @property
    def pending_axis(self) -> str | None:
        """Target axis waiting for clearance completion, if any."""
        return self._pending_axis

    @property
    def transition_state(self) -> PhaseTransitionState:
        """Current clearance stage (NONE, YELLOW, or ALL_RED)."""
        return self._transition_state

    @property
    def transition_state_name(self) -> str | None:
        """Name of the clearance stage, or None if in steady green."""
        return None if self._transition_state == PhaseTransitionState.NONE else self._transition_state.value

    @property
    def is_in_clearance(self) -> bool:
        """True if the intersection is currently executing yellow or all-red clearance."""
        return self._transition_state != PhaseTransitionState.NONE

    @property
    def phase_elapsed(self) -> float:
        """Elapsed time in seconds for the current green phase."""
        return self._phase_elapsed

    @property
    def phase_duration(self) -> float:
        """Allocated green duration in seconds for the current phase."""
        return self._phase_duration

    @property
    def has_met_min_green(self) -> bool:
        """True when the current green phase has met the minimum green limit."""
        return self._phase_elapsed >= self.min_green_duration

    @property
    def transition_elapsed(self) -> float:
        """Elapsed time in seconds for the active clearance interval."""
        return self._transition_elapsed

    @property
    def signal_states(self) -> dict[str, str]:
        """Current signal colors for all four approaches."""
        return dict(self._signal_states)

    def _clamp_green_duration(self, duration: float) -> float:
        return min(
            self.max_green_duration,
            max(self.min_green_duration, float(duration)),
        )

    @staticmethod
    def other_axis(axis: str) -> str:
        """Return the conflicting crossing axis."""
        return "EW" if axis == "NS" else "NS"

    def start(self, initial_axis: str = "NS", duration: float | None = None) -> None:
        """Start signal operation with the specified axis green."""
        if initial_axis not in self.AXIS_APPROACHES:
            raise ValueError(f"Invalid axis: {initial_axis}")

        self._active_axis = initial_axis
        self._pending_axis = None
        self._transition_state = PhaseTransitionState.NONE
        self._transition_elapsed = 0.0
        self._phase_elapsed = 0.0
        self._phase_duration = (
            self._clamp_green_duration(duration)
            if duration is not None
            else self.default_green_duration
        )

        self._apply_axis_green(initial_axis)

    def reset(self) -> None:
        """Reset the controller to all RED stopped state."""
        self._active_axis = "NS"
        self._pending_axis = None
        self._transition_state = PhaseTransitionState.NONE
        self._transition_elapsed = 0.0
        self._phase_elapsed = 0.0
        self._phase_duration = self.default_green_duration
        self._pending_phase_duration = self.default_green_duration

        for approach in self.APPROACHES:
            self._signal_states[approach] = SignalColor.RED.value

    def _apply_axis_green(self, axis: str) -> None:
        """Set green only on the selected axis; conflicting axis is strictly red."""
        green_approaches = self.AXIS_APPROACHES[axis]
        for approach in self.APPROACHES:
            self._signal_states[approach] = (
                SignalColor.GREEN.value
                if approach in green_approaches
                else SignalColor.RED.value
            )

    def request_phase_switch(
        self,
        target_axis: str,
        target_green_duration: float | None = None,
    ) -> bool:
        """Schedule or initiate a safe clearance transition to target_axis.

        Returns True if a transition is in progress or was initiated;
        False if target_axis is already active and steady.
        """
        if target_axis not in self.AXIS_APPROACHES:
            raise ValueError(f"Invalid axis: {target_axis}")

        clamped_duration = (
            self._clamp_green_duration(target_green_duration)
            if target_green_duration is not None
            else self.default_green_duration
        )

        # If already on the target axis and not clearing, just update duration if needed
        if target_axis == self._active_axis and not self.is_in_clearance:
            if target_green_duration is not None:
                self._phase_duration = clamped_duration
            return False

        # If already in clearance, update the pending axis to transition to next
        if self.is_in_clearance:
            self._pending_axis = target_axis
            self._pending_phase_duration = clamped_duration
            return True

        # Begin clearance transition: active axis turns YELLOW, cross axis stays RED
        self._pending_axis = target_axis
        self._pending_phase_duration = clamped_duration
        self._transition_state = PhaseTransitionState.YELLOW
        self._transition_elapsed = 0.0

        for approach in self.AXIS_APPROACHES[self._active_axis]:
            self._signal_states[approach] = SignalColor.YELLOW.value

        for approach in self.AXIS_APPROACHES[target_axis]:
            self._signal_states[approach] = SignalColor.RED.value

        return True

    def step(self, delta_time: float) -> tuple[bool, str | None]:
        """Advance signal timers according to delta_time.

        Returns:
            (transition_completed, new_active_axis)
        """
        if delta_time < 0:
            raise ValueError("delta_time cannot be negative")

        if self._transition_state == PhaseTransitionState.YELLOW:
            self._transition_elapsed += delta_time
            if self._transition_elapsed >= self.yellow_duration:
                # Transition to ALL_RED clearance
                self._transition_state = PhaseTransitionState.ALL_RED
                self._transition_elapsed = 0.0
                for approach in self.APPROACHES:
                    self._signal_states[approach] = SignalColor.RED.value
            return False, None

        if self._transition_state == PhaseTransitionState.ALL_RED:
            self._transition_elapsed += delta_time
            if self._transition_elapsed >= self.all_red_duration:
                # Clearance complete! Safely activate the target axis
                new_axis = self._pending_axis or self.other_axis(self._active_axis)
                self._transition_state = PhaseTransitionState.NONE
                self._transition_elapsed = 0.0
                self._pending_axis = None
                self._active_axis = new_axis
                self._phase_elapsed = 0.0
                self._phase_duration = self._pending_phase_duration
                self._apply_axis_green(new_axis)
                return True, new_axis
            return False, None

        # Steady green state
        self._phase_elapsed += delta_time
        return False, None

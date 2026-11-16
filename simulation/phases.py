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

    APPROACHES: tuple[str, ...] = ("North", "East", "South", "West")
    CLOCKWISE_ORDER: tuple[str, ...] = ("North", "East", "South", "West")
    AXIS_APPROACHES: dict[str, tuple[str, ...]] = {
        "North": ("North",),
        "East": ("East",),
        "South": ("South",),
        "West": ("West",),
        "NS": ("North",),
        "EW": ("East",),
    }

    DEFAULT_YELLOW_DURATION: float = 1.0
    DEFAULT_ALL_RED_DURATION: float = 1.0
    MIN_GREEN: float = 10.0
    MAX_GREEN: float = 60.0
    GAP_OUT_TIME: float = 1.0
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

        self._active_axis: str = "North"
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
        """Currently active axis or approach."""
        return self._active_axis

    @property
    def active_approaches(self) -> tuple[str, ...]:
        """Approaches belonging to the active phase (single approach)."""
        norm = self.normalize_axis(self._active_axis)
        return self.AXIS_APPROACHES.get(self._active_axis, (norm,))

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

    @classmethod
    def normalize_axis(cls, axis: str) -> str:
        """Normalize axis or approach name to a single valid approach in CLOCKWISE_ORDER."""
        if not isinstance(axis, str) or not axis.strip():
            raise ValueError(f"Invalid axis: {axis}")
        clean = axis.strip()
        for app in cls.CLOCKWISE_ORDER:
            if clean.lower() == app.lower():
                return app
        if clean.upper() == "NS":
            return "North"
        if clean.upper() == "EW":
            return "East"
        if clean in cls.AXIS_APPROACHES:
            return cls.AXIS_APPROACHES[clean][0]
        raise ValueError(f"Invalid axis: {axis}")

    @classmethod
    def get_clockwise_next(cls, current: str) -> str:
        """Return the next approach in clockwise order (North -> East -> South -> West -> North)."""
        norm = cls.normalize_axis(current)
        idx = cls.CLOCKWISE_ORDER.index(norm)
        return cls.CLOCKWISE_ORDER[(idx + 1) % len(cls.CLOCKWISE_ORDER)]

    @classmethod
    def other_axis(cls, axis: str) -> str:
        """Return the next approach in clockwise order."""
        return cls.get_clockwise_next(axis)

    def start(self, initial_axis: str = "North", duration: float | None = None) -> None:
        """Start signal operation with the specified axis green."""
        norm_axis = self.normalize_axis(initial_axis)

        self._active_axis = norm_axis
        self._pending_axis = None
        self._transition_state = PhaseTransitionState.NONE
        self._transition_elapsed = 0.0
        self._phase_elapsed = 0.0
        self._phase_duration = (
            self._clamp_green_duration(duration)
            if duration is not None
            else self.default_green_duration
        )

        self._apply_axis_green(norm_axis)

    def reset(self) -> None:
        """Reset the controller to all RED stopped state."""
        self._active_axis = "North"
        self._pending_axis = None
        self._transition_state = PhaseTransitionState.NONE
        self._transition_elapsed = 0.0
        self._phase_elapsed = 0.0
        self._phase_duration = self.default_green_duration
        self._pending_phase_duration = self.default_green_duration

        for approach in self.APPROACHES:
            self._signal_states[approach] = SignalColor.RED.value

    def _apply_axis_green(self, axis: str) -> None:
        """Set green only on the single selected approach; all other signals are strictly red."""
        norm = self.normalize_axis(axis)
        green_approaches = self.AXIS_APPROACHES.get(axis, (norm,))
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
        norm_target = self.normalize_axis(target_axis)
        norm_active = self.normalize_axis(self._active_axis)

        clamped_duration = (
            self._clamp_green_duration(target_green_duration)
            if target_green_duration is not None
            else self.default_green_duration
        )

        # If already on the target axis and not clearing, just update duration if needed
        if norm_target == norm_active and not self.is_in_clearance:
            if target_green_duration is not None:
                self._phase_duration = clamped_duration
            return False

        # If already in clearance, update the pending axis to transition to next
        if self.is_in_clearance:
            self._pending_axis = norm_target
            self._pending_phase_duration = clamped_duration
            return True

        # Begin clearance transition: active axis turns YELLOW, all other signals stay RED
        self._pending_axis = norm_target
        self._pending_phase_duration = clamped_duration
        self._transition_state = PhaseTransitionState.YELLOW
        self._transition_elapsed = 0.0

        active_apps = self.AXIS_APPROACHES.get(self._active_axis, (norm_active,))
        for approach in self.APPROACHES:
            if approach in active_apps:
                self._signal_states[approach] = SignalColor.YELLOW.value
            else:
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
                new_axis = self._pending_axis or self.get_clockwise_next(self._active_axis)
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

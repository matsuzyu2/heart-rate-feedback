"""Participant-facing feedback display window."""

from __future__ import annotations

import tkinter as tk

_TREND_SYMBOLS: dict[str, str] = {
    "increasing": "▲",
    "decreasing": "▼",
    "stable": "─",
}

_BG = "#f3f6fb"
_FG_DARK = "#1f2d3d"
_FG_MID = "#22313f"
_REWARD_BAR_WIDTH = 400
_REWARD_BAR_HEIGHT = 28
_REWARD_MAX = 1000.0  # yen; bar fills at this value


class FeedbackDisplay:
    """Secondary window shown to the participant during the experiment.

    Displays:
    - Large heart-rate value with trend indicator (▲ / ▼ / ─).
    - A canvas-based reward bar showing accumulated reward in yen.
    - Phase name and countdown timer.

    Args:
        root: Parent :class:`tk.Tk` window.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._window = tk.Toplevel(root)
        self._window.title("HR Feedback Display")
        self._window.geometry("500x420")
        self._window.configure(bg=_BG)

        # --- Heart rate + trend row ---
        hr_frame = tk.Frame(self._window, bg=_BG)
        hr_frame.pack(pady=(30, 4))

        self._hr_label = tk.Label(
            hr_frame,
            text="HR --.- BPM",
            font=("Helvetica", 34, "bold"),
            bg=_BG,
            fg=_FG_DARK,
        )
        self._hr_label.pack(side=tk.LEFT, padx=(0, 10))

        self._trend_label = tk.Label(
            hr_frame,
            text="─",
            font=("Helvetica", 30),
            bg=_BG,
            fg="#3a7bd5",
        )
        self._trend_label.pack(side=tk.LEFT)

        # --- Reward bar ---
        reward_frame = tk.Frame(self._window, bg=_BG)
        reward_frame.pack(pady=10)

        tk.Label(
            reward_frame,
            text="Reward",
            font=("Helvetica", 13),
            bg=_BG,
            fg=_FG_MID,
        ).pack(anchor="w")

        self._reward_canvas = tk.Canvas(
            reward_frame,
            width=_REWARD_BAR_WIDTH,
            height=_REWARD_BAR_HEIGHT,
            bg="#dce3ed",
            highlightthickness=1,
            highlightbackground="#b0bec5",
        )
        self._reward_canvas.pack()

        self._reward_bar = self._reward_canvas.create_rectangle(
            0, 0, 0, _REWARD_BAR_HEIGHT,
            fill="#4caf50",
            outline="",
        )

        self._reward_text = tk.Label(
            reward_frame,
            text="¥0",
            font=("Helvetica", 13),
            bg=_BG,
            fg=_FG_MID,
        )
        self._reward_text.pack(anchor="e")

        # --- Phase and timer ---
        self._phase_label = tk.Label(
            self._window,
            text="Phase: -",
            font=("Helvetica", 18),
            bg=_BG,
            fg=_FG_MID,
        )
        self._phase_label.pack(pady=8)

        self._time_label = tk.Label(
            self._window,
            text="Remaining: --:--",
            font=("Helvetica", 20),
            bg=_BG,
            fg=_FG_MID,
        )
        self._time_label.pack(pady=8)

        self._reward_accumulated: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_hr(self, bpm: float) -> None:
        """Update the displayed heart-rate value.

        Args:
            bpm: Heart rate in beats per minute.
        """
        self._hr_label.configure(text=f"HR {bpm:.1f} BPM")

    def set_trend(self, trend: str) -> None:
        """Update the trend indicator symbol.

        Args:
            trend: One of ``"increasing"``, ``"decreasing"``, or ``"stable"``.
        """
        symbol = _TREND_SYMBOLS.get(trend, "─")
        colors = {
            "increasing": "#e53935",
            "decreasing": "#1e88e5",
            "stable": "#3a7bd5",
        }
        color = colors.get(trend, "#3a7bd5")
        self._trend_label.configure(text=symbol, fg=color)

    def set_reward(self, amount: float) -> None:
        """Update the reward bar and text label.

        Args:
            amount: Accumulated reward in yen.
        """
        self._reward_accumulated = max(0.0, amount)
        fill_ratio = min(1.0, self._reward_accumulated / _REWARD_MAX)
        bar_width = int(fill_ratio * _REWARD_BAR_WIDTH)
        self._reward_canvas.coords(
            self._reward_bar,
            0, 0, bar_width, _REWARD_BAR_HEIGHT,
        )
        self._reward_text.configure(text=f"¥{self._reward_accumulated:.0f}")

    def set_hr_and_trend(self, bpm: float, trend: str) -> None:
        """Convenience method to update HR and trend in one call.

        Args:
            bpm: Heart rate in beats per minute.
            trend: One of ``"increasing"``, ``"decreasing"``, or ``"stable"``.
        """
        self.set_hr(bpm)
        self.set_trend(trend)

    def set_phase(self, phase_text: str) -> None:
        """Update the phase name label.

        Args:
            phase_text: Phase name string.
        """
        self._phase_label.configure(text=f"Phase: {phase_text}")

    def set_remaining(self, seconds: int) -> None:
        """Update the remaining-time label.

        Args:
            seconds: Remaining seconds (non-negative).
        """
        m, s = divmod(max(0, seconds), 60)
        self._time_label.configure(text=f"Remaining: {m:02d}:{s:02d}")

"""Participant-facing feedback display window."""

from __future__ import annotations

import tkinter as tk


class FeedbackDisplay:
    """Secondary window for participant-facing feedback."""

    def __init__(self, root: tk.Tk) -> None:
        self._window = tk.Toplevel(root)
        self._window.title("HR Feedback Display")
        self._window.geometry("500x320")
        self._window.configure(bg="#f3f6fb")

        self._hr_label = tk.Label(
            self._window,
            text="HR --.- BPM",
            font=("Helvetica", 34, "bold"),
            bg="#f3f6fb",
            fg="#1f2d3d",
        )
        self._hr_label.pack(pady=30)

        self._phase_label = tk.Label(
            self._window,
            text="Phase: -",
            font=("Helvetica", 18),
            bg="#f3f6fb",
            fg="#22313f",
        )
        self._phase_label.pack(pady=8)

        self._time_label = tk.Label(
            self._window,
            text="Remaining: --:--",
            font=("Helvetica", 20),
            bg="#f3f6fb",
            fg="#22313f",
        )
        self._time_label.pack(pady=8)

    def set_hr(self, bpm: float) -> None:
        """Update displayed heart-rate value."""
        self._hr_label.configure(text=f"HR {bpm:.1f} BPM")

    def set_phase(self, phase_text: str) -> None:
        """Update phase text."""
        self._phase_label.configure(text=f"Phase: {phase_text}")

    def set_remaining(self, seconds: int) -> None:
        """Update remaining time in mm:ss."""
        m, s = divmod(max(0, seconds), 60)
        self._time_label.configure(text=f"Remaining: {m:02d}:{s:02d}")

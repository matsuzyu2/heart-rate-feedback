"""Experimenter control panel widgets."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


class ExperimenterPanel(tk.Frame):
    """Control panel with start/stop/skip actions."""

    def __init__(
        self,
        master: tk.Misc,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_skip: Callable[[], None],
    ) -> None:
        super().__init__(master, bg="#ffffff", padx=12, pady=12)
        tk.Button(self, text="Start", command=on_start, width=10).pack(side=tk.LEFT, padx=6)
        tk.Button(self, text="Stop", command=on_stop, width=10).pack(side=tk.LEFT, padx=6)
        tk.Button(self, text="Next Phase", command=on_skip, width=12).pack(side=tk.LEFT, padx=6)

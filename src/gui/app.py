"""Main Tkinter application for experimenter and participant windows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
import tkinter as tk
from tkinter import messagebox

from src.config.settings import load_settings
from src.gui.experiment_flow import build_phase_plan
from src.gui.experimenter_panel import ExperimenterPanel
from src.gui.feedback_display import FeedbackDisplay
from src.gui.participant_form import Group, ParticipantInput, validate_participant_id
from src.logging.trigger_logger import TriggerLogger
from src.sensor.trigger.actichamp import ActiChampTrigger
from src.sensor.trigger.base import TriggerDevice, TriggerDispatcher
from src.sensor.trigger.cognionics import CognionicsTrigger
from src.sensor.trigger.lsl import LSLTrigger
from src.session.session_manager import SessionManager


@dataclass
class AppState:
    """Mutable app runtime state."""

    running: bool = False
    phase_index: int = 0
    phase_remaining: int = 0
    elapsed_seconds: int = 0


class HRFBApp:
    """Experiment management GUI application."""

    def __init__(self) -> None:
        self.settings = load_settings()
        self.session_manager = SessionManager(data_dir=self.settings.data_dir)

        self.root = tk.Tk()
        self.root.title("HRFB Experimenter")
        self.root.geometry("760x520")
        self.root.configure(bg="#f8fafc")

        self.feedback_display = FeedbackDisplay(self.root)
        self.state = AppState()
        self._phase_plan = []
        self._active_participant_id: str | None = None
        self._active_session_number: int | None = None
        self._session_started_mono: float | None = None
        self._trigger_dispatcher: TriggerDispatcher | None = None

        self._build_form()
        self._build_status()
        self._build_controls()

    def _build_form(self) -> None:
        frame = tk.Frame(self.root, bg="#f8fafc", padx=14, pady=12)
        frame.pack(fill=tk.X)

        tk.Label(frame, text="Participant ID", bg="#f8fafc").grid(row=0, column=0, sticky="w")
        self.participant_id_entry = tk.Entry(frame, width=12)
        self.participant_id_entry.insert(0, "P001")
        self.participant_id_entry.grid(row=1, column=0, padx=4)

        tk.Label(frame, text="Group", bg="#f8fafc").grid(row=0, column=1, sticky="w")
        self.group_var = tk.StringVar(value=Group.DR.value)
        tk.OptionMenu(frame, self.group_var, Group.UR.value, Group.DR.value).grid(row=1, column=1, padx=4)

        tk.Label(frame, text="Session #", bg="#f8fafc").grid(row=0, column=2, sticky="w")
        self.session_entry = tk.Entry(frame, width=8)
        self.session_entry.insert(0, "1")
        self.session_entry.grid(row=1, column=2, padx=4)

    def _build_status(self) -> None:
        frame = tk.Frame(self.root, bg="#f8fafc", padx=14, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        self.phase_label = tk.Label(frame, text="Phase: -", font=("Helvetica", 18, "bold"), bg="#f8fafc")
        self.phase_label.pack(anchor="w", pady=8)

        self.timer_label = tk.Label(frame, text="Remaining: --:--", font=("Helvetica", 20), bg="#f8fafc")
        self.timer_label.pack(anchor="w", pady=8)

        self.history_text = tk.Text(frame, height=12, width=90)
        self.history_text.pack(fill=tk.BOTH, expand=True)

    def _build_controls(self) -> None:
        panel = ExperimenterPanel(
            self.root,
            on_start=self.start_session,
            on_stop=self.stop_session,
            on_skip=self.skip_phase,
        )
        panel.pack(fill=tk.X, pady=8)

    def _build_input(self) -> ParticipantInput | None:
        participant_id = self.participant_id_entry.get().strip().upper()
        if not validate_participant_id(participant_id):
            messagebox.showerror("Input Error", "Participant ID must be like P001")
            return None
        try:
            session_number = int(self.session_entry.get().strip())
        except ValueError:
            messagebox.showerror("Input Error", "Session number must be integer")
            return None

        group = Group(self.group_var.get())
        return ParticipantInput(
            participant_id=participant_id,
            group=group,
            session_number=session_number,
        )

    def start_session(self) -> None:
        """Initialize plan and begin local phase timer loop."""
        if self.state.running:
            return
        model = self._build_input()
        if model is None:
            return

        self.session_manager.ensure_participant(
            participant_id=model.participant_id,
            group=model.group.value,
        )
        self._phase_plan = build_phase_plan(
            session_number=model.session_number,
            rest_seconds=self.settings.timing.rest_seconds,
            hrfb_seconds=self.settings.timing.hrfb_seconds,
            break_seconds=self.settings.timing.break_seconds,
        )

        condition_order = [
            p.condition.value
            for p in self._phase_plan
            if p.condition is not None
        ]
        self.session_manager.create_session_meta(
            participant_id=model.participant_id,
            session_number=model.session_number,
            condition_order=condition_order,
            polar_device_id=self.settings.polar_device_id,
        )
        self._setup_trigger_dispatcher(
            participant_id=model.participant_id,
            session_number=model.session_number,
        )

        self.state.running = True
        self.state.phase_index = 0
        self.state.elapsed_seconds = 0
        self.state.phase_remaining = self._phase_plan[0].duration_seconds
        self._active_participant_id = model.participant_id
        self._active_session_number = model.session_number
        self._session_started_mono = time.monotonic()
        self._begin_current_phase()
        self._emit_trigger(
            trigger_value=self.settings.trigger.session_start_code,
            annotation="session_start",
        )
        self._refresh_view()
        self._tick()

    def stop_session(self) -> None:
        """Stop local timer loop."""
        if self.state.running:
            self._end_current_phase()
            self._emit_trigger(
                trigger_value=self.settings.trigger.session_end_code,
                annotation="session_end",
            )
            self._finalize_session_meta()
        self.state.running = False

    def skip_phase(self) -> None:
        """Manual jump to the next phase."""
        if not self.state.running:
            return
        self._advance_phase()

    def _advance_phase(self) -> None:
        self._end_current_phase()
        self.state.phase_index += 1
        if self.state.phase_index >= len(self._phase_plan):
            self.state.running = False
            self.phase_label.configure(text="Phase: completed")
            self.timer_label.configure(text="Remaining: 00:00")
            self._finalize_session_meta()
            return
        self.state.phase_remaining = self._phase_plan[self.state.phase_index].duration_seconds
        self._begin_current_phase()
        self._refresh_view()

    def _tick(self) -> None:
        if not self.state.running:
            return
        self.state.phase_remaining -= 1
        self.state.elapsed_seconds += 1
        if self.state.phase_remaining <= 0:
            self._advance_phase()
        self._refresh_view()
        self.root.after(1000, self._tick)

    def _begin_current_phase(self) -> None:
        if self._active_participant_id is None or self._active_session_number is None:
            return
        current = self._phase_plan[self.state.phase_index]
        self.session_manager.begin_phase(
            participant_id=self._active_participant_id,
            session_number=self._active_session_number,
            phase_name=current.name.value,
            started_elapsed_sec=float(self.state.elapsed_seconds),
            condition=current.condition.value if current.condition is not None else None,
        )
        self._emit_trigger(
            trigger_value=self.settings.trigger.phase_start_code,
            annotation=f"phase_{current.name.value}_start",
        )

    def _end_current_phase(self) -> None:
        if self._active_participant_id is None or self._active_session_number is None:
            return
        if not self._phase_plan:
            return
        idx = min(self.state.phase_index, len(self._phase_plan) - 1)
        current = self._phase_plan[idx]
        try:
            self.session_manager.end_phase(
                participant_id=self._active_participant_id,
                session_number=self._active_session_number,
                phase_name=current.name.value,
                ended_elapsed_sec=float(self.state.elapsed_seconds),
            )
            self._emit_trigger(
                trigger_value=self.settings.trigger.phase_end_code,
                annotation=f"phase_{current.name.value}_end",
            )
        except ValueError:
            return

    def _finalize_session_meta(self) -> None:
        if self._active_participant_id is None or self._active_session_number is None:
            return
        self.session_manager.finalize_session(
            participant_id=self._active_participant_id,
            session_number=self._active_session_number,
            clock_sync={},
        )

    def _setup_trigger_dispatcher(self, participant_id: str, session_number: int) -> None:
        session_dir = self.session_manager.get_session_dir(participant_id, session_number)
        trigger_logger = TriggerLogger(session_dir / "trigger_log.csv")

        devices: list[TriggerDevice] = []

        actichamp = ActiChampTrigger(
            port=self.settings.actichamp.serial_port,
            baudrate=self.settings.actichamp.serial_baudrate,
            enabled=self.settings.actichamp.enabled,
        )
        if actichamp.connect():
            devices.append(actichamp)

        cognionics = CognionicsTrigger(
            zmq_address=self.settings.cognionics.zmq_address,
            serial_port=self.settings.cognionics.serial_port,
            serial_baudrate=self.settings.cognionics.serial_baudrate,
            enabled=self.settings.cognionics.enabled,
        )
        if cognionics.connect():
            devices.append(cognionics)

        lsl = LSLTrigger(
            stream_name=self.settings.lsl.stream_name,
            source_id=self.settings.lsl.source_id,
            enabled=self.settings.lsl.enabled,
        )
        devices.append(lsl)

        self._trigger_dispatcher = TriggerDispatcher(devices=devices, logger=trigger_logger)

    def _emit_trigger(self, trigger_value: int, annotation: str) -> None:
        if self._trigger_dispatcher is None:
            return
        system_time_ns = time.time_ns()
        asyncio.run(
            self._trigger_dispatcher.send_all(
                trigger_value=trigger_value,
                annotation=annotation,
                system_time_ns=system_time_ns,
                reset_pulse_seconds=self.settings.trigger.reset_pulse_seconds,
            )
        )

    def _refresh_view(self) -> None:
        if not self._phase_plan:
            return
        phase = self._phase_plan[min(self.state.phase_index, len(self._phase_plan) - 1)]
        self.phase_label.configure(text=f"Phase: {phase.name.value}")
        m, s = divmod(max(0, self.state.phase_remaining), 60)
        self.timer_label.configure(text=f"Remaining: {m:02d}:{s:02d}")
        self.feedback_display.set_phase(phase.name.value)
        self.feedback_display.set_remaining(self.state.phase_remaining)

    def run(self) -> None:
        """Run Tk mainloop."""
        self._render_history()
        self.root.mainloop()

    def _render_history(self) -> None:
        participant_id = self.participant_id_entry.get().strip().upper()
        if not validate_participant_id(participant_id):
            return
        history = self.session_manager.get_session_history(participant_id)
        self.history_text.delete("1.0", tk.END)
        if not history:
            self.history_text.insert(tk.END, "No session history yet.\n")
            return
        for row in history:
            self.history_text.insert(
                tk.END,
                f"session={row['session_number']} started={row['started_at']} order={row['condition_order']}\n",
            )


def run_app() -> None:
    """Entrypoint helper for console script."""
    HRFBApp().run()

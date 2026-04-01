"""ECG pipeline runner that streams data in a background asyncio thread."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from src.config.settings import AppSettings
from src.logging.session_logger import SessionLogger
from src.processing.ecg_filter import ECGFilter
from src.processing.heart_rate import HeartRateEstimator
from src.processing.r_peak_detector import RPeakDetector
from src.sensor.polar_ecg import PolarECGClient
from src.sensor.trigger.base import TriggerDispatcher

logger = logging.getLogger(__name__)


class EcgRunner:
    """Run the ECG streaming pipeline in a background asyncio thread.

    The runner owns a dedicated OS thread which hosts its own asyncio event
    loop.  The main (GUI) thread may safely poll :attr:`latest_hr`,
    :attr:`beat_count`, :attr:`clock_sync`, and :attr:`connected` at any time
    because all shared state is protected by a :class:`threading.Lock`.

    Usage::

        runner = EcgRunner(settings, session_logger, trigger_dispatcher)
        runner.start()          # launches background thread
        hr = runner.latest_hr   # poll from main thread
        runner.stop()           # signal shutdown and join thread

    Args:
        settings: Application settings (device ID, processing params, …).
        session_logger: Open per-session CSV writers.
        trigger_dispatcher: Optional trigger dispatcher (reserved for future
            feedback-trigger integration; not used internally yet).
    """

    def __init__(
        self,
        settings: AppSettings,
        session_logger: SessionLogger,
        trigger_dispatcher: Optional[TriggerDispatcher] = None,
    ) -> None:
        self._settings = settings
        self._session_logger = session_logger
        self._trigger_dispatcher = trigger_dispatcher

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None

        # Thread-safe shared state
        self._lock = threading.Lock()
        self._latest_hr: Optional[float] = None
        self._beat_count: int = 0
        self._clock_sync: Optional[dict] = None
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Thread-safe properties (safe to read from the main/GUI thread)
    # ------------------------------------------------------------------

    @property
    def latest_hr(self) -> Optional[float]:
        """Latest heart rate in BPM, or ``None`` if not yet available."""
        with self._lock:
            return self._latest_hr

    @property
    def beat_count(self) -> int:
        """Number of R-peaks detected since streaming started."""
        with self._lock:
            return self._beat_count

    @property
    def clock_sync(self) -> Optional[dict]:
        """Clock synchronisation dict from :class:`PolarECGClient`, or ``None``."""
        with self._lock:
            return self._clock_sync

    @property
    def connected(self) -> bool:
        """``True`` while the BLE connection is active."""
        with self._lock:
            return self._connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the background ECG thread and return immediately."""
        self._thread = threading.Thread(
            target=self._run_thread,
            daemon=True,
            name="EcgRunner",
        )
        self._thread.start()
        logger.info("EcgRunner background thread started")

    def stop(self) -> None:
        """Signal the background thread to stop and wait up to 5 seconds."""
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("EcgRunner thread did not terminate within 5 s")
        logger.info("EcgRunner stopped")

    # ------------------------------------------------------------------
    # Background thread internals
    # ------------------------------------------------------------------

    def _run_thread(self) -> None:
        """Thread entry point: create an asyncio loop and run the pipeline."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_async())
        except Exception:
            logger.exception("Unhandled exception in EcgRunner async pipeline")
        finally:
            self._loop.close()

    async def _run_async(self) -> None:
        """Async pipeline: connect, stream, process, log."""
        self._stop_event = asyncio.Event()

        s = self._settings
        client = PolarECGClient(
            device_id=s.polar_device_id,
            sampling_rate_hz=s.processing.sampling_rate_hz,
        )

        ecg_filter = ECGFilter(
            sampling_rate_hz=s.processing.sampling_rate_hz,
            low_hz=s.processing.bandpass_low_hz,
            high_hz=s.processing.bandpass_high_hz,
        )
        r_peak_detector = RPeakDetector(
            refractory_period_ms=s.processing.refractory_period_ms,
            sampling_rate_hz=s.processing.sampling_rate_hz,
        )
        hr_estimator = HeartRateEstimator()
        beat_counter = [0]

        async def on_sample(timestamp_ns: int, ecg_uv: int) -> None:
            # Capture clock sync after the first sample arrives
            cs = client.clock_sync
            if cs is not None:
                with self._lock:
                    if self._clock_sync is None:
                        self._clock_sync = cs

            # Log raw ECG
            self._session_logger.ecg_raw.write_row([timestamp_ns, ecg_uv])

            # Filter
            filtered = ecg_filter.process(float(ecg_uv))

            # R-peak detection
            event = r_peak_detector.update(timestamp_ns, filtered)
            if event is not None:
                beat = hr_estimator.on_peak(event.timestamp_ns)
                beat_counter[0] += 1

                # Log heartbeat
                self._session_logger.heartbeats.write_row([
                    beat.beat_id,
                    beat.timestamp_ns,
                    beat.rr_interval_ms if beat.rr_interval_ms is not None else "",
                    beat.heart_rate_bpm if beat.heart_rate_bpm is not None else "",
                ])

                # Update shared state (thread-safe)
                with self._lock:
                    self._latest_hr = beat.heart_rate_bpm
                    self._beat_count = beat_counter[0]

        connected = await client.connect()
        with self._lock:
            self._connected = connected

        if not connected:
            logger.error("Failed to connect to Polar H10 — aborting EcgRunner")
            return

        try:
            started = await client.start_streaming(on_sample)
            if not started:
                logger.error("start_streaming returned False — aborting EcgRunner")
                return

            # Block until the main thread signals stop
            await self._stop_event.wait()

        finally:
            await client.stop_streaming()
            await client.disconnect()
            with self._lock:
                self._connected = False
            logger.info("EcgRunner async pipeline finished")

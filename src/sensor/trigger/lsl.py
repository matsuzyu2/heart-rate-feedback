"""LSL trigger implementation wrapper."""

from __future__ import annotations

from pylsl import StreamInfo, StreamOutlet


class LSLTrigger:
    """LSL marker sender."""

    name = "lsl"

    def __init__(self, stream_name: str, source_id: str, enabled: bool = True) -> None:
        self._enabled = enabled
        self._outlet: StreamOutlet | None = None
        if enabled:
            info = StreamInfo(stream_name, "Markers", 1, 0, "int32", source_id)
            self._outlet = StreamOutlet(info)

    async def send(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        """Push marker sample."""
        _ = reset_pulse_seconds
        if not self._enabled:
            return True
        if self._outlet is None:
            return False
        self._outlet.push_sample([trigger_value])
        return True

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] Running MVP automated tests..."
python3 -m pytest -q \
  tests/test_session/test_feedback_scheduler.py \
  tests/test_config/test_settings.py \
  tests/test_session/test_session_manager.py \
  tests/test_gui/test_experiment_flow.py \
  tests/test_sensor/test_trigger_dispatcher.py

echo "[2/3] Running session metadata lifecycle smoke check..."
python3 - <<'PY'
from pathlib import Path
import json
import tempfile

from src.session.session_manager import SessionManager

base = Path(tempfile.mkdtemp(prefix="hrfb_daily_check_"))
manager = SessionManager(data_dir=base)

manager.ensure_participant("P999", "UR")
manager.create_session_meta(
    participant_id="P999",
    session_number=1,
    condition_order=["target", "control"],
    polar_device_id="D1948025",
)
manager.begin_phase("P999", 1, "rest_pre_1", 0.0)
manager.end_phase("P999", 1, "rest_pre_1", 120.0)
manager.finalize_session("P999", 1, clock_sync={})

meta_path = base / "P999" / "session_001" / "session_meta.json"
payload = json.loads(meta_path.read_text(encoding="utf-8"))
assert payload["phases"][0]["phase"] == "rest_pre_1"
assert payload["phases"][0]["ended_at"] is not None
assert payload["ended_at"] is not None
print(f"smoke_ok meta={meta_path}")
PY

echo "[3/3] Daily MVP integration check completed successfully."

# Heart-Rate Biofeedback (Rebuild)

This repository is being rebuilt for graduate research use.
The scope is limited to HRFB-only components:

- Polar H10 ECG streaming
- ECG processing and R-peak-based HR estimation
- Visual feedback UI
- EEG trigger delivery (ActiCHamp, Cognionics, LSL)
- Structured session logging for longitudinal sessions

## Current Status

Initial implementation foundation is complete:

- New architecture modules under `src/config`, `src/gui`, `src/logging`, `src/sensor/trigger`, and `src/session`
- Audio feedback modules removed
- Trigger dispatcher scaffold supports shared timestamp logging and parallel dispatch
- Participant persistence and session-history query implemented
- Initial tests added and passing

## Setup

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 -m src.main
```

## Data Layout (Target)

Session data is stored under:

- `data/Pxxx/participant.json`
- `data/Pxxx/session_yyy/session_meta.json`
- `data/Pxxx/session_yyy/ecg_raw.csv`
- `data/Pxxx/session_yyy/heartbeats.csv`
- `data/Pxxx/session_yyy/feedback_events.csv`
- `data/Pxxx/session_yyy/trigger_log.csv`

## Notes

- The repository is in active migration from legacy modules.
- Full BLE streaming wiring and complete session orchestration are in progress.



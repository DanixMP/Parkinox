# Parkinox Security Operator (`parkinox_sec_op`)

Security monitoring panel for Parkinox. Reuses the same local FastAPI camera/detection stack as `parkinox_op`, but **does not** run gate approval, wallet, or parking session flows.

## Scope

| Feature | Included |
|---------|----------|
| Entry/exit live camera preview (USB / IP RTSP) | Yes |
| FastAPI camera config sync + plate WebSocket alerts | Yes |
| Plate alert feed (live + history, acknowledge) | Yes |
| Gate confirm / wallet / unpaid / season reset | No |
| Django operator login | No (local monitoring station) |

## Run

```bat
cd parkinox_sec_op
flutter pub get --offline
flutter run -d windows
```

Or build: `build_windows.bat`

## Settings

- **FastAPI URL** (default `http://localhost:8002`)
- Entry/exit cameras (USB index or Hikvision RTSP)

Settings are stored under a separate key (`sec_app_settings`) so they do not overwrite `parkinox_op` preferences.

## Architecture

```
parkinox_sec_op ──WS/HTTP──► FastAPI :8002 (same Core as operator)
       │
       └── RTSP preview (channel 102) via media_kit
```

Does **not** modify backend, `parkinox_op`, or other frontends.

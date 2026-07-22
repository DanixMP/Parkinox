# Changelog

All notable changes to Parkinox v3 are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **Remote management cloud (pilot)** — Local-first outbox sync (`SyncOutbox`, UUIDs, `sync_to_cloud`), success-event image capture (`Core/parking_media` + `/success-capture/finalize`), and separate `cloud/` Django reporting replica with Persian RTL HTML dashboard (overview, parked, history, session detail, reports Excel/PDF/CSV, Chart.js analytics, sync health). See [docs/REMOTE_CLOUD.md](docs/REMOTE_CLOUD.md) and [cloud/DEPLOYMENT.md](cloud/DEPLOYMENT.md)
- **Detection fail capture** — Non-invasive Type A/B/C fail store under `Core/data_fails/` with dedup, rate limits, and best-in-window selection; Django `DetectionFail` review APIs; operator panel to correct plates (via `confirm_gate_event`) or mark not-a-plate. See [docs/DETECTION_FAIL_CAPTURE.md](docs/DETECTION_FAIL_CAPTURE.md)
- **Local IP camera pipeline** — FastAPI ingests RTSP streams, runs YOLO detection, serves MJPEG preview, broadcasts `plate_detected` via WebSocket
- **`camera_stream_service.py`** — Entry/exit camera workers with detection cooldown and reconnect logic
- **FastAPI endpoints** — `POST /cameras/config`, `GET /cameras/status`, `GET /cameras/{entry|exit}/mjpeg`, `WebSocket /ws`
- **Operator app** — `RtspPreview` (`media_kit`) for low-latency IP preview, `FastApiCameraApi`, `fastApiDetectionControllerProvider`
- **Hikvision quick-setup** in IP camera settings (channels 101/102)
- **Windows build script** — `parkinox_op/build_windows.bat` with VS 2026 Flutter SDK patch
- **`run_all.bat`** — One-command launcher for FastAPI, Django, and operator app
- **Comprehensive documentation** — `docs/` architecture, API, camera, and getting started guides

### Changed

- **IP camera architecture** — Detection moved from Flutter screenshot loop to local FastAPI (operator PC)
- **Operator dashboard** — IP cameras use direct RTSP sub-stream preview (`media_kit`, channel 102) while FastAPI detects on channel 101
- **Flutter SDK constraints** — Aligned to Flutter 3.35.3 / Dart 3.9.2
- **Django default port** — Development uses port 8001 (FastAPI uses 8002)
- **Root README** — Rewritten with architecture diagrams and professional documentation index

### Fixed

- **Windows CMake build** — Stale cache when project path changes; `flutter clean` guidance
- **Visual Studio 2026** — Flutter SDK mapping for Windows desktop builds
- **IP camera settings** — `TextEditingController` lifecycle bug on rebuild
- **`TextEditingController` in settings** — Persisted URL no longer resets on parent rebuild

---

## [1.0.0] — Initial release

### Added

- Django REST API — accounts, parking, plates, wallets, reports
- Operator Flutter desktop app — dashboard, gate events, plate approval
- Student Flutter mobile app — OTP auth, plates, wallet
- FastAPI YOLOv5 bridge — `/detect`, `/health`, OpenAPI docs
- Django Channels WebSocket — operator panel real-time updates
- Persian plate format support and RTL operator UI
- SQLite local cache for operator plate entries

---

[Unreleased]: https://github.com/your-org/parkinox-v3/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/parkinox-v3/releases/tag/v1.0.0

# Getting Started

Complete setup guide for running Parkinox v3 on a development machine (Windows-focused; Linux/macOS notes included).

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Clone and structure](#clone-and-structure)
3. [FastAPI detection service](#fastapi-detection-service)
4. [Django backend](#django-backend)
5. [Operator Flutter app](#operator-flutter-app)
6. [Student Flutter app](#student-flutter-app)
7. [One-command launch](#one-command-launch)
8. [First-time operator configuration](#first-time-operator-configuration)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required

| Software | Version | Verify |
|----------|---------|--------|
| Python | 3.10 – 3.12 | `python --version` |
| Flutter | ≥ 3.35.3 | `flutter --version` |
| Dart | ≥ 3.9.2 | (bundled with Flutter) |
| Git | Latest | `git --version` |

### Windows-specific

| Software | Purpose |
|----------|---------|
| Visual Studio 2022 or 2026 | Flutter Windows desktop build (Desktop development with C++) |
| FFmpeg | RTSP decoding in OpenCV (add to PATH) |

### Optional

| Software | Purpose |
|----------|---------|
| NVIDIA CUDA + cuDNN | GPU-accelerated YOLO (3–5× faster) |
| PostgreSQL | Production Django database |

### YOLO model weights

Place in `Core/models/`:

- `plateYolo.pt` — plate region detection
- `CharsYolo.pt` — character recognition

Fallback paths are checked in `operator_panel/models/` if local models are missing.

---

## Clone and structure

```bash
git clone <repository-url> Parkinox-v3-M
cd Parkinox-v3-M
```

Top-level launch scripts:

| Script | Action |
|--------|--------|
| `run_all.bat` | Start FastAPI + Django + Operator app |
| `run_fastapi.bat` | FastAPI only |
| `run_django.bat` | Django only |
| `run_flutter.bat` | Operator Flutter app only |

---

## FastAPI detection service

### 1. Create virtual environment

```powershell
cd Core
python -m venv venv
.\venv\Scripts\activate
```

```bash
# Linux / macOS
cd Core
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

PyTorch with CUDA (optional):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 3. Verify models

```bash
python -c "from plate_detector import PlateDetector; d = PlateDetector(); print(d.device)"
```

### 4. Start server

```bash
python fastapi_app.py
```

Server listens on `http://0.0.0.0:8000`

### 5. Health check

```bash
curl http://localhost:8000/health
```

Expected:

```json
{
  "status": "ok",
  "models_loaded": true,
  "device": "cuda",
  "version": "1.0.0"
}
```

Interactive docs: http://localhost:8000/docs

---

## Django backend

### 1. Create virtual environment

```powershell
cd backend
python -m venv env
.\env\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment file

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/macOS
```

Edit `.env` — minimum for development:

```env
SECRET_KEY=dev-secret-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

SQLite is used by default in development — no database setup required.

### 4. Migrate and superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

Use the superuser **phone number** in operator settings (Parkinox uses phone-based operator login).

### 5. Start server (port 8001)

```bash
python manage.py runserver 8001
```

> **Note:** Django runs on **8001** so FastAPI can use **8000**.

### 6. Health check

```bash
curl http://localhost:8001/api/health/
```

---

## Operator Flutter app

### 1. Dependencies

```bash
cd parkinox_op
flutter pub get
```

### 2. Run in debug

```bash
flutter run -d windows
```

Other targets: `flutter devices` then `flutter run -d <device_id>`

### 3. Windows release build

```bat
build_windows.bat
```

Output: `build\windows\x64\runner\Release\parkinox_op.exe`

**VS 2026 note:** `build_windows.bat` patches the Flutter SDK if needed for Visual Studio 2026 support. Update `FLUTTER_ROOT` in the script if your Flutter install path differs.

### 4. Configure endpoints

In the app: **Settings → Server addresses**

| Field | Default |
|-------|---------|
| FastAPI | `http://localhost:8000` |
| Django API | `http://localhost:8001/api` |
| WebSocket | `ws://localhost:8001/ws/panel/` |
| Superuser phone | Your Django superuser phone |

---

## Student Flutter app

```bash
cd parkinox_stdn
flutter pub get
flutter run
```

Point the student app to the same Django API base URL configured in its settings/constants.

---

## One-command launch

From repository root on Windows:

```bat
run_all.bat
```

Sequence:

1. FastAPI starts in new terminal (port 8000)
2. 3-second wait for model load
3. Django starts in new terminal (port 8001)
4. Operator app launches (builds Windows exe if missing)

---

## First-time operator configuration

1. **Start all services** (`run_all.bat`)
2. **Settings → Server addresses** — verify URLs, save
3. **Settings → Superuser phone** — enter Django superuser phone
4. **Login** — 6-digit operator PIN / admin password dialog
5. **Settings → Cameras**
   - Entry: enable, choose USB / Webcam / IP Camera
   - For Hikvision IP: use quick-setup or paste RTSP URL
   - Test connection → Save
6. **Dashboard** — verify LIVE preview and wait for plate detection

---

## Troubleshooting

### FastAPI: models not loaded

```
GET /health → models_loaded: false
```

- Confirm `Core/models/plateYolo.pt` and `CharsYolo.pt` exist
- Check PyTorch install: `python -c "import torch; print(torch.__version__)"`
- Review terminal traceback on startup

### FastAPI: IP camera won't connect

- Test RTSP in VLC: `rtsp://user:pass@ip:554/Streaming/Channels/101`
- Ensure FFmpeg is on PATH (OpenCV backend)
- Try sub-stream channel `102` (lower bandwidth)
- Check `GET http://localhost:8000/cameras/status`

### Flutter: no MJPEG preview

- FastAPI must be running
- Camera config must be synced (`POST /cameras/config` — happens on save)
- URL must match: `http://localhost:8000/cameras/entry/mjpeg`
- Firewall blocking localhost HTTP

### Flutter: plates detected but no approval UI

- Check FastAPI WS connected: settings bootstrap on dashboard load
- FastAPI terminal should log `Plate detected: ...`
- Verify `camera_id` is `entry_camera` or `exit_camera`

### Flutter: Windows build fails (CMake / VS)

- Run `flutter clean` in `parkinox_op`
- Delete stale `build/` if project was moved
- Run `build_windows.bat` (applies VS 2026 patch)
- Confirm "Desktop development with C++" workload in Visual Studio Installer

### Django: operator can't connect

- Django must be on port **8001** (not 8000)
- Create superuser with phone number
- Enter same phone in operator settings
- Check `ws://localhost:8001/ws/panel/` with valid JWT

### Django: CORS errors

- Add Flutter origin to `CORS_ALLOWED_ORIGINS` in `.env`
- For desktop apps, ensure `127.0.0.1` is in `ALLOWED_HOSTS`

### pub get SDK version error

`parkinox_op` requires:

```yaml
sdk: '>=3.9.2 <4.0.0'
flutter: '>=3.35.3'
```

Upgrade Flutter or adjust `pubspec.yaml` to match your SDK.

---

## Next steps

- [CAMERA_INTEGRATION.md](CAMERA_INTEGRATION.md) — Hikvision RTSP deep dive
- [API_OVERVIEW.md](API_OVERVIEW.md) — endpoint reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — system design
- [../backend/DEPLOYMENT_UBUNTU_24.md](../backend/DEPLOYMENT_UBUNTU_24.md) — production deployment

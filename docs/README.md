# Parkinox v3 — Documentation

Welcome to the technical documentation for **Parkinox v3**, a smart university parking platform with Iranian license plate recognition.

## Who should read what?

| Audience | Start here |
|----------|------------|
| **New developers** | [GETTING_STARTED.md](GETTING_STARTED.md) → [ARCHITECTURE.md](ARCHITECTURE.md) |
| **Operator / IT setup** | [GETTING_STARTED.md](GETTING_STARTED.md) → [CAMERA_INTEGRATION.md](CAMERA_INTEGRATION.md) |
| **Backend engineers** | [API_OVERVIEW.md](API_OVERVIEW.md) → [../backend/DEPLOYMENT_UBUNTU_24.md](../backend/DEPLOYMENT_UBUNTU_24.md) |
| **AI / detection work** | [../Core/FASTAPI_README.md](../Core/FASTAPI_README.md) → [CAMERA_INTEGRATION.md](CAMERA_INTEGRATION.md) |
| **Flutter developers** | [ARCHITECTURE.md](ARCHITECTURE.md) → `parkinox_op/lib/` source |

## Document index

### Core documentation

| File | Contents |
|------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Multi-tier design, detection pipeline, WebSocket flows |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Prerequisites, installation, first run, troubleshooting |
| [API_OVERVIEW.md](API_OVERVIEW.md) | FastAPI and Django REST/WebSocket reference |
| [CAMERA_INTEGRATION.md](CAMERA_INTEGRATION.md) | USB, webcam, Hikvision RTSP, MJPEG, config sync |

### Module-specific docs

| Location | Contents |
|----------|----------|
| [../Core/FASTAPI_README.md](../Core/FASTAPI_README.md) | FastAPI detection service |
| [../Core/README.md](../Core/README.md) | Core utilities overview |
| [../backend/README.md](../backend/README.md) | Django backend setup |
| [../backend/DEPLOYMENT_UBUNTU_24.md](../backend/DEPLOYMENT_UBUNTU_24.md) | Ubuntu 24 production deployment |
| [../backend/accounts/AUTH_README.md](../backend/accounts/AUTH_README.md) | Authentication flows |

## System at a glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPERATOR PC (local)                       │
│  ┌──────────────┐    WS/MJPEG/HTTP    ┌──────────────────────┐ │
│  │ parkinox_op  │ ◄──────────────────►│ FastAPI :8000 (Core) │ │
│  │   Flutter    │                     │ YOLOv5 + OpenCV RTSP │ │
│  └──────┬───────┘                     └──────────┬───────────┘ │
│         │                                        │              │
│         │              IP / USB Cameras          │              │
│         └────────────────────────────────────────┘              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / WSS (JWT)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REMOTE SERVER                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Django :8001 — REST API, WebSocket, PostgreSQL/SQLite    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ parkinox_stdn   │
                    │ Student mobile  │
                    └─────────────────┘
```

## Default ports

| Port | Service |
|------|---------|
| 8000 | FastAPI (local detection) |
| 8001 | Django (remote backend) |

## Getting help

1. Check [GETTING_STARTED.md — Troubleshooting](GETTING_STARTED.md#troubleshooting)
2. Verify FastAPI health: `GET http://localhost:8000/health`
3. Verify Django health: `GET http://localhost:8001/api/health/`
4. Review FastAPI logs in the Core terminal window
5. Review Django logs in the backend terminal window

## Changelog

See [../CHANGELOG.md](../CHANGELOG.md) for release notes.

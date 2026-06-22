# API Overview

Reference for Parkinox v3 HTTP and WebSocket APIs. The system exposes two independent services on different ports.

| Service | Base URL | Auth |
|---------|----------|------|
| **FastAPI** (local) | `http://localhost:8000` | None (localhost trust) |
| **Django** (remote) | `http://localhost:8001/api` | JWT Bearer |

---

## FastAPI — Local detection service

Interactive documentation: **http://localhost:8000/docs**

### Health & info

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | API metadata |
| `GET` | `/health` | Model load status, device (cpu/cuda) |
| `GET` | `/models/info` | Model paths and confidence threshold |

**`GET /health` response:**

```json
{
  "status": "ok",
  "models_loaded": true,
  "device": "cuda",
  "version": "1.0.0"
}
```

---

### Plate detection

| Method | Path | Content-Type | Description |
|--------|------|--------------|-------------|
| `POST` | `/detect` | `multipart/form-data` | Upload image field `image` |
| `POST` | `/detect/file` | `application/json` | Server-side file path (testing) |

**`POST /detect` response (success):**

```json
{
  "success": true,
  "plate": "12 ب 345 17",
  "confidence": 0.85,
  "char_confidence": 0.78,
  "num_characters": 8,
  "bbox": [120, 80, 420, 160],
  "message": "Plate detected successfully"
}
```

**`POST /detect` response (no plate):**

```json
{
  "success": false,
  "plate": null,
  "confidence": 0.0,
  "message": "No plate detected"
}
```

| Status | Meaning |
|--------|---------|
| 200 | Processed (may have no plate) |
| 400 | Invalid image |
| 503 | Models not loaded |

---

### IP camera management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/cameras/config` | Push entry/exit RTSP config from Flutter |
| `GET` | `/cameras/status` | Connection state per slot |
| `GET` | `/cameras/entry/mjpeg` | MJPEG preview stream (entry) |
| `GET` | `/cameras/exit/mjpeg` | MJPEG preview stream (exit) |

**`POST /cameras/config` body:**

```json
{
  "entry_enabled": true,
  "exit_enabled": false,
  "entry_url": "rtsp://admin:pass@192.168.1.64:554/Streaming/Channels/101",
  "exit_url": null
}
```

**`GET /cameras/status` response:**

```json
{
  "entry": {
    "enabled": true,
    "url": "rtsp://...",
    "connected": true,
    "error": null
  },
  "exit": {
    "enabled": false,
    "url": null,
    "connected": false,
    "error": null
  }
}
```

MJPEG response: `Content-Type: multipart/x-mixed-replace; boundary=frame`

---

### FastAPI WebSocket

**URL:** `ws://localhost:8000/ws`

#### Server → client messages

**Connected:**

```json
{ "type": "connected" }
```

**Plate detected:**

```json
{
  "type": "plate_detected",
  "data": {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "plate_number": "12 ب 345 17",
    "camera_id": "entry_camera",
    "confidence": 0.87,
    "char_confidence": 0.82,
    "timestamp": "2026-06-22T10:30:00+00:00",
    "status": "unregistered",
    "bbox": [100, 200, 300, 250]
  }
}
```

#### Client → server messages

```json
{ "type": "ping" }
```

Response: `{ "type": "pong" }`

Optional config push:

```json
{
  "type": "camera_config",
  "data": {
    "entry_enabled": true,
    "entry_url": "rtsp://..."
  }
}
```

---

## Django — Remote backend API

Base path: `/api/`

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login/` | Operator/admin login |
| `POST` | `/auth/operator-login/` | Operator PIN login |
| `POST` | `/auth/refresh/` | JWT refresh token |
| `POST` | `/auth/student/otp/send/` | Send student OTP |
| `POST` | `/auth/student/otp/verify/` | Verify OTP |
| `POST` | `/auth/student/register/` | Student registration |
| `GET` | `/auth/student/me/` | Student profile |

**JWT usage:**

```
Authorization: Bearer <access_token>
```

### Parking

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/parking/rates/` | Current rate configuration |
| `POST` | `/parking/gate-events/` | Create gate entry/exit event |
| `GET` | `/parking/plates/lookup/` | Lookup plate registration |
| `GET` | `/parking/sessions/` | List parked vehicles |
| `GET` | `/parking/sessions/<id>/` | Session detail |
| `POST` | `/parking/sessions/<id>/cash-payment/` | Record cash payment |
| `POST` | `/parking/sessions/<id>/waive-fee/` | Waive parking fee |

**Gate event example:**

```json
POST /api/parking/gate-events/
{
  "camera_id": "entry",
  "direction": "entry",
  "plate_raw": "12ب345-17",
  "plate_confirmed": "12ب345-17",
  "confidence_score": 0.87,
  "was_edited": false,
  "was_auto_approved": true
}
```

### Plates

| Method | Path | Description |
|--------|------|-------------|
| — | `/plates/` | Plate registry endpoints |

### Wallets

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/wallets/student/demo-topup/` | Demo student top-up |
| `POST` | `/wallets/operator/topup-by-plate/` | Operator top-up by plate |

### Reports

| Method | Path | Description |
|--------|------|-------------|
| — | `/reports/` | Reporting endpoints |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health/` | Django health check |

---

## Django WebSocket — Operator panel

**URL:** `ws://<host>:8001/ws/panel/?token=<JWT_ACCESS_TOKEN>`

Implemented in `backend/parking/consumers.py` (`ParkingConsumer`).

### Connection

- JWT required in query string
- Close code `4001` if token missing or invalid

### Message types (representative)

| Type | Direction | Purpose |
|------|-----------|---------|
| Heartbeat ping/pong | Both | Keep-alive |
| Gate event confirmation | Client → Server | Confirm detected plate |
| Gate event rejection | Client → Server | Reject detection |
| Statistics update | Server → Client | Live parking stats |
| Cash payment | Client → Server | Record payment at exit |

See `ParkingConsumer` source for full message schema.

---

## Error conventions

### FastAPI

```json
{
  "detail": "Human-readable error message"
}
```

### Django REST

```json
{
  "detail": "Error message"
}
```

or field-level validation errors per DRF standard.

---

## Rate limits & performance

| Endpoint | Typical latency |
|----------|-----------------|
| `POST /detect` (GPU) | 50–150 ms |
| `POST /detect` (CPU) | 200–500 ms |
| IP camera detection | Every 3 seconds per stream |
| MJPEG frame rate | ~20 fps (50 ms sleep in generator) |

---

## Client configuration (Flutter operator)

Default settings stored in `SettingsModel`:

| Field | Default |
|-------|---------|
| `fastApiUrl` | `http://localhost:8000` |
| `djangoApiUrl` | `http://localhost:8001/api` |
| `wsUrl` | `ws://localhost:8001/ws/panel/` |

Derived URLs in `FastApiCameraApi`:

- WebSocket: `ws://localhost:8000/ws`
- Entry MJPEG: `http://localhost:8000/cameras/entry/mjpeg`
- Exit MJPEG: `http://localhost:8000/cameras/exit/mjpeg`

---

## Further reading

- [CAMERA_INTEGRATION.md](CAMERA_INTEGRATION.md)
- [../Core/FASTAPI_README.md](../Core/FASTAPI_README.md)
- [../backend/accounts/AUTH_README.md](../backend/accounts/AUTH_README.md)

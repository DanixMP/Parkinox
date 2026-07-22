# Camera Integration

Guide for connecting USB webcams, built-in cameras, and IP cameras (Hikvision and RTSP-compatible) to the Parkinox operator dashboard.

---

## Overview

Parkinox uses a **split architecture** for cameras:

| Camera type | Preview | Detection |
|-------------|---------|-----------|
| **USB / Webcam** | Flutter `CameraPreview` | Flutter captures frame → `POST /detect` |
| **IP (RTSP)** | Flutter `RtspPreview` (`media_kit`) | FastAPI OpenCV thread → YOLO → WebSocket |

IP cameras use split channels in the operator PC:
- **FastAPI detection:** RTSP channel **101** (main stream)
- **Flutter preview:** RTSP channel **102** (sub-stream via `media_kit`)

FastAPI still performs all YOLO detection and pushes `plate_detected` over WebSocket.

```
┌─────────────┐  RTSP 101   ┌──────────────┐
│  Hikvision  │────────────►│   FastAPI    │
│  IP Camera  │             │  (YOLO + WS) │
└──────┬──────┘             └──────┬───────┘
       │ RTSP 102                 │ plate_detected WS
       ▼                          ▼
┌─────────────┐             ┌─────────────┐
│ parkinox_op │◄────────────│   Flutter   │
│ RtspPreview │             │ approval UI │
└─────────────┘             └─────────────┘
```

---

## USB and webcam

### Setup

1. **Settings → Cameras → Entry or Exit**
2. Enable the camera
3. Select **USB** or **Webcam**
4. Choose device from the list
5. Return to **Dashboard**

### How it works

- `CameraPanel` initializes `CameraController` with `ResolutionPreset.medium`
- `continuous_detection_provider` polls every 3 seconds
- Each poll: `takePicture()` → `PlateDetectionService.detectPlate()` → FastAPI `/detect`

### Tips

- Use good lighting; avoid glare on plate
- Position camera at slight angle (15–30°) for better OCR
- Only one app should access the camera at a time

---

## IP cameras (RTSP)

### Supported devices

Any RTSP-compatible camera. **Hikvision** (e.g. DS-2CD2183G2-LIS2U) is tested with ISAPI streaming paths.

### Hikvision RTSP URL format

```
rtsp://<username>:<password>@<ip>:554/Streaming/Channels/<channel>
```

| Channel | Stream | Use case |
|---------|--------|----------|
| `101` | Main (HD) | Best detection accuracy |
| `102` | Sub (SD) | Lower bandwidth, faster on slow networks |

**Example:**

```
rtsp://admin:YourPassword@192.168.1.64:554/Streaming/Channels/101
```

### Settings UI workflow

1. **Settings → Cameras** — enable entry or exit camera
2. Select **IP Camera**
3. Optional: enable **Hikvision quick setup**
   - Enter IP, username, password, channel
   - Click **Build RTSP URL**
4. Click **Test connection**
   - Flutter syncs detection URL to FastAPI (`syncTestSlot`) on channel 101
   - Preview plays via `RtspPreview` on channel 102
5. Click **Save settings**
   - Persists URL; full config syncs via `POST /cameras/config`

### Dashboard workflow

When IP camera is enabled on dashboard:

1. `CameraPanel` syncs config to FastAPI
2. `RtspPreview` plays the configured RTSP URL on channel 102
3. `fastApiDetectionController` receives `plate_detected` on `ws://localhost:8002/ws`
4. Approval panel shows plate with countdown

---

## FastAPI camera API

### Configure cameras

```http
POST http://localhost:8002/cameras/config
Content-Type: application/json

{
  "entry_enabled": true,
  "exit_enabled": true,
  "entry_url": "rtsp://admin:pass@192.168.1.64:554/Streaming/Channels/101",
  "exit_url": "rtsp://admin:pass@192.168.1.65:554/Streaming/Channels/101"
}
```

### Check status

```http
GET http://localhost:8002/cameras/status
```

```json
{
  "entry": {
    "enabled": true,
    "url": "rtsp://...",
    "connected": true,
    "error": null
  },
  "exit": { ... }
}
```

### Optional MJPEG debug endpoint

FastAPI still exposes `/cameras/{slot}/mjpeg` for backend diagnostics, but operator preview uses `RtspPreview`.

---

## WebSocket detection events

When YOLO detects a plate on an IP stream:

```json
{
  "type": "plate_detected",
  "data": {
    "event_id": "uuid",
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

| `camera_id` | Dashboard slot |
|-------------|----------------|
| `entry_camera` | Entry approval panel |
| `exit_camera` | Exit approval panel |

**Cooldown:** Same plate on the same camera is not re-emitted for 10 seconds.

**Detection interval:** One inference attempt every 3 seconds per active stream.

---

## FFmpeg requirement

OpenCV uses FFmpeg for RTSP on Windows. Install FFmpeg and add to PATH:

```powershell
ffmpeg -version
```

Verify RTSP outside Parkinox:

```bash
ffplay -rtsp_transport tcp "rtsp://admin:pass@192.168.1.64:554/Streaming/Channels/101"
```

Or use VLC → Open Network Stream.

### RTSP transport

If connection is unstable, Hikvision often works better with TCP. FastAPI sets `OPENCV_FFMPEG_CAPTURE_OPTIONS` with TCP transport before OpenCV loads; for problematic networks, use sub-stream (channel 102) or network VLAN isolation for cameras.

### Dual RTSP clients (H.264 decode errors, no detections)

Parkinox must avoid two consumers on the **same channel**. Use:
- FastAPI on **101**
- Flutter preview on **102**

| Symptom | Likely cause |
|---------|----------------|
| `Picture timing SEI`, `error while decoding MB` in logs | Another app connects to channel 101 (VLC/ffplay/old test tool) |
| Preview works but no `plate_detected` | FastAPI stream 101 unstable or competing clients |
| `connected: true` but flaky preview | Too many clients on camera; check channel split |

**Fix:** Close VLC/ffplay/browser tests. Keep FastAPI on 101 and Flutter preview on 102.

```bash
ffplay -rtsp_transport tcp "rtsp://admin:pass@192.168.1.64:554/Streaming/Channels/102"
```

Then stop `ffplay` before starting Parkinox.

---

## Troubleshooting

### Preview shows loading spinner forever

| Check | Action |
|-------|--------|
| FastAPI running? | `curl http://localhost:8002/health` |
| Camera enabled? | `GET /cameras/status` → `enabled: true` |
| RTSP valid? | Test in VLC |
| Config synced? | Save settings or toggle camera on dashboard |
| MJPEG URL | Must be `entry` or `exit` slot matching settings |

### `connected: false` in status

- Wrong password in RTSP URL
- Camera offline or wrong IP
- Port 554 blocked by firewall
- Too many concurrent RTSP clients (Hikvision limit) — close VLC/test streams

### Detection works in `/detect` but not on IP stream

- Check FastAPI logs for `Camera [entry] plate detected`
- Ensure stream is running (preview working)
- Try channel 101 vs 102
- Plate may be too small in frame — adjust camera angle/zoom
- Lower `conf_threshold` in `PlateDetector` if needed

### WebSocket connected but no UI update

- Confirm `camera_id` is `entry_camera` or `exit_camera`
- Check Flutter logs for WebSocket parse errors
- Plate may be in 10-second cooldown after previous detection

### Credentials in URLs

RTSP URLs contain passwords. They are stored in local operator settings and sent only to **local** FastAPI. Do not log or commit these URLs.

---

## Security checklist

- [ ] Change default Hikvision `admin` password
- [ ] Isolate cameras on dedicated VLAN
- [ ] FastAPI bound to localhost or operator LAN only
- [ ] Do not expose port 8002 to the public internet
- [ ] Use strong passwords in RTSP URLs

---

## Related documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — detection pipeline design
- [API_OVERVIEW.md](API_OVERVIEW.md) — full endpoint reference
- [GETTING_STARTED.md](GETTING_STARTED.md) — installation

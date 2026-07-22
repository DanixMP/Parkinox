# Detection Fail Capture and Operator Review

Non-invasive layer around the existing plate pipeline. Valid detections continue unchanged; failed outcomes are captured for training and operator correction.

## Constraint

Do **not** weaken Iranian plate validation or auto-open the gate on rejected OCR.

Existing happy path remains:

```text
plateYolo.pt → CharsYolo.pt → validate_detection_plate()
  → plate_detected → operator/auto confirm → confirm_gate_event()
```

## Failure types

| Type | Code | Meaning |
|------|------|---------|
| A | `ocr_invalid_format` | Plate bbox found; OCR text fails Iranian format rules |
| B | `ocr_empty` | Plate bbox found; OCR empty / below confidence |
| C | `operator_confirmed_miss` | Operator Capture miss (visible plate, no bbox) |
| D | (metric only) | Transient: fail then valid emit within ~5s on same camera |

## Flow

```text
Camera frame  OR  HTML test upload (POST /detect)
    ↓
Existing plate detection architecture
    ↓
Valid plate ───────────────→ Existing normal application flow
    ↓
Failed or unreadable plate (Type A/B)
    ↓
FailCaptureStore (dedup / rate limit / best-in-window)
    ↓                    (uploads use immediate=True)
Core/data_fails/YYYY-MM-DD/<uuid>/{full.jpg,scene_b.jpg?,crop.jpg?,meta.json}
    ↓
POST Django /api/parking/detection-fails/ingest/
    ↓
Operator review panel (parkinox_op) — 3 images when scene B present
    ↓
Correct plate ──→ confirm_gate_event() + DetectionFail.gate_event link
    ↓
“Not a plate” ──→ status=not_a_plate (training only, no parking records)
```

`POST /detect` (test UI / upload) also archives Type A/B fails with
`fail_captured` / `fail_capture_id` in the JSON response. Valid plates are
still never auto-injected when OCR is invalid.

## Disk layout

```text
Core/data_fails/
  YYYY-MM-DD/
    <uuid>/
      full.jpg       # scene A (detection frame)
      scene_b.jpg    # optional second scene
      crop.jpg       # omitted for Type C / no bbox
      meta.json      # + has_scene_b, scene_b_source, scene_b_delay_ms, scene_b_sharpness
```

### Scene B rules

| Source | Behavior |
|--------|----------|
| Live RTSP | Same worker grabs a frame ~500ms later (`FAIL_CAPTURE_SCENE_B_DELAY_MS`); keep if Laplacian variance ≥ 25 and not near-identical to scene A; `scene_b_source: rtsp_delayed` |
| Upload `/detect` | If bbox exists: padded ROI around plate; `scene_b_source: padded_bbox` |
| Otherwise | Omit `scene_b.jpg`; `has_scene_b: false` |

`full.jpg` remains scene A for backward compatibility. Ingest may include optional multipart `scene_b_image`.

## Dedup and rate limits (Core)

| Setting | Env var | Default |
|---------|---------|---------|
| Per-camera cooldown | `FAIL_CAPTURE_COOLDOWN_SEC` | `3` |
| Max writes / minute / camera | `FAIL_CAPTURE_MAX_PER_MINUTE` | `10` |
| Best-candidate window | `FAIL_CAPTURE_BEST_WINDOW_SEC` | `1.5` |
| BBox IoU duplicate threshold | `FAIL_CAPTURE_IOU_THRESHOLD` | `0.7` |
| Type D window | `FAIL_CAPTURE_TRANSIENT_WINDOW_SEC` | `5` |
| Scene B delay (RTSP) | `FAIL_CAPTURE_SCENE_B_DELAY_MS` | `500` |

Near-duplicates: average-hash of crop (or full frame) + bbox IoU within cooldown.

## Django ingest

| Env | Default |
|-----|---------|
| `DJANGO_BASE_URL` | `http://127.0.0.1:8001` |
| `DETECTION_FAIL_INGEST_TOKEN` | `dev-fail-ingest-token` |

Header: `X-Fail-Ingest-Token`.

Media files are stored under Django `MEDIA_ROOT` for the operator UI.

## API

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/parking/detection-fails/ingest/` | Ingest token |
| GET | `/api/parking/detection-fails/?status=pending&date=YYYY-MM-DD&offset=0&limit=50` | Operator JWT |
| GET | `/api/parking/detection-fails/<uuid>/` | Operator JWT |
| POST | `/api/parking/detection-fails/<uuid>/review/` | Operator JWT |
| GET | `/api/parking/detection-fails/metrics/` | Operator JWT |
| POST | FastAPI `/cameras/{entry\|exit}/capture-miss` | Local |
| GET | FastAPI `/metrics/detection-fails` | Local |

### List query params

| Param | Default | Notes |
|-------|---------|-------|
| `date` | Tehran today | Calendar day in `Asia/Tehran` on `captured_at` (fallback `created_at`) |
| `status` | (none) | `pending` / `corrected` / `not_a_plate` |
| `offset` | `0` | Pagination offset |
| `limit` | `50` (max 200) | Page size — does **not** drop unread records |

Response: `{ count, results, offset, limit, has_more, date }` where `count` is the **total** matching rows.

### Review body

```json
{ "action": "correct", "plate_confirmed": "۱۲ ب ۳۴۵ ۶۷" }
```

or

```json
{ "action": "not_a_plate" }
```

Corrected plates call the shared `confirm_gate_event(..., occurred_at=captured_at)` so GateEvent / session timestamps use the **original capture time**. `reviewed_at` / `reviewed_by` store the operator review time. Conflicting historical inserts return HTTP 400 and leave the fail `pending`.

## Operator UI

- Toolbar → **بازبینی تشخیص‌های ناموفق** (`/failed-detections`)
- Camera panel orange flag → Type C Capture miss
- Date picker (same pattern as archive reports); status chips; **بارگذاری بیشتر** for pagination
- Review images: **فریم ۱ (لحظه تشخیص)** · **فریم ۲** (or “فقط یک فریم موجود است”) · **برش پلاک** (emphasized for typing)
- Enter plate via `IranPlateInput`, or mark not-a-plate
- **پایان فصل و شروع مجدد** reuses the Settings End-of-Season flow (`POST /parking/season/reset/`)

## Metrics (Core `GET /metrics/detection-fails`)

- `plate_bbox_hits`
- `ocr_empty`
- `ocr_invalid_format`
- `ocr_valid_emitted`
- `operator_confirmed_miss`
- `operator_corrected_plate` / `operator_marked_not_plate` (Django metrics endpoint)
- `duplicate_fail_skipped`
- `fail_capture_rate_limited`
- `transient_retry_success` (Type D)

## Migrations

```bash
cd backend
python manage.py migrate parking
```

## Created / modified files

### Created

- `Core/fail_capture.py`
- `Core/fail_metrics.py`
- `Core/test_fail_capture.py`
- `backend/parking/detection_fail_service.py`
- `backend/parking/migrations/0005_detectionfail.py`
- `backend/parking/migrations/0006_detectionfail_scene_b.py`
- `backend/parking/test_detection_fail.py`
- `docs/DETECTION_FAIL_CAPTURE.md`
- `parkinox_op/lib/data/models/detection_fail_dto.dart`
- `parkinox_op/lib/providers/failed_detection_provider.dart`
- `parkinox_op/lib/ui/review/failed_detections_screen.dart`
- `parkinox_op/test/detection_fail_dto_test.dart`

### Modified

- `Core/plate_detector.py` — Type B empty-OCR metadata only
- `Core/camera_stream_service.py` — fail capture hooks + capture-miss
- `Core/fastapi_app.py` — capture-miss + metrics endpoints
- `backend/parking/models.py` — `DetectionFail`
- `backend/parking/views.py` / `urls.py`
- `backend/parking/gate_event_service.py` — optional `plate_image_path`
- `backend/config/settings/base.py` — `MEDIA_*`, ingest token
- `backend/config/urls.py` — media serving in DEBUG
- `parkinox_op/lib/data/api/api_client.dart`
- `parkinox_op/lib/data/services/fastapi_camera_api.dart`
- `parkinox_op/lib/core/router.dart`
- `parkinox_op/lib/ui/dashboard/components/top_toolbar.dart`
- `parkinox_op/lib/ui/dashboard/components/camera_panel.dart`
- `CHANGELOG.md`
- `docs/README.md`

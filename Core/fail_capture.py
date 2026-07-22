"""
Failure capture layer for plate detection.

Observes Type A/B/C failures, deduplicates, rate-limits, picks best-in-window,
writes Core/data_fails/YYYY-MM-DD/<uuid>/{full,crop,meta}, then optionally
ingests to Django. Does not alter YOLO / validation / gate-open logic.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

import cv2
import numpy as np

from fail_metrics import fail_metrics

logger = logging.getLogger(__name__)

FAIL_TYPE_OCR_INVALID = "ocr_invalid_format"
FAIL_TYPE_OCR_EMPTY = "ocr_empty"
FAIL_TYPE_OPERATOR_MISS = "operator_confirmed_miss"

DEFAULT_COOLDOWN_SEC = float(os.environ.get("FAIL_CAPTURE_COOLDOWN_SEC", "3"))
DEFAULT_MAX_PER_MINUTE = int(os.environ.get("FAIL_CAPTURE_MAX_PER_MINUTE", "10"))
DEFAULT_BEST_WINDOW_SEC = float(os.environ.get("FAIL_CAPTURE_BEST_WINDOW_SEC", "1.5"))
DEFAULT_IOU_THRESHOLD = float(os.environ.get("FAIL_CAPTURE_IOU_THRESHOLD", "0.7"))
TRANSIENT_WINDOW_SEC = float(os.environ.get("FAIL_CAPTURE_TRANSIENT_WINDOW_SEC", "5.0"))
SCENE_B_DELAY_MS = int(os.environ.get("FAIL_CAPTURE_SCENE_B_DELAY_MS", "500"))
SCENE_B_MIN_SHARPNESS = float(os.environ.get("FAIL_CAPTURE_SCENE_B_MIN_SHARPNESS", "25"))
SCENE_B_HASH_HAMMING_MAX = int(os.environ.get("FAIL_CAPTURE_SCENE_B_HASH_HAMMING_MAX", "6"))

DATA_FAILS_ROOT = Path(__file__).resolve().parent / "data_fails"

FrameProvider = Callable[[], Optional[np.ndarray]]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def crop_from_bbox(
    frame: np.ndarray,
    bbox: Optional[list],
    pad: int = 10,
) -> Optional[np.ndarray]:
    if frame is None or not bbox or len(bbox) < 4:
        return None
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
    x1p = max(0, x1 - pad)
    y1p = max(0, y1 - pad)
    x2p = min(w, x2 + pad)
    y2p = min(h, y2 + pad)
    if x2p <= x1p or y2p <= y1p:
        return None
    crop = frame[y1p:y2p, x1p:x2p]
    if crop.size == 0:
        return None
    return crop


def padded_context_from_bbox(
    frame: np.ndarray,
    bbox: Optional[list],
) -> Optional[np.ndarray]:
    """Wider plate context for upload Scene B (not a true second moment)."""
    if frame is None or not bbox or len(bbox) < 4:
        return None
    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    pad = max(40, int(0.35 * max(bw, bh)))
    return crop_from_bbox(frame, bbox, pad=pad)


def sharpness_score(image: Optional[np.ndarray]) -> float:
    if image is None or image.size == 0:
        return 0.0
    gray = (
        cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if len(image.shape) == 3
        else image
    )
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def average_hash(image: Optional[np.ndarray], hash_size: int = 8) -> str:
    """Simple average hash for near-duplicate detection."""
    if image is None or image.size == 0:
        return ""
    gray = (
        cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if len(image.shape) == 3
        else image
    )
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    avg = float(resized.mean())
    bits = (resized >= avg).flatten()
    # Pack to hex
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    width = (hash_size * hash_size + 3) // 4
    return f"{value:0{width}x}"


def hamming_distance_hex(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def bbox_iou(a: Optional[list], b: Optional[list]) -> float:
    if not a or not b or len(a) < 4 or len(b) < 4:
        return 0.0
    ax1, ay1, ax2, ay2 = map(float, a[:4])
    bx1, by1, bx2, by2 = map(float, b[:4])
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def candidate_score(plate_confidence: float, sharpness: float) -> float:
    # Normalize sharpness roughly into 0..1 (Laplacian var often 0..500+ for plates)
    sharp_norm = min(1.0, max(0.0, sharpness / 400.0))
    return float(plate_confidence) * 0.6 + sharp_norm * 0.4


def direction_from_camera_id(camera_id: str) -> str:
    cid = (camera_id or "").lower()
    if "exit" in cid:
        return "exit"
    return "entry"


@dataclass
class FailCandidate:
    fail_type: str
    frame: np.ndarray
    camera_id: str
    raw_ocr: Optional[str] = None
    validation_error: Optional[str] = None
    plate_confidence: float = 0.0
    char_confidence: float = 0.0
    bbox: Optional[list] = None
    crop: Optional[np.ndarray] = None
    sharpness: float = 0.0
    image_hash: str = ""
    score: float = 0.0
    submitted_at: float = field(default_factory=time.time)


@dataclass
class _CameraWindow:
    best: Optional[FailCandidate] = None
    timer: Optional[threading.Timer] = None
    recent_hashes: list[tuple[float, str, Optional[list]]] = field(default_factory=list)
    write_times: list[float] = field(default_factory=list)
    last_fail_at: float = 0.0


class FailCaptureStore:
    """Dedup + rate-limit + best-window fail capture to disk (+ Django ingest)."""

    def __init__(
        self,
        root: Optional[Path] = None,
        cooldown_sec: float = DEFAULT_COOLDOWN_SEC,
        max_per_minute: int = DEFAULT_MAX_PER_MINUTE,
        best_window_sec: float = DEFAULT_BEST_WINDOW_SEC,
        iou_threshold: float = DEFAULT_IOU_THRESHOLD,
        ingest_callback: Optional[Callable[[Path, dict], None]] = None,
    ):
        self.root = Path(root) if root else DATA_FAILS_ROOT
        self.cooldown_sec = cooldown_sec
        self.max_per_minute = max_per_minute
        self.best_window_sec = best_window_sec
        self.iou_threshold = iou_threshold
        self.ingest_callback = ingest_callback
        self.scene_b_delay_ms = SCENE_B_DELAY_MS
        self.scene_b_min_sharpness = SCENE_B_MIN_SHARPNESS
        self._lock = threading.Lock()
        self._cameras: dict[str, _CameraWindow] = {}
        self._frame_sources: dict[str, FrameProvider] = {}
        self._ingest_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="fail-ingest",
        )

    def register_frame_source(self, camera_id: str, provider: FrameProvider) -> None:
        """Register live RTSP frame provider for delayed Scene B capture."""
        with self._lock:
            self._frame_sources[camera_id] = provider

    def unregister_frame_source(self, camera_id: str) -> None:
        with self._lock:
            self._frame_sources.pop(camera_id, None)

    def _cam(self, camera_id: str) -> _CameraWindow:
        if camera_id not in self._cameras:
            self._cameras[camera_id] = _CameraWindow()
        return self._cameras[camera_id]

    def note_recent_fail(self, camera_id: str) -> None:
        with self._lock:
            self._cam(camera_id).last_fail_at = time.time()

    def note_valid_emit(self, camera_id: str) -> None:
        """Track Type D: valid plate shortly after a fail on same camera."""
        fail_metrics.inc("ocr_valid_emitted")
        with self._lock:
            last = self._cam(camera_id).last_fail_at
        if last and (time.time() - last) <= TRANSIENT_WINDOW_SEC:
            fail_metrics.inc("transient_retry_success")

    def submit(
        self,
        *,
        fail_type: str,
        frame: np.ndarray,
        camera_id: str,
        raw_ocr: Optional[str] = None,
        validation_error: Optional[str] = None,
        plate_confidence: float = 0.0,
        char_confidence: float = 0.0,
        bbox: Optional[list] = None,
        immediate: bool = False,
    ) -> Optional[Path]:
        """
        Queue or write a fail capture.

        Returns the output directory when a write happens immediately
        (``immediate=True`` or Type C). Deferred best-window writes return None.
        """
        if frame is None or frame.size == 0:
            return None

        crop = crop_from_bbox(frame, bbox) if bbox else None
        hash_src = crop if crop is not None else frame
        img_hash = average_hash(hash_src)
        sharp = sharpness_score(hash_src)
        score = candidate_score(plate_confidence, sharp)

        candidate = FailCandidate(
            fail_type=fail_type,
            frame=frame.copy(),
            camera_id=camera_id,
            raw_ocr=raw_ocr,
            validation_error=validation_error,
            plate_confidence=float(plate_confidence or 0.0),
            char_confidence=float(char_confidence or 0.0),
            bbox=list(bbox) if bbox else None,
            crop=crop.copy() if crop is not None else None,
            sharpness=sharp,
            image_hash=img_hash,
            score=score,
        )

        if fail_type == FAIL_TYPE_OCR_INVALID:
            fail_metrics.inc("ocr_invalid_format")
            fail_metrics.inc("plate_bbox_hits")
        elif fail_type == FAIL_TYPE_OCR_EMPTY:
            fail_metrics.inc("ocr_empty")
            fail_metrics.inc("plate_bbox_hits")
        elif fail_type == FAIL_TYPE_OPERATOR_MISS:
            fail_metrics.inc("operator_confirmed_miss")

        self.note_recent_fail(camera_id)

        if immediate or fail_type == FAIL_TYPE_OPERATOR_MISS:
            return self._try_flush_candidate(candidate)

        with self._lock:
            cam = self._cam(camera_id)
            if cam.best is None or candidate.score >= cam.best.score:
                cam.best = candidate
            if cam.timer is None:
                timer = threading.Timer(
                    self.best_window_sec,
                    self._flush_window,
                    args=(camera_id,),
                )
                timer.daemon = True
                cam.timer = timer
                timer.start()
        return None

    def _flush_window(self, camera_id: str) -> None:
        with self._lock:
            cam = self._cam(camera_id)
            candidate = cam.best
            cam.best = None
            cam.timer = None
        if candidate is not None:
            self._try_flush_candidate(candidate)

    def _is_duplicate_locked(self, cam: _CameraWindow, candidate: FailCandidate) -> bool:
        now = time.time()
        cam.recent_hashes = [
            (t, h, b) for t, h, b in cam.recent_hashes if now - t <= self.cooldown_sec
        ]
        for t, h, b in cam.recent_hashes:
            if h and candidate.image_hash and hamming_distance_hex(h, candidate.image_hash) <= 6:
                return True
            if candidate.bbox and b and bbox_iou(candidate.bbox, b) >= self.iou_threshold:
                return True
        return False

    def _rate_limited_locked(self, cam: _CameraWindow) -> bool:
        now = time.time()
        cam.write_times = [t for t in cam.write_times if now - t < 60.0]
        return len(cam.write_times) >= self.max_per_minute

    def _resolve_scene_b(
        self,
        candidate: FailCandidate,
        scene_a_hash: str,
    ) -> tuple[Optional[np.ndarray], str, int, float]:
        """
        Returns (frame_or_None, source, delay_ms, sharpness).

        Live RTSP: delayed frame from registered provider.
        Upload / no provider: padded bbox context when bbox exists.
        """
        with self._lock:
            provider = self._frame_sources.get(candidate.camera_id)

        if provider is not None:
            delay_ms = int(self.scene_b_delay_ms)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            try:
                frame_b = provider()
            except Exception as exc:
                logger.warning("Scene B provider failed [%s]: %s", candidate.camera_id, exc)
                return None, "", delay_ms, 0.0
            if frame_b is None or frame_b.size == 0:
                return None, "", delay_ms, 0.0
            sharp_b = sharpness_score(frame_b)
            if sharp_b < self.scene_b_min_sharpness:
                logger.info(
                    "Scene B omitted (blurry %.1f < %.1f) camera=%s",
                    sharp_b,
                    self.scene_b_min_sharpness,
                    candidate.camera_id,
                )
                return None, "", delay_ms, sharp_b
            hash_b = average_hash(frame_b)
            if hamming_distance_hex(scene_a_hash, hash_b) <= SCENE_B_HASH_HAMMING_MAX:
                logger.info(
                    "Scene B omitted (near-duplicate of scene A) camera=%s",
                    candidate.camera_id,
                )
                return None, "", delay_ms, sharp_b
            return frame_b.copy(), "rtsp_delayed", delay_ms, sharp_b

        # Upload / offline path: padded plate context
        padded = padded_context_from_bbox(candidate.frame, candidate.bbox)
        if padded is None:
            return None, "", 0, 0.0
        sharp_b = sharpness_score(padded)
        return padded, "padded_bbox", 0, sharp_b

    def _try_flush_candidate(self, candidate: FailCandidate) -> Optional[Path]:
        with self._lock:
            cam = self._cam(candidate.camera_id)
            if self._is_duplicate_locked(cam, candidate):
                fail_metrics.inc("duplicate_fail_skipped")
                logger.info(
                    "Fail capture skipped (duplicate) camera=%s type=%s",
                    candidate.camera_id,
                    candidate.fail_type,
                )
                return None
            if self._rate_limited_locked(cam):
                fail_metrics.inc("fail_capture_rate_limited")
                logger.info(
                    "Fail capture rate-limited camera=%s type=%s",
                    candidate.camera_id,
                    candidate.fail_type,
                )
                return None

            capture_id = str(uuid.uuid4())
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            out_dir = self.root / day / capture_id
            out_dir.mkdir(parents=True, exist_ok=True)

            full_path = out_dir / "full.jpg"
            cv2.imwrite(str(full_path), candidate.frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

            if candidate.crop is not None:
                cv2.imwrite(
                    str(out_dir / "crop.jpg"),
                    candidate.crop,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 92],
                )

            relative = f"{day}/{capture_id}"
            scene_a_hash = average_hash(candidate.frame)
            meta = {
                "capture_id": capture_id,
                "fail_type": candidate.fail_type,
                "raw_ocr": candidate.raw_ocr,
                "validation_error": candidate.validation_error,
                "plate_confidence": round(candidate.plate_confidence, 4),
                "char_confidence": round(candidate.char_confidence, 4),
                "bbox": candidate.bbox,
                "camera_id": candidate.camera_id,
                "direction": direction_from_camera_id(candidate.camera_id),
                "timestamp": _utcnow_iso(),
                "label_ground_truth": None,
                "review_status": "pending",
                "not_a_plate": False,
                "sharpness": round(candidate.sharpness, 3),
                "local_path": relative,
                "image_hash": candidate.image_hash,
                "score": round(candidate.score, 4),
                "has_scene_b": False,
                "scene_b_source": "",
                "scene_b_delay_ms": 0,
                "scene_b_sharpness": None,
            }

            cam.recent_hashes.append(
                (time.time(), candidate.image_hash, candidate.bbox)
            )
            cam.write_times.append(time.time())

        # Scene B outside lock (may sleep for RTSP delay)
        frame_b, source_b, delay_ms, sharp_b = self._resolve_scene_b(
            candidate, scene_a_hash
        )
        if frame_b is not None:
            cv2.imwrite(
                str(out_dir / "scene_b.jpg"),
                frame_b,
                [int(cv2.IMWRITE_JPEG_QUALITY), 90],
            )
            meta["has_scene_b"] = True
            meta["scene_b_source"] = source_b
            meta["scene_b_delay_ms"] = delay_ms
            meta["scene_b_sharpness"] = round(sharp_b, 3)

        meta_path = out_dir / "meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Fail captured %s type=%s camera=%s scene_b=%s",
            capture_id,
            candidate.fail_type,
            candidate.camera_id,
            meta.get("has_scene_b"),
        )

        if self.ingest_callback is not None:
            self._ingest_pool.submit(self._safe_ingest, out_dir, meta)

        return out_dir

    def _safe_ingest(self, out_dir: Path, meta: dict) -> None:
        try:
            self.ingest_callback(out_dir, meta)  # type: ignore[misc]
        except Exception as exc:
            logger.warning("Fail ingest failed for %s: %s", out_dir, exc)

    def flush_all(self) -> None:
        """Flush pending best-window candidates (tests / shutdown)."""
        with self._lock:
            cams = list(self._cameras.keys())
        for camera_id in cams:
            with self._lock:
                cam = self._cam(camera_id)
                if cam.timer is not None:
                    cam.timer.cancel()
                    cam.timer = None
            self._flush_window(camera_id)

    def shutdown(self) -> None:
        self.flush_all()
        self._ingest_pool.shutdown(wait=False)


def django_ingest_callback_factory(
    django_base_url: Optional[str] = None,
    ingest_token: Optional[str] = None,
) -> Optional[Callable[[Path, dict], None]]:
    """Build multipart ingest callback if Django URL + token are configured."""
    base = (
        django_base_url
        or os.environ.get("DJANGO_BASE_URL", "http://127.0.0.1:8001")
    ).rstrip("/")
    token = ingest_token or os.environ.get(
        "DETECTION_FAIL_INGEST_TOKEN", "dev-fail-ingest-token"
    )
    if not base or not token:
        logger.info(
            "Django fail ingest disabled (set DJANGO_BASE_URL and DETECTION_FAIL_INGEST_TOKEN)"
        )
        return None

    url = f"{base}/api/parking/detection-fails/ingest/"

    def _ingest(out_dir: Path, meta: dict) -> None:
        boundary = f"----ParkinoxFail{uuid.uuid4().hex}"
        body = bytearray()

        def add_field(name: str, value: str) -> None:
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            )
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")

        def add_file(name: str, path: Path, content_type: str) -> None:
            if not path.is_file():
                return
            data = path.read_bytes()
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode()
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
            body.extend(data)
            body.extend(b"\r\n")

        add_field("capture_id", str(meta.get("capture_id", "")))
        add_field("fail_type", str(meta.get("fail_type", "")))
        add_field("raw_ocr", str(meta.get("raw_ocr") or ""))
        add_field("validation_error", str(meta.get("validation_error") or ""))
        add_field("plate_confidence", str(meta.get("plate_confidence", 0)))
        add_field("char_confidence", str(meta.get("char_confidence", 0)))
        add_field("bbox", json.dumps(meta.get("bbox")))
        add_field("camera_id", str(meta.get("camera_id", "")))
        add_field("direction", str(meta.get("direction", "entry")))
        add_field("timestamp", str(meta.get("timestamp", "")))
        add_field("local_data_path", str(meta.get("local_path", "")))
        add_field("sharpness", str(meta.get("sharpness", 0)))
        add_field("has_scene_b", "true" if meta.get("has_scene_b") else "false")
        add_field("scene_b_source", str(meta.get("scene_b_source") or ""))
        add_field("scene_b_delay_ms", str(meta.get("scene_b_delay_ms") or 0))
        if meta.get("scene_b_sharpness") is not None:
            add_field("scene_b_sharpness", str(meta.get("scene_b_sharpness")))

        add_file("full_image", out_dir / "full.jpg", "image/jpeg")
        add_file("crop_image", out_dir / "crop.jpg", "image/jpeg")
        add_file("scene_b_image", out_dir / "scene_b.jpg", "image/jpeg")

        body.extend(f"--{boundary}--\r\n".encode())

        req = urlrequest.Request(
            url,
            data=bytes(body),
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-Fail-Ingest-Token": token,
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                logger.info(
                    "Ingested fail %s → Django HTTP %s",
                    meta.get("capture_id"),
                    resp.status,
                )
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            logger.warning(
                "Django ingest HTTP %s for %s: %s",
                exc.code,
                meta.get("capture_id"),
                detail,
            )
        except Exception as exc:
            logger.warning(
                "Django ingest error for %s: %s",
                meta.get("capture_id"),
                exc,
            )

    return _ingest


# Module-level store (wired at FastAPI startup)
fail_capture_store: Optional[FailCaptureStore] = None


def get_fail_capture_store() -> FailCaptureStore:
    global fail_capture_store
    if fail_capture_store is None:
        fail_capture_store = FailCaptureStore(
            ingest_callback=django_ingest_callback_factory()
        )
    return fail_capture_store

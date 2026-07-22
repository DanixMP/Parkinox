"""
Local IP camera streams for Parkinox FastAPI.

Reads RTSP on the operator machine, runs YOLO detection in-process,
exposes MJPEG preview and pushes detections to WebSocket clients.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional, Set

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DETECTION_INTERVAL_SEC = 2.0
INVALID_RETRY_INTERVAL_SEC = 0.3
FRAME_READ_INTERVAL_SEC = 0.04
PREVIEW_UPDATE_INTERVAL_SEC = 0.2
# Same plate is pushed at most once per 2 minutes on ANY camera (entry or exit).
PLATE_EMIT_COOLDOWN_SEC = 120.0

# Flush stale RTSP packets before using a frame for detection.
BUFFER_FLUSH_GRABS = 8
# Skip blurry/corrupt frames (Laplacian variance below this threshold).
MIN_FRAME_VARIANCE = 25.0
MAX_CONSECUTIVE_BAD_FRAMES = 20
RECONNECT_BACKOFF_SEC = 2.0

CAMERA_WS_IDS = {
    "entry": "entry_camera",
    "exit": "exit_camera",
}


def _is_valid_frame(frame: Optional[np.ndarray]) -> bool:
    """Reject empty, tiny, or heavily corrupted/blurred frames."""
    if frame is None or frame.size == 0:
        return False
    h, w = frame.shape[:2]
    if h < 80 or w < 120:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < MIN_FRAME_VARIANCE:
        return False
    return True


class CameraStream:
    """Single RTSP camera: capture loop, MJPEG buffer, periodic detection."""

    def __init__(
        self,
        slot: str,
        detector,
        on_detection: Callable[[dict], None],
        on_rejection: Callable[[dict], None],
        plate_emit_check: Callable[[str, str, Optional[str]], bool],
        detector_lock: threading.Lock,
        detect_executor: ThreadPoolExecutor,
    ):
        self.slot = slot
        self.camera_id = CAMERA_WS_IDS[slot]
        self.detector = detector
        self.on_detection = on_detection
        self.on_rejection = on_rejection
        self._plate_emit_check = plate_emit_check
        self._detector_lock = detector_lock
        self._detect_executor = detect_executor
        self.url: Optional[str] = None
        self.enabled = False
        self.connected = False
        self.error: Optional[str] = None

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._preview_jpeg: Optional[bytes] = None
        self._latest_bgr: Optional[np.ndarray] = None
        self._detect_in_flight = threading.Lock()
        self._detect_running = False
        self._bad_frame_streak = 0
        self._last_preview_at = 0.0
        self._force_next_detect = False
        self._state_lock = threading.Lock()

    def configure(self, url: Optional[str], enabled: bool) -> None:
        url = (url or "").strip() or None
        changed = url != self.url or enabled != self.enabled
        self.url = url
        self.enabled = enabled
        if changed:
            self.restart()

    def restart(self) -> None:
        self.stop()
        if self.enabled and self.url:
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name=f"parkinox-cam-{self.slot}",
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._latest_jpeg = None
            self._preview_jpeg = None
            self._latest_bgr = None
        self.connected = False
        self._bad_frame_streak = 0

    def _open_capture(self) -> bool:
        if not self.url:
            self.error = "No stream URL configured"
            self.connected = False
            return False

        with self._lock:
            if self._cap is not None:
                self._cap.release()
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000)
            if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
            for _ in range(BUFFER_FLUSH_GRABS):
                cap.grab()
            if not cap.isOpened():
                self.error = f"Cannot open stream: {self.url}"
                self.connected = False
                self._cap = None
                return False
            self._cap = cap
            self.connected = True
            self.error = None
            self._bad_frame_streak = 0
            logger.info("Camera [%s] connected: %s", self.slot, self.url)
            if "/Channels/101" in (self.url or ""):
                logger.info(
                    "Camera [%s]: main stream (101) is heavy; sub-stream (102) "
                    "reduces H.264 decode errors and speeds up detection.",
                    self.slot,
                )
            return True

    def _read_frame(self, cap: cv2.VideoCapture) -> Optional[np.ndarray]:
        """Grab the newest decodable frame, flushing the RTSP buffer first."""
        for _ in range(BUFFER_FLUSH_GRABS - 1):
            if not cap.grab():
                break
        ok, frame = cap.retrieve()
        if not ok or not _is_valid_frame(frame):
            return None
        return frame

    def _mark_bad_frame(self) -> None:
        self._bad_frame_streak += 1
        if self._bad_frame_streak >= MAX_CONSECUTIVE_BAD_FRAMES:
            self.connected = False
            self.error = "Stream unstable — reconnecting"
            logger.warning(
                "Camera [%s]: %s consecutive bad frames, reconnecting",
                self.slot,
                self._bad_frame_streak,
            )
            with self._lock:
                if self._cap is not None:
                    self._cap.release()
                    self._cap = None
            self._bad_frame_streak = 0
            time.sleep(RECONNECT_BACKOFF_SEC)
            self._open_capture()

    def _update_preview(self, frame: np.ndarray) -> None:
        preview_frame = cv2.resize(frame, (640, 360))
        ok_preview, preview_buf = cv2.imencode(
            ".jpg",
            preview_frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 60],
        )
        if ok_preview:
            with self._lock:
                self._preview_jpeg = preview_buf.tobytes()

        ok_jpg, buf = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )
        if ok_jpg:
            with self._lock:
                self._latest_jpeg = buf.tobytes()
                self._latest_bgr = frame.copy()

    def _schedule_detect(self, frame: np.ndarray) -> None:
        """Run YOLO off the capture thread so RTSP buffers stay drained."""
        if self._detect_running:
            return
        if not self._detect_in_flight.acquire(blocking=False):
            return

        self._detect_running = True
        frame_copy = frame.copy()

        def _worker() -> None:
            try:
                self._detect(frame_copy)
            finally:
                self._detect_running = False
                self._detect_in_flight.release()

        self._detect_executor.submit(_worker)

    def _run(self) -> None:
        if not self._open_capture():
            return

        last_detect = 0.0
        while not self._stop.is_set():
            with self._lock:
                cap = self._cap

            if cap is None or not cap.isOpened():
                time.sleep(1.0)
                if not self._open_capture():
                    time.sleep(RECONNECT_BACKOFF_SEC)
                continue

            frame = self._read_frame(cap)
            if frame is None:
                self._mark_bad_frame()
                time.sleep(FRAME_READ_INTERVAL_SEC)
                continue

            self._bad_frame_streak = 0
            self.connected = True
            self.error = None

            now = time.time()
            if now - self._last_preview_at >= PREVIEW_UPDATE_INTERVAL_SEC:
                self._last_preview_at = now
                self._update_preview(frame)

            with self._state_lock:
                force = self._force_next_detect
                if force:
                    self._force_next_detect = False

            due_interval = now - last_detect >= DETECTION_INTERVAL_SEC
            due_retry = force and (now - last_detect >= INVALID_RETRY_INTERVAL_SEC)
            if due_interval or due_retry:
                last_detect = now
                self._schedule_detect(frame)

            time.sleep(FRAME_READ_INTERVAL_SEC)

    def _request_immediate_retry(self) -> None:
        with self._state_lock:
            self._force_next_detect = True

    def _detect(self, frame: np.ndarray) -> None:
        try:
            with self._detector_lock:
                plate_text, confidence, metadata = self.detector.detect(frame)

            from fail_capture import (
                FAIL_TYPE_OCR_EMPTY,
                FAIL_TYPE_OCR_INVALID,
                get_fail_capture_store,
            )

            store = get_fail_capture_store()

            # Type B: bbox + empty OCR — capture only, no retry change
            if metadata and metadata.get("fail_type") == FAIL_TYPE_OCR_EMPTY:
                logger.info(
                    "Camera [%s] empty OCR with bbox — capturing fail",
                    self.slot,
                )
                store.submit(
                    fail_type=FAIL_TYPE_OCR_EMPTY,
                    frame=frame,
                    camera_id=self.camera_id,
                    raw_ocr=metadata.get("raw_ocr") or "",
                    validation_error="Empty or below-threshold OCR",
                    plate_confidence=float(confidence or 0.0),
                    char_confidence=float(metadata.get("char_confidence") or 0.0),
                    bbox=metadata.get("bbox"),
                )
                return

            if metadata and metadata.get("rejected"):
                logger.info(
                    "Camera [%s] invalid plate OCR %r — retrying (%s)",
                    self.slot,
                    metadata.get("raw_ocr"),
                    metadata.get("validation_error"),
                )
                store.submit(
                    fail_type=FAIL_TYPE_OCR_INVALID,
                    frame=frame,
                    camera_id=self.camera_id,
                    raw_ocr=metadata.get("raw_ocr") or metadata.get("raw_text"),
                    validation_error=metadata.get("validation_error"),
                    plate_confidence=float(confidence or 0.0),
                    char_confidence=float(metadata.get("char_confidence") or 0.0),
                    bbox=metadata.get("bbox"),
                )
                self.on_rejection({
                    "camera_id": self.camera_id,
                    "raw_ocr": metadata.get("raw_ocr"),
                    "validation_error": metadata.get("validation_error"),
                    "confidence": round(float(confidence), 3),
                    "char_confidence": round(
                        float(metadata.get("char_confidence") or 0.0), 3
                    ),
                    "bbox": metadata.get("bbox", []),
                    "fail_type": FAIL_TYPE_OCR_INVALID,
                })
                self._request_immediate_retry()
                return

            if not plate_text:
                return

            canonical = (metadata or {}).get("plate_canonical")
            if not self._plate_emit_check(plate_text, self.slot, canonical):
                return

            store.note_valid_emit(self.camera_id)

            event_id = str(uuid.uuid4())
            bbox = metadata.get("bbox", []) if metadata else []
            payload = {
                "event_id": event_id,
                "plate_number": plate_text,
                "plate_canonical": (metadata or {}).get("plate_canonical"),
                "camera_id": self.camera_id,
                "confidence": round(float(confidence), 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "unregistered",
                "char_confidence": round(
                    float(metadata.get("char_confidence", 0)) if metadata else 0.0,
                    3,
                ),
                "bbox": bbox,
            }
            # Non-blocking success-image buffer (does not affect emit / approval).
            try:
                from success_capture import get_success_capture_store

                get_success_capture_store().buffer_detection(
                    detection_event_id=event_id,
                    camera_id=self.camera_id,
                    plate=plate_text,
                    confidence=float(confidence or 0.0),
                    frame=frame,
                    bbox=bbox,
                )
            except Exception:
                logger.debug("success buffer skipped", exc_info=True)
            logger.info(
                "Camera [%s] plate detected: %s (%.3f)",
                self.slot,
                plate_text,
                confidence,
            )
            self.on_detection(payload)
        except Exception as exc:
            logger.error("Detection error [%s]: %s", self.slot, exc, exc_info=True)

    def capture_operator_miss(self) -> Optional[dict]:
        """Type C: operator marks a visible plate that had no bbox."""
        from fail_capture import FAIL_TYPE_OPERATOR_MISS, get_fail_capture_store

        with self._lock:
            jpeg = self._latest_jpeg
        if not jpeg:
            return None
        arr = np.frombuffer(jpeg, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        store = get_fail_capture_store()
        store.submit(
            fail_type=FAIL_TYPE_OPERATOR_MISS,
            frame=frame,
            camera_id=self.camera_id,
            raw_ocr=None,
            validation_error="Operator confirmed miss (no plate bbox)",
            plate_confidence=0.0,
            char_confidence=0.0,
            bbox=None,
            immediate=True,
        )
        return {
            "camera_id": self.camera_id,
            "fail_type": FAIL_TYPE_OPERATOR_MISS,
            "status": "captured",
        }

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def get_latest_preview_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._preview_jpeg

    def get_latest_bgr(self) -> Optional[np.ndarray]:
        """Copy of latest valid BGR frame for fail-capture Scene B."""
        with self._lock:
            if self._latest_bgr is None:
                return None
            return self._latest_bgr.copy()

    def to_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "url": self.url,
            "connected": self.connected,
            "error": self.error,
        }


class CameraManager:
    """Entry/exit camera workers and WebSocket broadcast hub."""

    def __init__(self, detector):
        self.detector = detector
        self._detector_lock = threading.Lock()
        self._detect_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="parkinox-detect",
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_clients: Set = set()
        self._global_plate_lock = threading.Lock()
        # identity_key -> (timestamp, slot) — blocks all cameras for PLATE_EMIT_COOLDOWN_SEC
        self._global_plates: dict[str, tuple[float, str]] = {}
        self.entry = CameraStream(
            "entry",
            detector,
            self._emit_detection,
            self._emit_rejection,
            self._can_emit_plate,
            self._detector_lock,
            self._detect_executor,
        )
        self.exit = CameraStream(
            "exit",
            detector,
            self._emit_detection,
            self._emit_rejection,
            self._can_emit_plate,
            self._detector_lock,
            self._detect_executor,
        )
        # Live RTSP frame providers for dual-scene fail capture (Scene B).
        try:
            from fail_capture import get_fail_capture_store

            store = get_fail_capture_store()
            store.register_frame_source(self.entry.camera_id, self.entry.get_latest_bgr)
            store.register_frame_source(self.exit.camera_id, self.exit.get_latest_bgr)
        except Exception:
            logger.warning("Fail-capture frame source registration skipped", exc_info=True)
        try:
            from success_capture import get_success_capture_store

            sstore = get_success_capture_store()
            sstore.register_frame_source(self.entry.camera_id, self.entry.get_latest_bgr)
            sstore.register_frame_source(self.exit.camera_id, self.exit.get_latest_bgr)
        except Exception:
            logger.warning("Success-capture frame source registration skipped", exc_info=True)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def apply_config(self, config: dict) -> None:
        self.entry.configure(
            config.get("entry_url"),
            bool(config.get("entry_enabled", False)),
        )
        self.exit.configure(
            config.get("exit_url"),
            bool(config.get("exit_enabled", False)),
        )

    @staticmethod
    def _latinize_digits(text: str) -> str:
        """Convert Persian/Arabic-Indic digits to ASCII (matches Flutter plateKey)."""
        out = text
        for i, ch in enumerate("0123456789"):
            out = out.replace(chr(0x06F0 + i), ch)  # Persian ۰-۹
            out = out.replace(chr(0x0660 + i), ch)  # Arabic-Indic ٠-٩
        return out

    @staticmethod
    def _identity_keys_similar(a: str, b: str) -> bool:
        """Tolerate one OCR digit flip in the serial group (same XX+letter prefix)."""
        if not a or not b:
            return False
        if a == b:
            return True
        if len(a) >= 6 and len(b) >= 6 and a[:3] == b[:3]:
            sa, sb = a[3:6], b[3:6]
            if len(sa) == 3 and len(sb) == 3:
                return sum(x != y for x, y in zip(sa, sb)) <= 1
        return False

    @staticmethod
    def _plate_identity_key(plate_text: str, canonical: Optional[str] = None) -> str:
        """Match Flutter CrossCameraPlateGuard.identityKey logic."""
        from plate_validator import validate_detection_plate, _normalizer_module

        raw = (canonical or plate_text or "").strip()
        if not raw:
            return ""

        canonical_plate = canonical
        if not canonical_plate:
            canonical_plate, _err = validate_detection_plate(raw)

        if canonical_plate:
            try:
                normalizer = _normalizer_module()
                api = normalizer.to_api_format(canonical_plate)
                m = re.match(r"^(\d{2})([A-Z]+)(\d{3})IR\d{2}$", api)
                if m:
                    return f"{m.group(1)}{m.group(2)}{m.group(3)}"
                m = re.match(r"^(\d{5})FZ", api)
                if m:
                    return m.group(1)
            except ValueError:
                pass

        compact = re.sub(r"[\s_\-]+", "", raw)
        latin = CameraManager._latinize_digits(compact).upper()

        m = re.match(r"^(\d{2})([A-Z]+)(\d{3})IR\d{2}$", latin)
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"

        m = re.match(r"^(\d{5})FZ", latin)
        if m:
            return m.group(1)

        m = re.match(
            r"^(\d{2})([آ-یA-Za-z]+|[\u0600-\u06FF]+)(\d{3})(\d{2})$",
            latin,
        )
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"

        if re.match(r"^\d{7}$", latin):
            return latin[:5]

        return latin

    def _can_emit_plate(
        self,
        plate_text: str,
        slot: str,
        canonical: Optional[str] = None,
    ) -> bool:
        """
        Allow at most one WebSocket push per plate identity every 2 minutes,
        on the same camera or the opposite camera.
        """
        key = self._plate_identity_key(plate_text, canonical)
        if not key:
            return True
        now = time.time()
        with self._global_plate_lock:
            expired = [
                plate
                for plate, (seen_at, _) in self._global_plates.items()
                if now - seen_at > PLATE_EMIT_COOLDOWN_SEC
            ]
            for plate in expired:
                del self._global_plates[plate]

            prev = self._global_plates.get(key)
            if prev is not None:
                prev_time, prev_slot = prev
                if (now - prev_time) < PLATE_EMIT_COOLDOWN_SEC:
                    if prev_slot == slot:
                        logger.info(
                            "Plate cooldown (%ss): %s already pushed on %s",
                            int(PLATE_EMIT_COOLDOWN_SEC),
                            plate_text,
                            slot,
                        )
                    else:
                        logger.info(
                            "Cross-camera cooldown (%ss): %s pushed on %s, ignoring %s",
                            int(PLATE_EMIT_COOLDOWN_SEC),
                            plate_text,
                            prev_slot,
                            slot,
                        )
                    return False

            for seen_key, (seen_at, seen_slot) in self._global_plates.items():
                if (now - seen_at) >= PLATE_EMIT_COOLDOWN_SEC:
                    continue
                if not self._identity_keys_similar(key, seen_key):
                    continue
                if seen_slot == slot:
                    logger.info(
                        "OCR-similar cooldown (%ss): %s ~ %s on %s",
                        int(PLATE_EMIT_COOLDOWN_SEC),
                        plate_text,
                        seen_key,
                        slot,
                    )
                else:
                    logger.info(
                        "Cross-camera OCR-similar cooldown (%ss): %s ~ %s (was %s)",
                        int(PLATE_EMIT_COOLDOWN_SEC),
                        plate_text,
                        seen_key,
                        seen_slot,
                    )
                return False

            self._global_plates[key] = (now, slot)
            return True

    def inject_plate_detected(self, data: dict) -> None:
        """Broadcast a synthetic plate_detected event (test UI / Flutter)."""
        self._emit_detection(data)

    def _emit_rejection(self, data: dict) -> None:
        message = json.dumps({"type": "plate_rejected", "data": data})
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)

    def _emit_detection(self, data: dict) -> None:
        message = json.dumps({"type": "plate_detected", "data": data})
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
        else:
            logger.warning(
                "Dropping plate_detected for %s: event loop not ready",
                data.get("plate_number"),
            )

    async def broadcast(self, message: str) -> None:
        dead = []
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.discard(ws)

    async def add_client(self, ws) -> None:
        await ws.accept()
        self._ws_clients.add(ws)
        await ws.send_text(json.dumps({"type": "connected"}))

    def remove_client(self, ws) -> None:
        self._ws_clients.discard(ws)

    def capture_miss(self, slot: str) -> Optional[dict]:
        """Type C operator miss for entry/exit slot."""
        return self.stream_for(slot).capture_operator_miss()

    def shutdown(self) -> None:
        self.entry.stop()
        self.exit.stop()
        try:
            from fail_capture import get_fail_capture_store

            get_fail_capture_store().shutdown()
        except Exception:
            pass
        try:
            from success_capture import get_success_capture_store

            get_success_capture_store().shutdown()
        except Exception:
            pass
        self._detect_executor.shutdown(wait=False, cancel_futures=True)

    def status(self) -> dict:
        return {
            "entry": self.entry.to_status(),
            "exit": self.exit.to_status(),
        }

    def stream_for(self, slot: str) -> CameraStream:
        if slot == "entry":
            return self.entry
        if slot == "exit":
            return self.exit
        raise KeyError(slot)

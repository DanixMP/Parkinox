"""
Local IP camera streams for Parkinox FastAPI.

Reads RTSP on the operator machine, runs YOLO detection in-process,
exposes MJPEG preview and pushes detections to WebSocket clients.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional, Set

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DETECTION_INTERVAL_SEC = 3.0
FRAME_READ_INTERVAL_SEC = 0.05
PLATE_COOLDOWN_SEC = 10.0
CROSS_CAMERA_COOLDOWN_SEC = 60.0

CAMERA_WS_IDS = {
    "entry": "entry_camera",
    "exit": "exit_camera",
}


class CameraStream:
    """Single RTSP camera: capture loop, MJPEG buffer, periodic detection."""

    def __init__(self, slot: str, detector, on_detection: Callable[[dict], None]):
        self.slot = slot
        self.camera_id = CAMERA_WS_IDS[slot]
        self.detector = detector
        self.on_detection = on_detection
        self.url: Optional[str] = None
        self.enabled = False
        self.connected = False
        self.error: Optional[str] = None

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._last_plate: Optional[str] = None
        self._last_plate_time = 0.0

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
        self.connected = False

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
            if not cap.isOpened():
                self.error = f"Cannot open stream: {self.url}"
                self.connected = False
                self._cap = None
                return False
            self._cap = cap
            self.connected = True
            self.error = None
            logger.info("Camera [%s] connected: %s", self.slot, self.url)
            return True

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
                    time.sleep(3.0)
                continue

            ok, frame = cap.read()
            if not ok or frame is None:
                self.connected = False
                self.error = "Stream read failed — reconnecting"
                time.sleep(0.5)
                self._open_capture()
                continue

            self.connected = True
            self.error = None

            ok_jpg, buf = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 80],
            )
            if ok_jpg:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()

            now = time.time()
            if now - last_detect >= DETECTION_INTERVAL_SEC:
                last_detect = now
                self._detect(frame)

            time.sleep(FRAME_READ_INTERVAL_SEC)

    def _detect(self, frame: np.ndarray) -> None:
        try:
            plate_text, confidence, metadata = self.detector.detect(frame)
            if not plate_text:
                return

            now = time.time()
            if (
                plate_text == self._last_plate
                and (now - self._last_plate_time) < PLATE_COOLDOWN_SEC
            ):
                return

            self._last_plate = plate_text
            self._last_plate_time = now

            payload = {
                "event_id": str(uuid.uuid4()),
                "plate_number": plate_text,
                "camera_id": self.camera_id,
                "confidence": round(float(confidence), 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "unregistered",
                "char_confidence": round(
                    float(metadata.get("char_confidence", 0)) if metadata else 0.0,
                    3,
                ),
                "bbox": metadata.get("bbox", []) if metadata else [],
            }
            logger.info(
                "Camera [%s] plate detected: %s (%.3f)",
                self.slot,
                plate_text,
                confidence,
            )
            self.on_detection(payload)
        except Exception as exc:
            logger.error("Detection error [%s]: %s", self.slot, exc, exc_info=True)

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

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
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_clients: Set = set()
        self._global_plate_lock = threading.Lock()
        # plate -> (timestamp, slot) — blocks opposite camera for CROSS_CAMERA_COOLDOWN_SEC
        self._global_plates: dict[str, tuple[float, str]] = {}
        self.entry = CameraStream("entry", detector, self._emit_detection)
        self.exit = CameraStream("exit", detector, self._emit_detection)

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

    def _slot_for_camera_id(self, camera_id: str) -> Optional[str]:
        if camera_id == CAMERA_WS_IDS["entry"]:
            return "entry"
        if camera_id == CAMERA_WS_IDS["exit"]:
            return "exit"
        return None

    def _can_emit_cross_camera(self, plate_text: str, slot: str) -> bool:
        """Suppress the same plate on the opposite camera for one minute."""
        now = time.time()
        with self._global_plate_lock:
            expired = [
                plate
                for plate, (seen_at, _) in self._global_plates.items()
                if now - seen_at > CROSS_CAMERA_COOLDOWN_SEC
            ]
            for plate in expired:
                del self._global_plates[plate]

            prev = self._global_plates.get(plate_text)
            if prev is not None:
                prev_time, prev_slot = prev
                if (
                    prev_slot != slot
                    and (now - prev_time) < CROSS_CAMERA_COOLDOWN_SEC
                ):
                    logger.info(
                        "Cross-camera cooldown: %s seen on %s, ignoring %s",
                        plate_text,
                        prev_slot,
                        slot,
                    )
                    return False

            self._global_plates[plate_text] = (now, slot)
            return True

    def _emit_detection(self, data: dict) -> None:
        plate_text = data.get("plate_number")
        slot = self._slot_for_camera_id(data.get("camera_id", ""))
        if plate_text and slot and not self._can_emit_cross_camera(plate_text, slot):
            return

        message = json.dumps({"type": "plate_detected", "data": data})
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)

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

    def shutdown(self) -> None:
        self.entry.stop()
        self.exit.stop()

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

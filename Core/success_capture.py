"""
Successful plate event image capture (local-first).

Buffers frames on valid plate_detected emit; finalizes to parking_media/ after
gate confirm via POST /success-capture/finalize. Never blocks detection or gate logic.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Set, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DATA_MEDIA_ROOT = Path(__file__).resolve().parent / "parking_media"
BUFFER_TTL_SEC = float(os.environ.get("SUCCESS_CAPTURE_BUFFER_TTL_SEC", "120"))
SCENE_B_DELAY_MS = int(os.environ.get("SUCCESS_CAPTURE_SCENE_B_DELAY_MS", "500"))
THUMB_MAX_W = int(os.environ.get("SUCCESS_CAPTURE_THUMB_MAX_W", "320"))
JPEG_QUALITY = int(os.environ.get("SUCCESS_CAPTURE_JPEG_QUALITY", "85"))

FrameProvider = Callable[[], Optional[np.ndarray]]

CAMERA_ID_ALIASES = {
    "entry": "entry_camera",
    "exit": "exit_camera",
    "entry_camera": "entry_camera",
    "exit_camera": "exit_camera",
}

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# Latin letter code → Persian (API ↔ OCR plate-key bridge). Longest codes first.
_LATIN_TO_PERSIAN_LETTER = {
    "Taxi": "ت",
    "Hamza": "ء",
    "PwD": "ژ",
    "PuV": "ع",
    "Sin": "س",
    "Sad": "ص",
    "Sha": "ش",
    "Tha": "ث",
    "Kh": "خ",
    "Ha": "ح",
    "Gh": "ق",
    "Aa": "آ",
    "Ch": "چ",
    "B": "ب",
    "J": "ج",
    "D": "د",
    "T": "ط",
    "L": "ل",
    "M": "م",
    "N": "ن",
    "V": "و",
    "H": "ه",
    "Y": "ی",
    "A": "الف",
    "P": "پ",
    "Z": "ز",
    "F": "ف",
    "K": "ک",
    "G": "گ",
    "R": "ر",
    "S": "س",  # OCR single-letter alias for Sin
}
_SORTED_LATIN_CODES = sorted(_LATIN_TO_PERSIAN_LETTER.keys(), key=len, reverse=True)

_API_NATIONAL_RE = re.compile(r"^(\d{2})([a-z]+)(\d{3})ir(\d{2})$", re.IGNORECASE)
_API_FZ_RE = re.compile(r"^(\d{5})fz[a-z]+(\d{2})$", re.IGNORECASE)
# Digits + Latin letter code + digits (OCR Latin without IR), e.g. 33s33333
_LATIN_EMBEDDED_RE = re.compile(r"^(\d{2})([a-z]+)(\d{3})(\d{2})$", re.IGNORECASE)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_camera_id(camera_id: str) -> str:
    """Map Flutter/Django 'entry'/'exit' to Core 'entry_camera'/'exit_camera'."""
    raw = (camera_id or "").strip()
    return CAMERA_ID_ALIASES.get(raw, raw)


def normalize_plate_key(plate: str) -> str:
    """Canonical plate key for buffer lookup (digits ASCII, no spaces/dashes)."""
    if not plate:
        return ""
    s = str(plate).translate(_DIGIT_MAP)
    for ch in (" ", "\u200c", "-", "_", "\t"):
        s = s.replace(ch, "")
    return s.lower()


def _latin_code_to_persian(code: str) -> Optional[str]:
    if not code:
        return None
    # Prefer exact case-insensitive match against known codes (longest first).
    lower = code.lower()
    for lat in _SORTED_LATIN_CODES:
        if lat.lower() == lower:
            return _LATIN_TO_PERSIAN_LETTER[lat]
    return None


def plate_lookup_keys(plate: str) -> Set[str]:
    """
    Keys used to index/resolve a buffered detection.

    Indexes both the raw OCR/API key and a digit+Persian-letter form so
    ``12B345IR67`` and ``12ب345-67`` resolve to the same buffer.
    """
    keys: Set[str] = set()
    raw = normalize_plate_key(plate)
    if not raw:
        return keys
    keys.add(raw)

    m = _API_NATIONAL_RE.match(raw)
    if m:
        letter = _latin_code_to_persian(m.group(2))
        if letter:
            keys.add(f"{m.group(1)}{letter}{m.group(3)}{m.group(4)}")
        # Also index without IR noise using Latin letter as-is
        keys.add(f"{m.group(1)}{m.group(2).lower()}{m.group(3)}{m.group(4)}")
    else:
        m = _API_FZ_RE.match(raw)
        if m:
            keys.add(f"{m.group(1)}{m.group(2)}")
        else:
            m = _LATIN_EMBEDDED_RE.match(raw)
            if m:
                letter = _latin_code_to_persian(m.group(2))
                if letter:
                    keys.add(f"{m.group(1)}{letter}{m.group(3)}{m.group(4)}")

    # Strip trailing IR/FZ fragments if present without full match
    stripped = raw
    if "ir" in stripped:
        stripped = stripped.replace("ir", "")
        if stripped:
            keys.add(stripped)
    if "fz" in stripped:
        # Remove fz + following latin zone token roughly
        stripped2 = re.sub(r"fz[a-z]*", "", stripped, flags=re.IGNORECASE)
        if stripped2:
            keys.add(stripped2)

    return {k for k in keys if k}


def crop_from_bbox(frame: np.ndarray, bbox: Optional[list], pad: int = 10) -> Optional[np.ndarray]:
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


def make_thumbnail(frame: np.ndarray, max_w: int = THUMB_MAX_W) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= max_w:
        return frame
    scale = max_w / float(w)
    return cv2.resize(frame, (max_w, int(h * scale)), interpolation=cv2.INTER_AREA)


@dataclass
class BufferedDetection:
    detection_event_id: str
    camera_id: str
    plate: str
    confidence: float
    bbox: Optional[list]
    scene_a: np.ndarray
    crop: Optional[np.ndarray]
    buffered_at: float = field(default_factory=time.time)
    meta: dict = field(default_factory=dict)


class SuccessCaptureStore:
    """In-memory buffer + async finalize writer for successful gate events."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DATA_MEDIA_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._by_detection: Dict[str, BufferedDetection] = {}
        self._by_camera_plate: Dict[Tuple[str, str], str] = {}
        self._finalizing: Set[str] = set()
        self._frame_sources: Dict[str, FrameProvider] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="success-cap")

    def register_frame_source(self, camera_id: str, provider: FrameProvider) -> None:
        with self._lock:
            self._frame_sources[camera_id] = provider

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            k for k, v in self._by_detection.items() if now - v.buffered_at > BUFFER_TTL_SEC
        ]
        for k in expired:
            buf = self._by_detection.pop(k, None)
            if buf:
                self._unindex_plate_keys_locked(buf)
            self._finalizing.discard(k)

    def _index_plate_keys_locked(self, buf: BufferedDetection) -> None:
        for plate_key in plate_lookup_keys(buf.plate):
            self._by_camera_plate[(buf.camera_id, plate_key)] = buf.detection_event_id

    def _unindex_plate_keys_locked(self, buf: BufferedDetection) -> None:
        for plate_key in plate_lookup_keys(buf.plate):
            key = (buf.camera_id, plate_key)
            if self._by_camera_plate.get(key) == buf.detection_event_id:
                self._by_camera_plate.pop(key, None)

    def buffer_detection(
        self,
        *,
        detection_event_id: str,
        camera_id: str,
        plate: str,
        confidence: float,
        frame: np.ndarray,
        bbox: Optional[list] = None,
        meta: Optional[dict] = None,
    ) -> None:
        """Call from detection path — copies frame; must stay fast."""
        if frame is None:
            return
        try:
            scene = frame.copy()
            crop = crop_from_bbox(scene, bbox)
            cam = normalize_camera_id(camera_id)
            plate_raw = plate or ""
            buf = BufferedDetection(
                detection_event_id=str(detection_event_id),
                camera_id=cam,
                plate=plate_raw,
                confidence=float(confidence or 0.0),
                bbox=list(bbox) if bbox else None,
                scene_a=scene,
                crop=crop,
                meta=dict(meta or {}),
            )
            with self._lock:
                self._purge_expired()
                # Replace any prior buffer for this detection id
                old = self._by_detection.get(buf.detection_event_id)
                if old is not None:
                    self._unindex_plate_keys_locked(old)
                self._by_detection[buf.detection_event_id] = buf
                self._index_plate_keys_locked(buf)
        except Exception:
            logger.exception("success buffer failed")

    def _consume_buffer_locked(self, buf: BufferedDetection) -> None:
        """Remove buffer so one detection can only finalize once (caller holds lock)."""
        self._by_detection.pop(buf.detection_event_id, None)
        self._unindex_plate_keys_locked(buf)
        self._finalizing.discard(buf.detection_event_id)

    def _release_finalizing_locked(self, detection_event_id: str) -> None:
        self._finalizing.discard(detection_event_id)

    def _resolve_buffer(
        self,
        *,
        detection_event_id: Optional[str],
        camera_id: str,
        plate: str,
        claim: bool = False,
    ) -> Optional[BufferedDetection]:
        """
        Find a buffered detection.

        Resolve order: detection_event_id → plate_key → miss.
        No camera-wide fallback.

        When ``claim`` is True, mark the buffer as in-flight so a concurrent
        finalize cannot reuse it, but leave frames in place until consume after
        a successful JPEG write.
        """
        cam = normalize_camera_id(camera_id)
        with self._lock:
            self._purge_expired()
            buf = None
            if detection_event_id and detection_event_id in self._by_detection:
                buf = self._by_detection.get(detection_event_id)
            else:
                for plate_key in plate_lookup_keys(plate):
                    det_id = self._by_camera_plate.get((cam, plate_key))
                    if det_id:
                        buf = self._by_detection.get(det_id)
                        if buf is not None:
                            break
            if buf is None:
                return None
            if claim:
                if buf.detection_event_id in self._finalizing:
                    return None
                self._finalizing.add(buf.detection_event_id)
            return buf

    def _grab_scene_b(self, camera_id: str) -> Optional[np.ndarray]:
        cam = normalize_camera_id(camera_id)
        provider = self._frame_sources.get(cam) or self._frame_sources.get(camera_id)
        if not provider:
            # try aliases
            for alias in (cam, camera_id, "entry_camera", "exit_camera"):
                provider = self._frame_sources.get(alias)
                if provider:
                    break
        if not provider:
            return None
        try:
            time.sleep(max(0, SCENE_B_DELAY_MS) / 1000.0)
            frame = provider()
            if frame is None:
                return None
            return frame.copy()
        except Exception:
            logger.debug("scene_b grab failed", exc_info=True)
            return None

    def finalize(
        self,
        *,
        event_uuid: str,
        camera_id: str,
        plate: str = "",
        direction: str = "entry",
        confidence: Optional[float] = None,
        detection_event_id: Optional[str] = None,
        session_uuid: Optional[str] = None,
        gate_event_id: Optional[int] = None,
    ) -> dict:
        """
        Write parking_media/YYYY-MM-DD/<event_uuid>/ synchronously in worker thread.
        Returns meta dict; empty files dict if buffer miss.

        Buffer is claimed (anti-reuse) without consuming frames; after JPEGs are
        written successfully the buffer is consumed. On write failure the claim
        is released so a retry can still hit the buffer.
        """
        buf = self._resolve_buffer(
            detection_event_id=detection_event_id,
            camera_id=camera_id,
            plate=plate,
            claim=True,
        )
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir = self.root / day / str(event_uuid)
        out_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "scene_a": False,
            "scene_b": False,
            "crop": False,
            "thumbnail": False,
        }
        if buf is None:
            meta = {
                "event_uuid": str(event_uuid),
                "session_uuid": session_uuid,
                "gate_event_id": gate_event_id,
                "camera_id": camera_id,
                "direction": direction,
                "plate": plate,
                "confidence": confidence,
                "detection_event_id": detection_event_id,
                "captured_at": _utcnow_iso(),
                "buffer_miss": True,
                "files": files,
                "media_dir": str(out_dir),
            }
            (out_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return meta

        wrote_ok = False
        try:
            conf = confidence if confidence is not None else buf.confidence
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

            ok, enc = cv2.imencode(".jpg", buf.scene_a, encode_params)
            if ok:
                (out_dir / "scene_a.jpg").write_bytes(enc.tobytes())
                files["scene_a"] = True

            if buf.crop is not None:
                ok, enc = cv2.imencode(".jpg", buf.crop, encode_params)
                if ok:
                    (out_dir / "crop.jpg").write_bytes(enc.tobytes())
                    files["crop"] = True

            thumb = make_thumbnail(buf.scene_a)
            ok, enc = cv2.imencode(".jpg", thumb, encode_params)
            if ok:
                (out_dir / "thumbnail.jpg").write_bytes(enc.tobytes())
                files["thumbnail"] = True

            scene_b = self._grab_scene_b(buf.camera_id)
            if scene_b is not None:
                ok, enc = cv2.imencode(".jpg", scene_b, encode_params)
                if ok:
                    (out_dir / "scene_b.jpg").write_bytes(enc.tobytes())
                    files["scene_b"] = True

            meta = {
                "event_uuid": str(event_uuid),
                "session_uuid": session_uuid,
                "gate_event_id": gate_event_id,
                "camera_id": camera_id,
                "direction": direction,
                "plate": plate or buf.plate,
                "confidence": conf,
                "detection_event_id": buf.detection_event_id,
                "bbox": buf.bbox,
                "captured_at": _utcnow_iso(),
                "buffer_miss": False,
                "files": files,
                "media_dir": str(out_dir),
            }
            (out_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            wrote_ok = any(files.values())
            return meta
        except Exception:
            logger.exception("success finalize write failed for %s", event_uuid)
            raise
        finally:
            with self._lock:
                if wrote_ok:
                    self._consume_buffer_locked(buf)
                else:
                    # Keep buffer for retry; clear in-flight claim only.
                    self._release_finalizing_locked(buf.detection_event_id)

    def finalize_async(self, **kwargs) -> None:
        def _job():
            try:
                self.finalize(**kwargs)
            except Exception:
                logger.exception("success finalize failed for %s", kwargs.get("event_uuid"))

        self._executor.submit(_job)


_store: Optional[SuccessCaptureStore] = None


def get_success_capture_store() -> SuccessCaptureStore:
    global _store
    if _store is None:
        _store = SuccessCaptureStore()
    return _store

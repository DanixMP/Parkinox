"""Unit tests for FailCaptureStore (no YOLO required)."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

from fail_capture import (
    FAIL_TYPE_OCR_EMPTY,
    FAIL_TYPE_OCR_INVALID,
    FAIL_TYPE_OPERATOR_MISS,
    FailCaptureStore,
    average_hash,
    bbox_iou,
    candidate_score,
)
from fail_metrics import fail_metrics


def _solid_frame(color=(40, 80, 120), size=(240, 320)) -> np.ndarray:
    h, w = size
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    # Add texture so sharpness/hash are non-trivial
    cv2.rectangle(frame, (20, 20), (120, 60), (255, 255, 255), -1)
    cv2.putText(frame, "12B345", (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return frame


class FailCaptureStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        fail_metrics.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bbox_iou_and_score(self):
        self.assertGreater(bbox_iou([0, 0, 100, 50], [10, 10, 110, 60]), 0.5)
        self.assertEqual(bbox_iou([0, 0, 10, 10], [50, 50, 60, 60]), 0.0)
        self.assertGreater(candidate_score(0.9, 400), candidate_score(0.2, 10))

    def test_writes_full_crop_meta(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=0.0,
            max_per_minute=100,
            best_window_sec=0.01,
        )
        frame = _solid_frame()
        out_dir = store.submit(
            fail_type=FAIL_TYPE_OCR_INVALID,
            frame=frame,
            camera_id="entry_camera",
            raw_ocr="۱۲ب۳۴۵۶۷۸",
            validation_error="bad format",
            plate_confidence=0.91,
            char_confidence=0.55,
            bbox=[20, 20, 120, 60],
            immediate=True,
        )
        self.assertIsNotNone(out_dir)
        self.assertTrue((out_dir / "full.jpg").is_file())
        self.assertTrue((out_dir / "crop.jpg").is_file())
        meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["fail_type"], FAIL_TYPE_OCR_INVALID)
        self.assertEqual(meta["review_status"], "pending")
        self.assertEqual(meta["raw_ocr"], "۱۲ب۳۴۵۶۷۸")
        self.assertEqual(fail_metrics.snapshot()["ocr_invalid_format"], 1)
        # Upload path (no RTSP provider): padded bbox Scene B
        self.assertTrue(meta.get("has_scene_b"))
        self.assertEqual(meta.get("scene_b_source"), "padded_bbox")
        self.assertTrue((out_dir / "scene_b.jpg").is_file())

    def test_type_c_no_crop(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=0.0,
            max_per_minute=100,
            best_window_sec=0.01,
        )
        store.submit(
            fail_type=FAIL_TYPE_OPERATOR_MISS,
            frame=_solid_frame(),
            camera_id="exit_camera",
            immediate=True,
        )
        out = next((self.root).rglob("meta.json")).parent
        self.assertTrue((out / "full.jpg").is_file())
        self.assertFalse((out / "crop.jpg").is_file())
        self.assertFalse((out / "scene_b.jpg").is_file())
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        self.assertFalse(meta.get("has_scene_b"))
        self.assertEqual(fail_metrics.snapshot()["operator_confirmed_miss"], 1)

    def test_scene_b_from_rtsp_provider(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=0.0,
            max_per_minute=100,
            best_window_sec=0.01,
        )
        store.scene_b_delay_ms = 20
        # Distinct geometry so average-hash differs from scene A
        scene_b = np.zeros((240, 320, 3), dtype=np.uint8)
        scene_b[:] = (20, 160, 40)
        cv2.circle(scene_b, (200, 140), 50, (255, 255, 255), -1)
        cv2.rectangle(scene_b, (10, 150), (300, 220), (0, 0, 0), -1)
        cv2.putText(
            scene_b,
            "SCENE_B",
            (40, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (255, 255, 0),
            3,
        )
        store.register_frame_source("entry_camera", lambda: scene_b.copy())
        out = store.submit(
            fail_type=FAIL_TYPE_OCR_INVALID,
            frame=_solid_frame(color=(200, 30, 30)),
            camera_id="entry_camera",
            bbox=[20, 20, 120, 60],
            plate_confidence=0.9,
            immediate=True,
        )
        self.assertIsNotNone(out)
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["has_scene_b"], meta)
        self.assertEqual(meta["scene_b_source"], "rtsp_delayed")
        self.assertTrue((out / "scene_b.jpg").is_file())

    def test_scene_b_omitted_when_provider_returns_none(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=0.0,
            max_per_minute=100,
            best_window_sec=0.01,
        )
        store.scene_b_delay_ms = 10
        store.register_frame_source("entry_camera", lambda: None)
        out = store.submit(
            fail_type=FAIL_TYPE_OCR_EMPTY,
            frame=_solid_frame(),
            camera_id="entry_camera",
            bbox=[20, 20, 120, 60],
            immediate=True,
        )
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        self.assertFalse(meta.get("has_scene_b"))
        self.assertFalse((out / "scene_b.jpg").is_file())

    def test_duplicate_skipped(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=10.0,
            max_per_minute=100,
            best_window_sec=0.01,
        )
        frame = _solid_frame()
        kwargs = dict(
            fail_type=FAIL_TYPE_OCR_EMPTY,
            frame=frame,
            camera_id="entry_camera",
            plate_confidence=0.8,
            bbox=[20, 20, 120, 60],
            immediate=True,
        )
        store.submit(**kwargs)
        store.submit(**kwargs)
        captures = list(self.root.rglob("meta.json"))
        self.assertEqual(len(captures), 1)
        self.assertEqual(fail_metrics.snapshot()["duplicate_fail_skipped"], 1)

    def test_rate_limit(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=0.0,
            max_per_minute=2,
            best_window_sec=0.01,
        )
        for i in range(4):
            # Distinct frames to avoid hash dedup
            frame = _solid_frame(color=(i * 40, 10, 200 - i * 20))
            cv2.putText(
                frame,
                str(i),
                (150, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
            )
            store.submit(
                fail_type=FAIL_TYPE_OCR_EMPTY,
                frame=frame,
                camera_id="entry_camera",
                plate_confidence=0.5,
                bbox=[10 + i, 10, 100 + i, 50],
                immediate=True,
            )
        self.assertEqual(len(list(self.root.rglob("meta.json"))), 2)
        self.assertGreaterEqual(fail_metrics.snapshot()["fail_capture_rate_limited"], 1)

    def test_best_window_keeps_higher_score(self):
        store = FailCaptureStore(
            root=self.root,
            cooldown_sec=0.0,
            max_per_minute=100,
            best_window_sec=0.25,
        )
        weak = _solid_frame(color=(10, 10, 10))
        strong = _solid_frame(color=(200, 200, 200))
        store.submit(
            fail_type=FAIL_TYPE_OCR_INVALID,
            frame=weak,
            camera_id="entry_camera",
            plate_confidence=0.2,
            bbox=[20, 20, 120, 60],
        )
        store.submit(
            fail_type=FAIL_TYPE_OCR_INVALID,
            frame=strong,
            camera_id="entry_camera",
            plate_confidence=0.95,
            bbox=[20, 20, 120, 60],
        )
        time.sleep(0.4)
        store.flush_all()
        metas = list(self.root.rglob("meta.json"))
        self.assertEqual(len(metas), 1)
        meta = json.loads(metas[0].read_text(encoding="utf-8"))
        self.assertGreaterEqual(meta["plate_confidence"], 0.95)

    def test_average_hash_stable(self):
        a = average_hash(_solid_frame())
        b = average_hash(_solid_frame())
        self.assertEqual(a, b)
        self.assertTrue(len(a) > 0)


if __name__ == "__main__":
    unittest.main()

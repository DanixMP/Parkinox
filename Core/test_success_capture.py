"""Unit tests for SuccessCaptureStore (no YOLO required)."""

import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import numpy as np

from success_capture import (
    SuccessCaptureStore,
    crop_from_bbox,
    make_thumbnail,
    plate_lookup_keys,
)


class SuccessCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SuccessCaptureStore(root=Path(self.tmp.name))

    def tearDown(self):
        self.store.shutdown()
        self.tmp.cleanup()

    def _frame(self):
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        img[:] = (40, 80, 120)
        return img

    def test_buffer_and_finalize(self):
        det = str(uuid.uuid4())
        frame = self._frame()
        self.store.buffer_detection(
            detection_event_id=det,
            camera_id='entry_camera',
            plate='12ب345-17',
            confidence=0.9,
            frame=frame,
            bbox=[10, 10, 100, 40],
        )
        event_uuid = str(uuid.uuid4())
        meta = self.store.finalize(
            event_uuid=event_uuid,
            camera_id='entry_camera',
            plate='12ب345-17',
            direction='entry',
            detection_event_id=det,
        )
        self.assertFalse(meta['buffer_miss'])
        out = Path(meta['media_dir'])
        self.assertTrue((out / 'scene_a.jpg').is_file())
        self.assertTrue((out / 'crop.jpg').is_file())
        self.assertTrue((out / 'thumbnail.jpg').is_file())
        self.assertTrue((out / 'meta.json').is_file())
        loaded = json.loads((out / 'meta.json').read_text(encoding='utf-8'))
        self.assertEqual(loaded['event_uuid'], event_uuid)

    def test_finalize_buffer_miss_still_writes_meta(self):
        event_uuid = str(uuid.uuid4())
        meta = self.store.finalize(
            event_uuid=event_uuid,
            camera_id='exit_camera',
            plate='unknown',
            direction='exit',
        )
        self.assertTrue(meta['buffer_miss'])
        self.assertTrue((Path(meta['media_dir']) / 'meta.json').is_file())

    def test_camera_id_and_plate_normalize_resolves_buffer(self):
        det = str(uuid.uuid4())
        frame = self._frame()
        self.store.buffer_detection(
            detection_event_id=det,
            camera_id='entry_camera',
            plate='۳۳ س ۳۳۳ ۳۳',
            confidence=0.9,
            frame=frame,
            bbox=[10, 10, 100, 40],
        )
        # Finalize as Django/Flutter would: camera_id=entry, canonical plate
        meta = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='۳۳س۳۳۳-۳۳',
            direction='entry',
        )
        self.assertFalse(meta['buffer_miss'], meta)
        self.assertTrue(meta['files']['scene_a'])

    def test_buffer_consumed_once_no_camera_fallback(self):
        det = str(uuid.uuid4())
        self.store.buffer_detection(
            detection_event_id=det,
            camera_id='entry_camera',
            plate='33S333-33',
            confidence=0.9,
            frame=self._frame(),
            bbox=[10, 10, 100, 40],
        )
        first = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='33S333-33',
            detection_event_id=det,
        )
        self.assertFalse(first['buffer_miss'])
        # Same plate, new detection id — must NOT reuse consumed buffer
        second = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='33S333-33',
            detection_event_id=str(uuid.uuid4()),
        )
        self.assertTrue(second['buffer_miss'], second)
        self.assertFalse(any(second['files'].values()))
        # Different plate must not steal via camera fallback
        third = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='78D737-64',
            detection_event_id=str(uuid.uuid4()),
        )
        self.assertTrue(third['buffer_miss'], third)

    def test_consume_only_after_successful_write(self):
        """Buffer stays available if JPEG write fails before consume."""
        det = str(uuid.uuid4())
        self.store.buffer_detection(
            detection_event_id=det,
            camera_id='entry_camera',
            plate='12ب345-17',
            confidence=0.9,
            frame=self._frame(),
            bbox=[10, 10, 100, 40],
        )
        with mock.patch('success_capture.cv2.imencode', side_effect=RuntimeError('encode boom')):
            with self.assertRaises(RuntimeError):
                self.store.finalize(
                    event_uuid=str(uuid.uuid4()),
                    camera_id='entry',
                    plate='12ب345-17',
                    detection_event_id=det,
                )
        # Retry should still hit the buffer
        meta = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='12ب345-17',
            detection_event_id=det,
        )
        self.assertFalse(meta['buffer_miss'], meta)
        self.assertTrue(meta['files']['scene_a'])
        # Second finalize after successful write must miss (anti-reuse)
        again = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='12ب345-17',
            detection_event_id=det,
        )
        self.assertTrue(again['buffer_miss'], again)

    def test_persian_buffer_api_plate_key_hit(self):
        """OCR Persian buffer resolves when finalize sends API ASCII plate."""
        det = str(uuid.uuid4())
        self.store.buffer_detection(
            detection_event_id=det,
            camera_id='entry_camera',
            plate='12ب345-67',
            confidence=0.95,
            frame=self._frame(),
            bbox=[10, 10, 100, 40],
        )
        # No detection_event_id — plate-key fallback only
        meta = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='12B345IR67',
            direction='entry',
        )
        self.assertFalse(meta['buffer_miss'], meta)
        self.assertTrue(meta['files']['scene_a'])
        # Keys for API and Persian should overlap
        self.assertTrue(plate_lookup_keys('12ب345-67') & plate_lookup_keys('12B345IR67'))

    def test_different_plate_misses_no_camera_fallback(self):
        det = str(uuid.uuid4())
        self.store.buffer_detection(
            detection_event_id=det,
            camera_id='entry_camera',
            plate='12ب345-67',
            confidence=0.9,
            frame=self._frame(),
            bbox=[10, 10, 100, 40],
        )
        meta = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='78D737IR64',
            direction='entry',
            detection_event_id=str(uuid.uuid4()),
        )
        self.assertTrue(meta['buffer_miss'], meta)
        # Original buffer still available for the correct plate
        hit = self.store.finalize(
            event_uuid=str(uuid.uuid4()),
            camera_id='entry',
            plate='12B345IR67',
        )
        self.assertFalse(hit['buffer_miss'], hit)

    def test_crop_and_thumb_helpers(self):
        frame = self._frame()
        crop = crop_from_bbox(frame, [5, 5, 50, 30])
        self.assertIsNotNone(crop)
        thumb = make_thumbnail(frame, max_w=80)
        self.assertEqual(thumb.shape[1], 80)


if __name__ == '__main__':
    unittest.main()

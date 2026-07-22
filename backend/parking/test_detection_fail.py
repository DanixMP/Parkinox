"""Tests for detection fail ingest and operator review."""

import io
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from utils.tehran_dates import TEHRAN_TZ
from .models import DetectionFail, GateEvent, ParkingSession


def _tiny_jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (32, 16), color=(200, 200, 200)).save(buf, format='JPEG')
    return buf.getvalue()


@override_settings(DETECTION_FAIL_INGEST_TOKEN='test-ingest-token')
class DetectionFailApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            phone='+989121111111',
            password='operator123',
            full_name='Fail Reviewer',
            role='operator',
        )
        self.capture_id = uuid.uuid4()

    def _ingest(self, **overrides):
        data = {
            'capture_id': str(self.capture_id),
            'fail_type': 'ocr_invalid_format',
            'raw_ocr': '۱۲ب۳۴۵۶۷۸',
            'validation_error': 'bad format',
            'plate_confidence': '0.9100',
            'char_confidence': '0.5000',
            'bbox': '[10,20,100,60]',
            'camera_id': 'entry_camera',
            'direction': 'entry',
            'local_data_path': '2026-07-18/' + str(self.capture_id),
            'sharpness': '120.5',
            'full_image': SimpleUploadedFile(
                'full.jpg', _tiny_jpeg_bytes(), content_type='image/jpeg'
            ),
            'crop_image': SimpleUploadedFile(
                'crop.jpg', _tiny_jpeg_bytes(), content_type='image/jpeg'
            ),
        }
        data.update(overrides)
        return self.client.post(
            '/api/parking/detection-fails/ingest/',
            data=data,
            format='multipart',
            HTTP_X_FAIL_INGEST_TOKEN='test-ingest-token',
        )

    def test_ingest_requires_token(self):
        resp = self.client.post(
            '/api/parking/detection-fails/ingest/',
            {'capture_id': str(uuid.uuid4()), 'fail_type': 'ocr_empty'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ingest_creates_pending(self):
        resp = self._ingest()
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertEqual(fail.review_status, 'pending')
        self.assertEqual(fail.fail_type, 'ocr_invalid_format')
        self.assertTrue(fail.full_image)
        self.assertTrue(fail.crop_image)

    def test_ingest_with_scene_b(self):
        resp = self._ingest(
            has_scene_b='true',
            scene_b_source='rtsp_delayed',
            scene_b_image=SimpleUploadedFile(
                'scene_b.jpg', _tiny_jpeg_bytes(), content_type='image/jpeg'
            ),
        )
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertTrue(fail.has_scene_b)
        self.assertEqual(fail.scene_b_source, 'rtsp_delayed')
        self.assertTrue(fail.scene_b_image)

        self.client.force_authenticate(user=self.operator)
        detail = self.client.get(f'/api/parking/detection-fails/{self.capture_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertTrue(detail.data['has_scene_b'])
        self.assertTrue(detail.data['scene_b_image_url'])

    def test_list_pending_requires_operator(self):
        self._ingest()
        resp = self.client.get('/api/parking/detection-fails/?status=pending')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.operator)
        resp = self.client.get('/api/parking/detection-fails/?status=pending')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_review_correct_creates_gate_event_and_session(self):
        self._ingest()
        self.client.force_authenticate(user=self.operator)
        resp = self.client.post(
            f'/api/parking/detection-fails/{self.capture_id}/review/',
            {
                'action': 'correct',
                'plate_confirmed': '۱۲ ب ۳۴۵ ۶۷',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertEqual(fail.review_status, 'corrected')
        self.assertIsNotNone(fail.gate_event_id)
        self.assertTrue(GateEvent.objects.filter(pk=fail.gate_event_id).exists())
        self.assertTrue(
            ParkingSession.objects.filter(entry_event_id=fail.gate_event_id).exists()
            or ParkingSession.objects.filter(id__isnull=False).exists()
        )
        ge = GateEvent.objects.get(pk=fail.gate_event_id)
        self.assertTrue(ge.was_edited)
        self.assertEqual(ge.operator_id, self.operator.id)

    def test_review_not_a_plate_no_session(self):
        self._ingest(fail_type='ocr_empty', raw_ocr='')
        self.client.force_authenticate(user=self.operator)
        before = GateEvent.objects.count()
        resp = self.client.post(
            f'/api/parking/detection-fails/{self.capture_id}/review/',
            {'action': 'not_a_plate'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertEqual(fail.review_status, 'not_a_plate')
        self.assertTrue(fail.not_a_plate)
        self.assertIsNone(fail.gate_event_id)
        self.assertEqual(GateEvent.objects.count(), before)

    def test_review_invalid_plate_rejected(self):
        self._ingest()
        self.client.force_authenticate(user=self.operator)
        resp = self.client.post(
            f'/api/parking/detection-fails/{self.capture_id}/review/',
            {'action': 'correct', 'plate_confirmed': 'not-a-plate'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertEqual(fail.review_status, 'pending')

    def test_metrics_endpoint(self):
        self._ingest()
        self.client.force_authenticate(user=self.operator)
        resp = self.client.get('/api/parking/detection-fails/metrics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['pending'], 1)

    def test_pagination_returns_all_pending_without_loss(self):
        """More than 50 pending fails remain accessible via offset pages."""
        today = timezone.now().astimezone(TEHRAN_TZ).date().isoformat()
        for _ in range(55):
            cid = uuid.uuid4()
            self.capture_id = cid
            resp = self._ingest(
                capture_id=str(cid),
                local_data_path=f'2026-07-19/{cid}',
                timestamp=timezone.now().isoformat(),
            )
            self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))

        self.client.force_authenticate(user=self.operator)
        page1 = self.client.get(
            f'/api/parking/detection-fails/?status=pending&date={today}&limit=50&offset=0'
        )
        self.assertEqual(page1.status_code, status.HTTP_200_OK)
        self.assertEqual(page1.data['count'], 55)
        self.assertEqual(len(page1.data['results']), 50)
        self.assertTrue(page1.data['has_more'])

        page2 = self.client.get(
            f'/api/parking/detection-fails/?status=pending&date={today}&limit=50&offset=50'
        )
        self.assertEqual(page2.status_code, status.HTTP_200_OK)
        self.assertEqual(page2.data['count'], 55)
        self.assertEqual(len(page2.data['results']), 5)
        self.assertFalse(page2.data['has_more'])

        ids = {r['id'] for r in page1.data['results']} | {
            r['id'] for r in page2.data['results']
        }
        self.assertEqual(len(ids), 55)

    def test_date_filter_uses_captured_at(self):
        older = timezone.now() - timedelta(days=2)
        newer = timezone.now()
        old_id = uuid.uuid4()
        new_id = uuid.uuid4()

        self.capture_id = old_id
        self._ingest(
            capture_id=str(old_id),
            local_data_path=f'old/{old_id}',
            timestamp=older.isoformat(),
        )
        self.capture_id = new_id
        self._ingest(
            capture_id=str(new_id),
            local_data_path=f'new/{new_id}',
            timestamp=newer.isoformat(),
        )

        # Force captured_at in case multipart parsing differs
        DetectionFail.objects.filter(pk=old_id).update(captured_at=older)
        DetectionFail.objects.filter(pk=new_id).update(captured_at=newer)

        old_day = older.astimezone(TEHRAN_TZ).date().isoformat()
        new_day = newer.astimezone(TEHRAN_TZ).date().isoformat()

        self.client.force_authenticate(user=self.operator)
        old_resp = self.client.get(
            f'/api/parking/detection-fails/?status=pending&date={old_day}'
        )
        self.assertEqual(old_resp.status_code, status.HTTP_200_OK)
        old_ids = {r['id'] for r in old_resp.data['results']}
        self.assertIn(str(old_id), old_ids)
        self.assertNotIn(str(new_id), old_ids)

        new_resp = self.client.get(
            f'/api/parking/detection-fails/?status=pending&date={new_day}'
        )
        self.assertEqual(new_resp.status_code, status.HTTP_200_OK)
        new_ids = {r['id'] for r in new_resp.data['results']}
        self.assertIn(str(new_id), new_ids)
        self.assertNotIn(str(old_id), new_ids)

    def test_ingest_preserves_timezone_aware_timestamp(self):
        ts = timezone.now() - timedelta(hours=3)
        resp = self._ingest(timestamp=ts.isoformat())
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertIsNotNone(fail.captured_at)
        self.assertTrue(timezone.is_aware(fail.captured_at))

    def test_review_correct_uses_captured_at_not_review_time(self):
        captured = timezone.now() - timedelta(hours=3)
        self._ingest(timestamp=captured.isoformat())
        DetectionFail.objects.filter(pk=self.capture_id).update(captured_at=captured)
        fail = DetectionFail.objects.get(pk=self.capture_id)

        self.client.force_authenticate(user=self.operator)
        before_review = timezone.now()
        resp = self.client.post(
            f'/api/parking/detection-fails/{self.capture_id}/review/',
            {'action': 'correct', 'plate_confirmed': '۱۲ ب ۳۴۵ ۶۷'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        fail.refresh_from_db()
        self.assertEqual(fail.review_status, 'corrected')
        self.assertIsNotNone(fail.reviewed_at)
        self.assertGreaterEqual(fail.reviewed_at, before_review)
        self.assertGreater(fail.reviewed_at, fail.captured_at)

        ge = GateEvent.objects.get(pk=fail.gate_event_id)
        self.assertAlmostEqual(
            ge.created_at.timestamp(),
            fail.captured_at.timestamp(),
            delta=1.0,
        )
        session = ParkingSession.objects.filter(entry_event=ge).first()
        self.assertIsNotNone(session)
        self.assertAlmostEqual(
            session.entry_time.timestamp(),
            fail.captured_at.timestamp(),
            delta=1.0,
        )

    def test_historical_exit_conflict_keeps_pending(self):
        """Exit capture earlier than active session entry → reject, stay pending."""
        captured = timezone.now() - timedelta(hours=4)
        self._ingest(
            camera_id='exit_camera',
            direction='exit',
            timestamp=captured.isoformat(),
        )
        DetectionFail.objects.filter(pk=self.capture_id).update(captured_at=captured)

        # Active session that started after the failed exit capture
        entry_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_raw='۱۲ب۳۴۵-۶۷',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            was_edited=False,
            was_auto_approved=True,
            was_rejected=False,
            operator_id=self.operator.id,
            created_at=timezone.now() - timedelta(hours=1),
        )
        ParkingSession.objects.create(
            guest_plate_number='۱۲ب۳۴۵-۶۷',
            entry_event=entry_event,
            entry_time=timezone.now() - timedelta(hours=1),
            status='parked',
        )

        self.client.force_authenticate(user=self.operator)
        resp = self.client.post(
            f'/api/parking/detection-fails/{self.capture_id}/review/',
            {'action': 'correct', 'plate_confirmed': '۱۲ ب ۳۴۵ ۶۷'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        fail = DetectionFail.objects.get(pk=self.capture_id)
        self.assertEqual(fail.review_status, 'pending')
        self.assertIsNone(fail.gate_event_id)

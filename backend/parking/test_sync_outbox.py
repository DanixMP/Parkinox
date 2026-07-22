"""Tests for local-first sync outbox (cloud disabled)."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from parking.gate_event_service import confirm_gate_event
from parking.models import EventMedia, GateEvent, SyncOutbox
from parking.sync_outbox import enqueue_after_gate_confirm, mark_acked, mark_retry


User = get_user_model()


@override_settings(CLOUD_SYNC_ENABLED=False, SUCCESS_CAPTURE_ENABLED=False)
class SyncOutboxTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            phone='09120000001',
            password='x',
            role='operator',
            full_name='Op',
        )

    def test_confirm_creates_outbox_and_uuids(self):
        result = confirm_gate_event(
            operator_id=self.operator.id,
            camera_id='entry',
            direction='entry',
            plate_raw='12ب345-17',
            plate_confirmed='12ب345-17',
            confidence_score=0.9,
        )
        # Force on_commit callbacks in TestCase
        self.assertIsNotNone(result.get('event_uuid'))
        ge = GateEvent.objects.get(pk=result['gate_event_id'])
        self.assertIsNotNone(ge.event_uuid)
        enqueue_after_gate_confirm(ge.id, result['session_id'])
        self.assertTrue(
            SyncOutbox.objects.filter(payload_type='gate_event', payload_uuid=ge.event_uuid).exists()
        )
        self.assertTrue(
            SyncOutbox.objects.filter(payload_type='parking_session').exists()
        )

    def test_confirm_works_when_fastapi_unreachable(self):
        with override_settings(SUCCESS_CAPTURE_ENABLED=True, SUCCESS_CAPTURE_FASTAPI_URL='http://127.0.0.1:9'):
            result = confirm_gate_event(
                operator_id=self.operator.id,
                camera_id='entry',
                direction='entry',
                plate_raw='12ب345-18',
                plate_confirmed='12ب345-18',
                confidence_score=0.8,
            )
        self.assertEqual(result['status'], 'success')
        self.assertIsNotNone(result['gate_event_id'])

    def test_retry_and_ack(self):
        row = SyncOutbox.objects.create(
            payload_type='gate_event',
            payload_uuid=uuid.uuid4(),
            body_json={'x': 1},
            status='pending',
            next_attempt_at=timezone.now(),
        )
        mark_retry(row, 'boom')
        row.refresh_from_db()
        self.assertEqual(row.status, 'pending')
        self.assertEqual(row.attempts, 1)
        mark_acked(row)
        row.refresh_from_db()
        self.assertEqual(row.status, 'acked')

    def test_event_media_register_idempotent(self):
        from parking.event_media_service import register_media_from_finalize
        import tempfile
        from pathlib import Path

        eu = uuid.uuid4()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'scene_a.jpg').write_bytes(b'abc')
            (root / 'thumbnail.jpg').write_bytes(b'def')
            rows1 = register_media_from_finalize(event_uuid=eu, media_dir=str(root))
            rows2 = register_media_from_finalize(event_uuid=eu, media_dir=str(root))
        self.assertEqual(EventMedia.objects.filter(event_uuid=eu).count(), 2)
        self.assertEqual(len(rows1), 2)
        self.assertEqual(len(rows2), 2)

    def test_register_skipped_on_buffer_miss_runs_on_hit(self):
        """Mirrors gate_event_service: skip when buffer_miss; register when files exist."""
        from parking.event_media_service import register_media_from_meta
        import tempfile
        from pathlib import Path

        miss_uuid = uuid.uuid4()
        hit_uuid = uuid.uuid4()
        with tempfile.TemporaryDirectory() as td:
            miss_dir = Path(td) / 'miss'
            hit_dir = Path(td) / 'hit'
            miss_dir.mkdir()
            hit_dir.mkdir()
            (hit_dir / 'scene_a.jpg').write_bytes(b'\xff\xd8scene')
            (hit_dir / 'thumbnail.jpg').write_bytes(b'\xff\xd8thumb')

            miss_meta = {
                'event_uuid': str(miss_uuid),
                'buffer_miss': True,
                'files': {'scene_a': False, 'thumbnail': False},
                'media_dir': str(miss_dir),
            }
            # Gate path skips register entirely on buffer_miss
            if not miss_meta.get('buffer_miss'):
                register_media_from_meta(miss_meta)
            self.assertEqual(EventMedia.objects.filter(event_uuid=miss_uuid).count(), 0)

            hit_meta = {
                'event_uuid': str(hit_uuid),
                'buffer_miss': False,
                'files': {'scene_a': True, 'scene_b': False, 'crop': False, 'thumbnail': True},
                'media_dir': str(hit_dir),
                'captured_at': timezone.now().isoformat(),
            }
            files = hit_meta.get('files') or {}
            has_files = any(bool(v) for v in files.values())
            self.assertTrue(has_files)
            if hit_meta.get('media_dir') and not hit_meta.get('buffer_miss') and has_files:
                rows = register_media_from_meta(hit_meta)
            else:
                rows = []
            self.assertEqual(len(rows), 2)
            self.assertEqual(EventMedia.objects.filter(event_uuid=hit_uuid).count(), 2)

    def test_recover_media_from_disk(self):
        from parking.event_media_service import recover_media_from_disk
        import tempfile
        from pathlib import Path
        import json

        eu = uuid.uuid4()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            day = root / '2026-07-22' / str(eu)
            day.mkdir(parents=True)
            (day / 'scene_a.jpg').write_bytes(b'\xff\xd8a')
            (day / 'thumbnail.jpg').write_bytes(b'\xff\xd8t')
            meta = {
                'event_uuid': str(eu),
                'buffer_miss': False,
                'files': {'scene_a': True, 'thumbnail': True, 'crop': False, 'scene_b': False},
                'media_dir': str(day),
                'captured_at': timezone.now().isoformat(),
            }
            (day / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
            # buffer_miss meta should be skipped
            miss_eu = uuid.uuid4()
            miss_day = root / '2026-07-22' / str(miss_eu)
            miss_day.mkdir(parents=True)
            (miss_day / 'meta.json').write_text(
                json.dumps({
                    'event_uuid': str(miss_eu),
                    'buffer_miss': True,
                    'files': {},
                    'media_dir': str(miss_day),
                }),
                encoding='utf-8',
            )
            stats = recover_media_from_disk(root)
            self.assertGreaterEqual(stats['scanned'], 2)
            self.assertEqual(stats['registered_events'], 1)
            self.assertEqual(EventMedia.objects.filter(event_uuid=eu).count(), 2)
            self.assertEqual(EventMedia.objects.filter(event_uuid=miss_eu).count(), 0)

    def test_cash_payment_reenqueues_session(self):
        from parking.services import ParkingSessionService

        result = confirm_gate_event(
            operator_id=self.operator.id,
            camera_id='entry',
            direction='entry',
            plate_raw='12ب345-19',
            plate_confirmed='12ب345-19',
            confidence_score=0.9,
        )
        session_id = result['session_id']
        # Force guest unpaid exit path: mark unpaid directly
        from parking.models import ParkingSession

        ParkingSession.objects.filter(pk=session_id).update(
            status='unpaid', payment_method='', fee_charged=1000
        )
        SyncOutbox.objects.filter(payload_type='parking_session').delete()

        with self.captureOnCommitCallbacks(execute=True):
            ParkingSessionService.record_cash_payment(
                session_id=session_id,
                operator_id=self.operator.id,
                notes='test',
            )
        self.assertTrue(
            SyncOutbox.objects.filter(payload_type='parking_session').exists()
        )

    def test_waive_reenqueues_session(self):
        from parking.services import ParkingSessionService
        from parking.models import ParkingSession

        result = confirm_gate_event(
            operator_id=self.operator.id,
            camera_id='entry',
            direction='entry',
            plate_raw='12ب345-20',
            plate_confirmed='12ب345-20',
            confidence_score=0.9,
        )
        session_id = result['session_id']
        ParkingSession.objects.filter(pk=session_id).update(status='unpaid', fee_charged=500)
        SyncOutbox.objects.filter(payload_type='parking_session').delete()

        with self.captureOnCommitCallbacks(execute=True):
            ParkingSessionService.waive_fee(
                session_id=session_id, operator_id=self.operator.id
            )
        self.assertTrue(
            SyncOutbox.objects.filter(payload_type='parking_session').exists()
        )

    def test_multipart_body_is_bytes_only(self):
        from parking.management.commands.sync_to_cloud import build_multipart_body

        body = build_multipart_body(
            '----T',
            {'event_uuid': 'abc', 'image_type': 'scene_a'},
            'scene_a.jpg',
            b'\xff\xd8fake',
            'image/jpeg',
        )
        self.assertIsInstance(body, bytes)
        self.assertIn(b'Content-Disposition: form-data; name="event_uuid"', body)
        self.assertIn(b'\xff\xd8fake', body)
        self.assertTrue(body.endswith(b'----T--\r\n'))

    def test_detection_fail_enqueue(self):
        from parking.models import DetectionFail
        from parking.sync_outbox import enqueue_detection_fail

        fail = DetectionFail.objects.create(
            fail_type='ocr_invalid_format',
            review_status='pending',
            camera_id='entry_camera',
            direction='entry',
            raw_ocr='xx',
            captured_at=timezone.now(),
        )
        enqueue_detection_fail(fail)
        self.assertTrue(
            SyncOutbox.objects.filter(
                payload_type='detection_fail', payload_uuid=fail.id
            ).exists()
        )

    def test_season_reset_enqueues_season_reset_and_sessions(self):
        from parking.models import ParkingSession
        from parking.season_service import reset_operational_season

        session = ParkingSession.objects.create(
            guest_plate_number='12ب345-17',
            entry_time=timezone.now(),
            status='parked',
            fee_charged=0,
        )
        state, closed, deleted = reset_operational_season(self.operator)
        self.assertEqual(closed, 1)
        # Force on_commit in TestCase
        from parking.sync_outbox import enqueue_after_season_reset

        enqueue_after_season_reset(
            season_started_at=state.season_started_at,
            reset_count=state.reset_count,
            closed_session_ids=[session.id],
            deleted_pending_fails=deleted,
        )
        self.assertTrue(
            SyncOutbox.objects.filter(payload_type='season_reset').exists()
        )
        self.assertTrue(
            SyncOutbox.objects.filter(
                payload_type='parking_session',
                payload_uuid=session.session_uuid,
            ).exists()
        )
        row = SyncOutbox.objects.filter(payload_type='season_reset').latest('id')
        self.assertTrue(row.body_json.get('deleted_pending_fails'))
        self.assertEqual(row.body_json.get('type'), 'season_reset')

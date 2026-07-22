"""Cloud ingest + dashboard smoke tests."""

import json
import uuid

from django.conf import settings
from django.test import Client, TestCase, override_settings

from ingest.views import get_or_create_site, upsert_gate_event, upsert_session
from replica.models import (
    ReplicaDetectionFail,
    ReplicaGateEvent,
    ReplicaParkingSession,
    SiteSyncCursor,
)


class IngestIdempotentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.headers = {
            'HTTP_X_SITE_INGEST_TOKEN': settings.SITE_INGEST_TOKEN,
            'HTTP_X_SITE_ID': 'pilot-main',
        }

    def test_health_requires_token(self):
        r = self.client.get('/api/ingest/health/')
        self.assertEqual(r.status_code, 401)

    def test_health_ok(self):
        r = self.client.get('/api/ingest/health/', **self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    def test_event_upsert_no_duplicate(self):
        eid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        payload = {
            'site_id': 'pilot-main',
            'events': [
                {
                    'type': 'gate_event',
                    'event_uuid': eid,
                    'direction': 'entry',
                    'camera_id': 'entry_camera',
                    'plate_confirmed': '12ب345-67',
                    'session_uuid': sid,
                    'occurred_at': '2026-07-20T10:00:00+00:00',
                }
            ],
            'sessions': [
                {
                    'type': 'parking_session',
                    'session_uuid': sid,
                    'plate_number': '12ب345-67',
                    'status': 'parked',
                    'entry_time': '2026-07-20T10:00:00+00:00',
                    'entry_event_uuid': eid,
                    'fee_charged': 0,
                }
            ],
        }
        r1 = self.client.post(
            '/api/ingest/events/',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers,
        )
        r2 = self.client.post(
            '/api/ingest/events/',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(ReplicaGateEvent.objects.count(), 1)
        self.assertEqual(ReplicaParkingSession.objects.count(), 1)
        # events_received counts only newly created gate events (not sessions)
        self.assertEqual(r1.json()['created']['events'], 1)
        self.assertEqual(r2.json()['created']['events'], 0)
        cursor = SiteSyncCursor.objects.get(site__site_id='pilot-main')
        self.assertEqual(cursor.events_received, 1)

    def test_events_received_not_inflated_by_session(self):
        eid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        payload = {
            'site_id': 'pilot-main',
            'type': 'gate_event',
            'event_uuid': eid,
            'direction': 'entry',
            'camera_id': 'entry_camera',
            'plate_confirmed': '12ب111-11',
            'session_uuid': sid,
        }
        r1 = self.client.post(
            '/api/ingest/events/',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers,
        )
        session_payload = {
            'site_id': 'pilot-main',
            'type': 'parking_session',
            'session_uuid': sid,
            'plate_number': '12ب111-11',
            'status': 'parked',
            'entry_event_uuid': eid,
            'fee_charged': 0,
        }
        r2 = self.client.post(
            '/api/ingest/events/',
            data=json.dumps(session_payload),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        cursor = SiteSyncCursor.objects.get(site__site_id='pilot-main')
        self.assertEqual(cursor.events_received, 1)

    def test_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        site = get_or_create_site('pilot-main')
        eid = uuid.uuid4()
        upsert_gate_event(
            site,
            {
                'event_uuid': str(eid),
                'direction': 'entry',
                'camera_id': 'entry_camera',
                'plate_confirmed': '12ب345-67',
            },
        )
        f = SimpleUploadedFile('scene_a.jpg', b'\xff\xd8\xff\xd9fakejpeg', content_type='image/jpeg')
        r = self.client.post(
            '/api/ingest/images/',
            data={
                'event_uuid': str(eid),
                'image_type': 'scene_a',
                'content_hash': 'abc',
                'file': f,
            },
            **self.headers,
        )
        self.assertIn(r.status_code, (200, 201))
        self.assertTrue(r.json()['success'])

    def test_ingest_season_reset_clears_pending_fails(self):
        site = get_or_create_site('pilot-main')
        pending_id = uuid.uuid4()
        ReplicaDetectionFail.objects.create(
            site=site,
            fail_uuid=pending_id,
            fail_type='ocr_invalid_format',
            review_status='pending',
            camera_id='entry',
            direction='entry',
        )
        payload = {
            'site_id': 'pilot-main',
            'season_resets': [
                {
                    'type': 'season_reset',
                    'season_started_at': '2026-07-22T12:00:00+00:00',
                    'deleted_pending_fails': True,
                    'reset_count': 1,
                }
            ],
        }
        r = self.client.post(
            '/api/ingest/events/',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['accepted']['season_resets'], 1)
        self.assertFalse(
            ReplicaDetectionFail.objects.filter(fail_uuid=pending_id).exists()
        )
        site.refresh_from_db()
        self.assertIsNotNone(site.season_started_at)


@override_settings(DASHBOARD_USERNAME='admin', DASHBOARD_PASSWORD='secret')
class DashboardAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        get_or_create_site('pilot-main')

    def test_overview_requires_login(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 302)

    def test_login_and_overview(self):
        r = self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        self.assertEqual(r.status_code, 302)
        r2 = self.client.get('/')
        self.assertEqual(r2.status_code, 200)

    def test_parked_and_history(self):
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        self.assertEqual(self.client.get('/parked/').status_code, 200)
        self.assertEqual(self.client.get('/history/').status_code, 200)
        self.assertEqual(self.client.get('/analytics/').status_code, 200)

    def test_excel_export(self):
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.get('/reports/excel/?type=sessions')
        self.assertEqual(r.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            r['Content-Type'],
        )

    def test_pdf_export(self):
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.get('/reports/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_fails_page(self):
        site = get_or_create_site('pilot-main')
        ReplicaDetectionFail.objects.create(
            site=site,
            fail_uuid=uuid.uuid4(),
            fail_type='ocr_invalid_format',
            review_status='pending',
            camera_id='entry_camera',
            direction='entry',
            raw_ocr='xx',
        )
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.get('/fails/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ocr_invalid_format')
        overview = self.client.get('/')
        self.assertContains(overview, 'بررسی دستی در انتظار')

    def test_history_has_plate_input(self):
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.get('/history/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'plate-input-ir')
        self.assertContains(r, 'jalali-date-input')
        self.assertContains(r, 'jalali-datepicker.js')

    def test_overview_clickable_kpis_and_logos(self):
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'kpi-link')
        self.assertContains(r, 'focus=exits')
        self.assertContains(r, 'iau_logo.png')
        self.assertContains(r, 'پارکینوکس')
        self.assertContains(r, 'chart-canvas-host', count=0)  # overview has no charts
        analytics = self.client.get('/analytics/')
        self.assertEqual(analytics.status_code, 200)
        self.assertContains(analytics, 'chart-canvas-host')

    def test_history_focus_exits(self):
        from django.utils import timezone
        from datetime import timedelta

        site = get_or_create_site('pilot-main')
        now = timezone.now()
        ReplicaParkingSession.objects.create(
            site=site,
            session_uuid=uuid.uuid4(),
            plate_number='12ب111-11',
            status='completed',
            entry_time=now - timedelta(days=2),
            exit_time=now,
            fee_charged=1000,
        )
        ReplicaParkingSession.objects.create(
            site=site,
            session_uuid=uuid.uuid4(),
            plate_number='12ب222-22',
            status='parked',
            entry_time=now,
            fee_charged=0,
        )
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        from dashboard.jalali import to_jalali_str
        from datetime import date

        today = to_jalali_str(date.today())
        r = self.client.get(f'/history/?from={today}&to={today}&focus=exits')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '12ب111-11')
        self.assertNotContains(r, '12ب222-22')

    @override_settings(
        LOCAL_SITE_API_URL='http://127.0.0.1:8001',
        LOCAL_SITE_OPERATOR_PHONE='09120000000',
        LOCAL_SITE_OPERATOR_PASSWORD='op',
        DASHBOARD_USERNAME='admin',
        DASHBOARD_PASSWORD='secret',
    )
    def test_season_reset_proxy(self):
        from unittest.mock import patch

        site = get_or_create_site('pilot-main')
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        with patch('dashboard.views.reset_local_season') as mock_reset:
            mock_reset.return_value = (True, 'ok', {'closed_sessions': 2})
            r = self.client.post(
                '/season/reset/',
                {'password': 'secret', 'next': '/', 'site': site.site_id},
            )
        self.assertEqual(r.status_code, 302)
        mock_reset.assert_called_once()

    @override_settings(
        LOCAL_SITE_API_URL='',
        DASHBOARD_USERNAME='admin',
        DASHBOARD_PASSWORD='secret',
    )
    def test_season_button_enabled_without_local_proxy(self):
        get_or_create_site('pilot-main')
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="open-season-reset"')
        self.assertNotContains(r, 'LOCAL_SITE_API_URL لازم است')
        self.assertContains(r, 'بازنشانی روی ابر')

    @override_settings(
        LOCAL_SITE_API_URL='',
        DASHBOARD_USERNAME='admin',
        DASHBOARD_PASSWORD='secret',
    )
    def test_season_reset_clears_pending_fails_without_local(self):
        site = get_or_create_site('pilot-main')
        ReplicaDetectionFail.objects.create(
            site=site,
            fail_uuid=uuid.uuid4(),
            fail_type='ocr_invalid_format',
            review_status='pending',
            camera_id='entry',
            direction='entry',
        )
        ReplicaDetectionFail.objects.create(
            site=site,
            fail_uuid=uuid.uuid4(),
            fail_type='ocr_empty',
            review_status='corrected',
            camera_id='exit',
            direction='exit',
        )
        self.client.post('/login/', {'username': 'admin', 'password': 'secret'})
        r = self.client.post(
            '/season/reset/',
            {'password': 'secret', 'next': '/', 'site': site.site_id},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            ReplicaDetectionFail.objects.filter(site=site, review_status='pending').count(),
            0,
        )
        self.assertEqual(
            ReplicaDetectionFail.objects.filter(site=site, review_status='corrected').count(),
            1,
        )
        site.refresh_from_db()
        self.assertIsNotNone(site.season_started_at)


class JalaliHelperTests(TestCase):
    def test_parse_and_format(self):
        from dashboard.jalali import parse_jalali_date, to_jalali_str
        from datetime import datetime, date
        from zoneinfo import ZoneInfo

        start, end = parse_jalali_date('۱۴۰۴/۰۴/۳۰')
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertGreater(end, start)
        dt = datetime(2025, 7, 21, 12, 0, tzinfo=ZoneInfo('Asia/Tehran'))
        s = to_jalali_str(dt, with_time=True)
        self.assertIn('/', s)
        self.assertTrue(any(c in s for c in '۰۱۲۳۴۵۶۷۸۹'))
        self.assertIn('/', to_jalali_str(date.today()))


class LocalSiteProxyTests(TestCase):
    @override_settings(LOCAL_SITE_API_URL='')
    def test_not_configured(self):
        from dashboard.local_site import local_season_configured, reset_local_season

        self.assertFalse(local_season_configured())
        ok, msg, _ = reset_local_season()
        self.assertFalse(ok)
        self.assertIn('LOCAL_SITE_API_URL', msg)

    @override_settings(
        LOCAL_SITE_API_URL='http://127.0.0.1:8001',
        LOCAL_SITE_OPERATOR_PHONE='0912',
        LOCAL_SITE_OPERATOR_PASSWORD='x',
    )
    def test_reset_success_mocked(self):
        from unittest.mock import patch
        from dashboard.local_site import reset_local_season

        with patch('dashboard.local_site._post_json') as post:
            post.side_effect = [
                (200, {'access_token': 'tok'}),
                (200, {'closed_sessions': 1, 'reset_count': 2}),
            ]
            ok, msg, payload = reset_local_season()
        self.assertTrue(ok)
        self.assertEqual(payload['closed_sessions'], 1)
        self.assertEqual(post.call_count, 2)
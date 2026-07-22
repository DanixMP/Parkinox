"""
Push local SyncOutbox rows to the cloud reporting replica.

Usage:
  python manage.py sync_to_cloud
  python manage.py sync_to_cloud --once
  python manage.py sync_to_cloud --images-only
  python manage.py sync_to_cloud --catch-up --once
"""

from __future__ import annotations

import json
import logging
import mimetypes
import time
import uuid as uuid_lib
from datetime import timedelta
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from parking.models import (
    DetectionFail,
    EventMedia,
    GateEvent,
    ParkingSession,
    SyncOutbox,
    SyncState,
)
from parking.sync_outbox import (
    claim_batch,
    enqueue_after_gate_confirm,
    enqueue_detection_fail,
    enqueue_parking_session_update,
    mark_acked,
    mark_retry,
    refresh_sync_state,
)

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SEC = 60.0
RECONCILE_CHUNK = 500
STALE_SENDING_SEC = 120
IMAGE_BATCH_MAX = 3


def build_multipart_body(boundary: str, fields: dict, filename: str, file_bytes: bytes, content_type: str) -> bytes:
    """Build a multipart/form-data body entirely as bytes (no str+bytes mix)."""
    parts = []
    for k, v in fields.items():
        parts.append(
            (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                f'{v}\r\n'
            ).encode('utf-8')
        )
    parts.append(
        (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'
        ).encode('utf-8')
        + file_bytes
        + b'\r\n'
    )
    parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
    return b''.join(parts)


class Command(BaseCommand):
    help = 'Drain SyncOutbox to CLOUD_BASE_URL (metadata first, then images).'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Single drain pass then exit')
        parser.add_argument('--images-only', action='store_true')
        parser.add_argument('--metadata-only', action='store_true')
        parser.add_argument('--sleep', type=float, default=5.0)
        parser.add_argument('--batch', type=int, default=20)
        parser.add_argument(
            '--catch-up',
            action='store_true',
            help='Reconcile missing UUIDs / re-enqueue recent rows, then drain until empty',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'CLOUD_SYNC_ENABLED', False):
            self.stdout.write(self.style.WARNING('CLOUD_SYNC_ENABLED=false — nothing to do'))
            return

        base = getattr(settings, 'CLOUD_BASE_URL', '').rstrip('/')
        token = getattr(settings, 'CLOUD_SITE_INGEST_TOKEN', '')
        site_id = getattr(settings, 'CLOUD_SITE_ID', 'pilot-main')
        if not base or not token:
            self.stderr.write('CLOUD_BASE_URL / CLOUD_SITE_INGEST_TOKEN required')
            return

        once = options['once']
        sleep_s = options['sleep']
        batch = options['batch']
        catch_up = options['catch_up']
        last_heartbeat_at = 0.0

        # Immediate freshness signal so dashboard is not stale while catch-up/drain runs
        if self._heartbeat(base, token, site_id):
            last_heartbeat_at = time.monotonic()

        if catch_up:
            enqueued = self._catch_up(base, token, site_id)
            self.stdout.write(self.style.NOTICE(f'Catch-up enqueued ~{enqueued} rows'))
            drained = self._drain_until_empty(
                base,
                token,
                site_id,
                batch,
                images_only=options['images_only'],
                metadata_only=options['metadata_only'],
            )
            self.stdout.write(self.style.SUCCESS(f'Catch-up drain complete (processed ~{drained})'))
            self._heartbeat(base, token, site_id)
            last_heartbeat_at = time.monotonic()
            if once:
                return

        while True:
            try:
                self._reclaim_stale_sending()
                sent = 0
                if not options['images_only']:
                    sent += self._drain_metadata(base, token, site_id, batch)
                if not options['metadata_only']:
                    sent += self._drain_images(
                        base, token, site_id, min(batch, IMAGE_BATCH_MAX)
                    )
                refresh_sync_state()

                now_mono = time.monotonic()
                # Keep cloud last_ingest_at fresh even while drains fail / retry.
                if (now_mono - last_heartbeat_at) >= HEARTBEAT_INTERVAL_SEC:
                    if self._heartbeat(base, token, site_id):
                        last_heartbeat_at = now_mono
                    else:
                        # Back off a bit on failure so we do not hammer a down host
                        last_heartbeat_at = now_mono

                if once:
                    # Ensure dashboard freshness even on a single idle pass
                    if last_heartbeat_at == 0.0:
                        self._heartbeat(base, token, site_id)
                    self.stdout.write(
                        self.style.SUCCESS(f'Drain complete (processed ~{sent})')
                    )
                    return
            except Exception:
                logger.exception('sync_to_cloud loop iteration failed; continuing')
                self.stderr.write('sync_to_cloud loop error — see logs; continuing')
                if once:
                    raise
            time.sleep(sleep_s)

    def _headers(self, token: str, site_id: str, idempotency_key: str) -> dict:
        return {
            'X-Site-Ingest-Token': token,
            'X-Site-Id': site_id,
            'Idempotency-Key': idempotency_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _post_json(self, url: str, headers: dict, body: dict) -> tuple[int, str]:
        data = json.dumps(body).encode('utf-8')
        req = urlrequest.Request(url, data=data, headers=headers, method='POST')
        try:
            with urlrequest.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode('utf-8', errors='replace')
        except urlerror.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace')
        except Exception as e:
            return 0, str(e)

    def _mark_local_success(self) -> None:
        state = SyncState.get_singleton()
        state.last_success_at = timezone.now()
        state.last_error = ''
        state.save(update_fields=['last_success_at', 'last_error', 'updated_at'])

    def _reclaim_stale_sending(self) -> int:
        """Return rows left in 'sending' after a killed worker to pending."""
        cutoff = timezone.now() - timedelta(seconds=STALE_SENDING_SEC)
        updated = SyncOutbox.objects.filter(
            status='sending', updated_at__lt=cutoff
        ).update(status='pending', next_attempt_at=timezone.now())
        if updated:
            logger.warning('Reclaimed %s stale sending SyncOutbox rows', updated)
        return updated

    def _heartbeat(self, base: str, token: str, site_id: str) -> bool:
        """Empty ingest POST so cloud Site.last_ingest_at stays fresh while idle."""
        key = f'heartbeat-{site_id}-{int(time.time())}'
        status_code, text = self._post_json(
            f'{base}/api/ingest/events/',
            self._headers(token, site_id, key),
            {
                'site_id': site_id,
                'events': [],
                'sessions': [],
                'detection_fails': [],
            },
        )
        if 200 <= status_code < 300:
            self._mark_local_success()
            self.stdout.write(f'Heartbeat ok ({status_code})')
            return True
        self.stderr.write(f'Heartbeat failed HTTP {status_code}: {text[:300]}')
        state = SyncState.get_singleton()
        state.last_error_at = timezone.now()
        state.last_error = f'heartbeat HTTP {status_code}: {text[:500]}'
        state.save(update_fields=['last_error_at', 'last_error', 'updated_at'])
        return False

    def _catch_up_since(self):
        state = SyncState.get_singleton()
        if state.last_success_at:
            return state.last_success_at
        return timezone.now() - timedelta(hours=24)

    def _catch_up(self, base: str, token: str, site_id: str) -> int:
        """Reconcile missing UUIDs and re-enqueue recent local rows."""
        enqueued = 0
        enqueued += self._recover_parking_media()
        enqueued += self._reconcile_missing(base, token, site_id)
        since = self._catch_up_since()
        self.stdout.write(f'Catch-up since {since.isoformat()}')

        for ge in GateEvent.objects.filter(created_at__gte=since).only('id', 'session_id').iterator(
            chunk_size=200
        ):
            enqueue_after_gate_confirm(ge.id, ge.session_id)
            enqueued += 1

        session_qs = ParkingSession.objects.filter(
            Q(created_at__gte=since) | Q(exit_time__gte=since)
        ).values_list('id', flat=True)
        for sid in session_qs.iterator(chunk_size=200):
            enqueue_parking_session_update(sid)
            enqueued += 1

        for fail in DetectionFail.objects.filter(created_at__gte=since).iterator(chunk_size=100):
            enqueue_detection_fail(fail)
            enqueued += 1

        refresh_sync_state()
        return enqueued

    def _recover_parking_media(self) -> int:
        """Register orphan parking_media metas and force-requeue EventMedia uploads."""
        from parking.event_media_service import force_requeue_event_media, recover_media_from_disk

        stats = recover_media_from_disk()
        self.stdout.write(
            f"Media disk recover: scanned={stats['scanned']} "
            f"new_events={stats['registered_events']} "
            f"rows={stats['registered_rows']} skipped={stats['skipped']}"
        )
        requeued = force_requeue_event_media()
        self.stdout.write(f'Media force-requeue: {requeued} EventMedia rows')
        return stats['registered_rows'] + requeued

    def _reconcile_missing(self, base: str, token: str, site_id: str) -> int:
        """Ask cloud which local UUIDs are missing and re-enqueue those."""
        enqueued = 0
        event_uuids = [
            str(u)
            for u in GateEvent.objects.exclude(event_uuid__isnull=True).values_list(
                'event_uuid', flat=True
            )
        ]
        session_uuids = [
            str(u)
            for u in ParkingSession.objects.exclude(session_uuid__isnull=True).values_list(
                'session_uuid', flat=True
            )
        ]

        missing_events: list[str] = []
        missing_sessions: list[str] = []

        for i in range(0, max(len(event_uuids), 1), RECONCILE_CHUNK):
            chunk_e = event_uuids[i : i + RECONCILE_CHUNK]
            chunk_s = session_uuids[i : i + RECONCILE_CHUNK] if i < len(session_uuids) else []
            # Also send remaining session chunks when events are done
            if not chunk_e and not chunk_s:
                break
            body = {
                'site_id': site_id,
                'event_uuids': chunk_e,
                'session_uuids': chunk_s,
            }
            key = f'reconcile-{site_id}-{i}-{uuid_lib.uuid4().hex[:8]}'
            status_code, text = self._post_json(
                f'{base}/api/ingest/reconcile/',
                self._headers(token, site_id, key),
                body,
            )
            if not (200 <= status_code < 300):
                self.stderr.write(f'Reconcile failed HTTP {status_code}: {text[:300]}')
                continue
            try:
                data = json.loads(text or '{}')
            except json.JSONDecodeError:
                continue
            missing_events.extend(data.get('missing_event_uuids') or [])
            missing_sessions.extend(data.get('missing_session_uuids') or [])

        # Finish leftover session UUID chunks not covered by event-aligned loop
        for i in range(0, len(session_uuids), RECONCILE_CHUNK):
            if i < len(event_uuids):
                # already sent alongside events above
                continue
            chunk_s = session_uuids[i : i + RECONCILE_CHUNK]
            body = {'site_id': site_id, 'event_uuids': [], 'session_uuids': chunk_s}
            key = f'reconcile-sess-{site_id}-{i}-{uuid_lib.uuid4().hex[:8]}'
            status_code, text = self._post_json(
                f'{base}/api/ingest/reconcile/',
                self._headers(token, site_id, key),
                body,
            )
            if not (200 <= status_code < 300):
                self.stderr.write(f'Reconcile sessions failed HTTP {status_code}: {text[:300]}')
                continue
            try:
                data = json.loads(text or '{}')
            except json.JSONDecodeError:
                continue
            missing_sessions.extend(data.get('missing_session_uuids') or [])

        missing_events = sorted(set(missing_events))
        missing_sessions = sorted(set(missing_sessions))
        self.stdout.write(
            f'Reconcile missing events={len(missing_events)} sessions={len(missing_sessions)}'
        )

        if missing_events:
            for ge in GateEvent.objects.filter(event_uuid__in=missing_events).only(
                'id', 'session_id'
            ):
                enqueue_after_gate_confirm(ge.id, ge.session_id)
                enqueued += 1

        if missing_sessions:
            for sid in ParkingSession.objects.filter(session_uuid__in=missing_sessions).values_list(
                'id', flat=True
            ):
                enqueue_parking_session_update(sid)
                enqueued += 1

        return enqueued

    def _drain_until_empty(
        self,
        base: str,
        token: str,
        site_id: str,
        batch: int,
        *,
        images_only: bool,
        metadata_only: bool,
        max_rounds: int = 500,
    ) -> int:
        total = 0
        for _ in range(max_rounds):
            self._reclaim_stale_sending()
            SyncOutbox.objects.filter(status='sending').update(
                status='pending', next_attempt_at=timezone.now()
            )
            pending = SyncOutbox.objects.filter(status='pending').count()
            if pending == 0:
                break
            sent = 0
            if not images_only:
                sent += self._drain_metadata(base, token, site_id, batch)
            if not metadata_only:
                sent += self._drain_images(
                    base, token, site_id, min(batch, IMAGE_BATCH_MAX)
                )
            refresh_sync_state()
            total += sent
            if sent == 0:
                # Retries scheduled in the future — stop to avoid spin
                break
        return total

    def _drain_metadata(self, base: str, token: str, site_id: str, batch: int) -> int:
        rows = claim_batch(batch, images=False)
        if not rows:
            return 0
        events = []
        sessions = []
        fails = []
        season_resets = []
        for row in rows:
            body = dict(row.body_json or {})
            body['site_id'] = site_id
            ptype = row.payload_type
            if ptype == 'gate_event':
                events.append(body)
            elif ptype == 'parking_session':
                sessions.append(body)
            elif ptype == 'detection_fail':
                fails.append(body)
            elif ptype == 'season_reset':
                season_resets.append(body)

        payload = {
            'site_id': site_id,
            'events': events,
            'sessions': sessions,
            'detection_fails': fails,
            'season_resets': season_resets,
        }
        key = rows[0].payload_uuid.hex if len(rows) == 1 else f'batch-{rows[0].id}-{rows[-1].id}'
        status_code, text = self._post_json(
            f'{base}/api/ingest/events/',
            self._headers(token, site_id, key),
            payload,
        )
        if 200 <= status_code < 300:
            for row in rows:
                mark_acked(row)
            self._mark_local_success()
            return len(rows)

        for row in rows:
            mark_retry(row, f'HTTP {status_code}: {text[:500]}')
        return 0

    def _drain_images(self, base: str, token: str, site_id: str, batch: int) -> int:
        rows = claim_batch(batch, images=True)
        ok_count = 0
        for row in rows:
            body = row.body_json or {}
            local_path = body.get('local_path') or ''
            path = Path(local_path)
            if not path.is_file():
                mark_retry(row, f'Missing local file: {local_path}')
                continue
            boundary = f'----Parkinox{row.id}'
            file_bytes = path.read_bytes()
            content_type = mimetypes.guess_type(str(path))[0] or 'image/jpeg'
            fields = {
                'event_uuid': str(body.get('event_uuid') or ''),
                'image_type': str(body.get('image_type') or ''),
                'content_hash': str(body.get('content_hash') or ''),
                'session_uuid': str(body.get('session_uuid') or ''),
                'size_bytes': str(body.get('size_bytes') or len(file_bytes)),
            }
            data = build_multipart_body(
                boundary, fields, path.name, file_bytes, content_type
            )
            headers = {
                'X-Site-Ingest-Token': token,
                'X-Site-Id': site_id,
                'Idempotency-Key': str(row.payload_uuid),
                'Content-Type': f'multipart/form-data; boundary={boundary}',
            }
            req = urlrequest.Request(
                f'{base}/api/ingest/images/',
                data=data,
                headers=headers,
                method='POST',
            )
            try:
                with urlrequest.urlopen(req, timeout=60) as resp:
                    status_code = resp.status
                    resp.read()
            except urlerror.HTTPError as e:
                status_code = e.code
                err = e.read().decode('utf-8', errors='replace')
                mark_retry(row, f'HTTP {status_code}: {err[:500]}')
                continue
            except Exception as e:
                mark_retry(row, str(e))
                continue

            if 200 <= status_code < 300:
                mark_acked(row)
                EventMedia.objects.filter(
                    event_uuid=body.get('event_uuid'),
                    image_type=body.get('image_type'),
                ).update(upload_status='uploaded')
                ok_count += 1
                self._mark_local_success()
            else:
                mark_retry(row, f'HTTP {status_code}')
        return ok_count

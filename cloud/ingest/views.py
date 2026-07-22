"""Idempotent cloud ingest for reporting replica."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from replica.models import (
    Camera,
    Gate,
    Organization,
    ReplicaDetectionFail,
    ReplicaEventMedia,
    ReplicaGateEvent,
    ReplicaParkingSession,
    Site,
    SiteSyncCursor,
)

from .auth import require_site_token


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    dt = parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt


def get_or_create_site(site_id: str) -> Site:
    org = Organization.objects.order_by('created_at').first()
    if org is None:
        org = Organization.objects.create(name=settings.DEFAULT_ORG_NAME)
    site, created = Site.objects.get_or_create(
        site_id=site_id,
        defaults={
            'organization': org,
            'name': site_id,
            'capacity': settings.PARKING_CAPACITY,
        },
    )
    for code, direction in (('entry', 'entry'), ('exit', 'exit')):
        Gate.objects.get_or_create(
            site=site, code=code, defaults={'direction': direction, 'name': code}
        )
        Camera.objects.get_or_create(
            site=site,
            camera_id=f'{code}_camera',
            defaults={'name': code},
        )
    return site


def upsert_gate_event(site: Site, body: dict) -> tuple:
    event_uuid = uuid.UUID(str(body['event_uuid']))
    operator = body.get('operator') or {}
    matched = body.get('matched_user') or {}
    local_ids = body.get('local_ids') or {}
    obj, created = ReplicaGateEvent.objects.update_or_create(
        site=site,
        event_uuid=event_uuid,
        defaults={
            'occurred_at': _parse_dt(body.get('occurred_at')),
            'direction': body.get('direction') or '',
            'camera_id': body.get('camera_id') or '',
            'plate_raw': body.get('plate_raw') or '',
            'plate_confirmed': body.get('plate_confirmed') or '',
            'confidence': body.get('confidence'),
            'was_edited': bool(body.get('was_edited')),
            'was_auto_approved': bool(body.get('was_auto_approved')),
            'was_rejected': bool(body.get('was_rejected')),
            'session_uuid': uuid.UUID(str(body['session_uuid'])) if body.get('session_uuid') else None,
            'operator_name': operator.get('name') or '',
            'matched_user_name': matched.get('full_name') or '',
            'local_gate_event_id': local_ids.get('gate_event_id'),
            'payload': body,
        },
    )
    return obj, created


def upsert_session(site: Site, body: dict) -> tuple:
    session_uuid = uuid.UUID(str(body['session_uuid']))
    local_ids = body.get('local_ids') or {}
    obj, created = ReplicaParkingSession.objects.update_or_create(
        site=site,
        session_uuid=session_uuid,
        defaults={
            'plate_number': body.get('plate_number') or '',
            'user_name': body.get('user_name') or '',
            'entry_time': _parse_dt(body.get('entry_time')),
            'exit_time': _parse_dt(body.get('exit_time')),
            'duration_minutes': body.get('duration_minutes'),
            'fee_charged': int(body.get('fee_charged') or 0),
            'status': body.get('status') or 'parked',
            'payment_method': body.get('payment_method') or '',
            'entry_event_uuid': uuid.UUID(str(body['entry_event_uuid'])) if body.get('entry_event_uuid') else None,
            'exit_event_uuid': uuid.UUID(str(body['exit_event_uuid'])) if body.get('exit_event_uuid') else None,
            'entry_camera_id': body.get('entry_camera_id') or '',
            'exit_camera_id': body.get('exit_camera_id') or '',
            'notes': body.get('notes') or '',
            'local_session_id': local_ids.get('session_id'),
            'payload': body,
        },
    )
    return obj, created


def upsert_fail(site: Site, body: dict) -> tuple:
    fail_uuid = uuid.UUID(str(body.get('fail_uuid') or body.get('id') or body.get('capture_id')))
    obj, created = ReplicaDetectionFail.objects.update_or_create(
        site=site,
        fail_uuid=fail_uuid,
        defaults={
            'fail_type': body.get('fail_type') or '',
            'review_status': body.get('review_status') or 'pending',
            'camera_id': body.get('camera_id') or '',
            'direction': body.get('direction') or '',
            'raw_ocr': body.get('raw_ocr') or '',
            'was_corrected': bool(body.get('was_corrected')),
            'captured_at': _parse_dt(body.get('captured_at')),
            'payload': body,
        },
    )
    return obj, created


def apply_season_reset(site: Site, body: dict) -> dict:
    """
    Apply an operational season reset on the cloud replica.

    Deletes pending detection fails; records season_started_at on Site.
    Closed sessions are expected as separate session upserts in the same batch
    or earlier outbox rows.
    """
    now = timezone.now()
    season_started = _parse_dt(body.get('season_started_at')) or now
    deleted_fails, _ = ReplicaDetectionFail.objects.filter(
        site=site,
        review_status='pending',
    ).delete()

    # Close any replica sessions still parked/unpaid (mirrors local semantics)
    closed = 0
    for session in ReplicaParkingSession.objects.filter(
        site=site, status__in=['parked', 'unpaid']
    ):
        if session.exit_time is None:
            session.exit_time = season_started
        if session.entry_time and session.exit_time:
            duration_seconds = (session.exit_time - session.entry_time).total_seconds()
            session.duration_minutes = max(0, int(duration_seconds // 60))
        session.status = 'waived'
        session.payment_method = 'waived'
        note_suffix = '[Season reset]'
        existing = (session.notes or '').strip()
        session.notes = f'{existing} {note_suffix}'.strip() if existing else note_suffix
        session.save(
            update_fields=[
                'exit_time',
                'duration_minutes',
                'status',
                'payment_method',
                'notes',
            ]
        )
        closed += 1

    site.season_started_at = season_started
    site.last_ingest_at = now
    site.save(update_fields=['season_started_at', 'last_ingest_at'])
    return {
        'deleted_pending_fails': deleted_fails,
        'closed_sessions': closed,
        'season_started_at': season_started.isoformat(),
    }

@csrf_exempt
@require_GET
@require_site_token
def health(request):
    site = get_or_create_site(request.site_id)
    cursor, _ = SiteSyncCursor.objects.get_or_create(site=site)
    return JsonResponse(
        {
            'ok': True,
            'site_id': site.site_id,
            'last_ingest_at': site.last_ingest_at.isoformat() if site.last_ingest_at else None,
            'events_received': cursor.events_received,
            'images_received': cursor.images_received,
        }
    )


@csrf_exempt
@require_POST
@require_site_token
def ingest_events(request):
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    site_id = body.get('site_id') or request.site_id
    site = get_or_create_site(site_id)
    accepted = {
        'events': 0,
        'sessions': 0,
        'detection_fails': 0,
        'season_resets': 0,
    }
    created_counts = {'events': 0, 'sessions': 0, 'detection_fails': 0}
    season_reset_result = None

    for item in body.get('events') or []:
        if not item.get('event_uuid'):
            continue
        _, created = upsert_gate_event(site, item)
        accepted['events'] += 1
        if created:
            created_counts['events'] += 1

    for item in body.get('sessions') or []:
        if not item.get('session_uuid'):
            continue
        _, created = upsert_session(site, item)
        accepted['sessions'] += 1
        if created:
            created_counts['sessions'] += 1

    for item in body.get('detection_fails') or []:
        _, created = upsert_fail(site, item)
        accepted['detection_fails'] += 1
        if created:
            created_counts['detection_fails'] += 1

    for item in body.get('season_resets') or []:
        season_reset_result = apply_season_reset(site, item or {})
        accepted['season_resets'] += 1

    # Also accept a single event/session at top level
    if body.get('type') == 'gate_event' and body.get('event_uuid'):
        _, created = upsert_gate_event(site, body)
        accepted['events'] += 1
        if created:
            created_counts['events'] += 1
    if body.get('type') == 'parking_session' and body.get('session_uuid'):
        _, created = upsert_session(site, body)
        accepted['sessions'] += 1
        if created:
            created_counts['sessions'] += 1
    if body.get('type') == 'detection_fail':
        _, created = upsert_fail(site, body)
        accepted['detection_fails'] += 1
        if created:
            created_counts['detection_fails'] += 1
    if body.get('type') == 'season_reset':
        season_reset_result = apply_season_reset(site, body)
        accepted['season_resets'] += 1

    now = timezone.now()
    site.last_ingest_at = now
    site.save(update_fields=['last_ingest_at'])
    cursor, _ = SiteSyncCursor.objects.get_or_create(site=site)
    # Count only newly created gate events (matches real-world event count)
    cursor.events_received += created_counts['events']
    cursor.last_event_at = now
    cursor.save(update_fields=['events_received', 'last_event_at', 'updated_at'])

    resp = {
        'success': True,
        'accepted': accepted,
        'created': created_counts,
        'gate_event_total': ReplicaGateEvent.objects.filter(site=site).count(),
    }
    if season_reset_result is not None:
        resp['season_reset'] = season_reset_result
    return JsonResponse(resp)

@csrf_exempt
@require_POST
@require_site_token
def ingest_images(request):
    site = get_or_create_site(request.site_id)
    event_uuid = request.POST.get('event_uuid')
    image_type = request.POST.get('image_type')
    content_hash = request.POST.get('content_hash') or ''
    session_uuid = request.POST.get('session_uuid') or None
    upload = request.FILES.get('file')
    if not event_uuid or not image_type or not upload:
        return JsonResponse({'error': 'event_uuid, image_type, file required'}, status=400)

    raw = upload.read()
    if not content_hash:
        content_hash = hashlib.sha256(raw).hexdigest()

    # Deduplicate by content hash within site+event+type already unique
    rel_dir = f'events/{site.site_id}/{event_uuid}'
    filename = f'{image_type}.jpg'
    abs_dir = settings.MEDIA_ROOT / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = abs_dir / filename
    abs_path.write_bytes(raw)
    object_key = f'{rel_dir}/{filename}'.replace('\\', '/')

    media, created = ReplicaEventMedia.objects.update_or_create(
        site=site,
        event_uuid=uuid.UUID(str(event_uuid)),
        image_type=image_type,
        defaults={
            'session_uuid': uuid.UUID(str(session_uuid)) if session_uuid else None,
            'object_key': object_key,
            'content_hash': content_hash,
            'size_bytes': len(raw),
            'upload_status': 'uploaded',
            'captured_at': timezone.now(),
        },
    )
    cursor, _ = SiteSyncCursor.objects.get_or_create(site=site)
    if created:
        cursor.images_received += 1
        cursor.save(update_fields=['images_received', 'updated_at'])
    site.last_ingest_at = timezone.now()
    site.save(update_fields=['last_ingest_at'])
    return JsonResponse(
        {'success': True, 'created': created, 'object_key': object_key, 'id': media.id},
        status=201 if created else 200,
    )


@csrf_exempt
@require_POST
@require_site_token
def reconcile(request):
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    site = get_or_create_site(body.get('site_id') or request.site_id)
    since = _parse_dt(body.get('since'))
    event_uuids = set(str(u) for u in (body.get('event_uuids') or []))
    session_uuids = set(str(u) for u in (body.get('session_uuids') or []))

    ge_qs = ReplicaGateEvent.objects.filter(site=site)
    se_qs = ReplicaParkingSession.objects.filter(site=site)
    if since:
        ge_qs = ge_qs.filter(occurred_at__gte=since)
        se_qs = se_qs.filter(entry_time__gte=since)

    cloud_events = set(str(u) for u in ge_qs.values_list('event_uuid', flat=True))
    cloud_sessions = set(str(u) for u in se_qs.values_list('session_uuid', flat=True))

    missing_events = sorted(event_uuids - cloud_events) if event_uuids else []
    missing_sessions = sorted(session_uuids - cloud_sessions) if session_uuids else []
    # If client sent counts only, report cloud counts
    cursor, _ = SiteSyncCursor.objects.get_or_create(site=site)
    cursor.last_reconcile_at = timezone.now()
    cursor.save(update_fields=['last_reconcile_at', 'updated_at'])

    return JsonResponse(
        {
            'success': True,
            'cloud_event_count': ge_qs.count(),
            'cloud_session_count': se_qs.count(),
            'missing_event_uuids': missing_events,
            'missing_session_uuids': missing_sessions,
            'counts_by_type': body.get('counts_by_type') or {},
        }
    )

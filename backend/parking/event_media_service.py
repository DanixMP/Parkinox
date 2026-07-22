"""
Register local EventMedia rows after success-capture finalize (non-blocking side path).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import EventMedia, GateEvent
from .sync_outbox import enqueue_event_media

logger = logging.getLogger(__name__)

IMAGE_FILES = {
    'scene_a': 'scene_a.jpg',
    'scene_b': 'scene_b.jpg',
    'crop': 'crop.jpg',
    'thumbnail': 'thumbnail.jpg',
}


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def register_media_from_finalize(
    *,
    event_uuid: uuid.UUID,
    session_uuid: Optional[uuid.UUID] = None,
    gate_event_id: Optional[int] = None,
    media_dir: str,
    captured_at: Optional[str] = None,
    files_present: Optional[Dict[str, bool]] = None,
) -> List[EventMedia]:
    """
    Create/update EventMedia rows for files under media_dir.
    Safe to call multiple times (upsert by event_uuid + image_type).
    """
    root = Path(media_dir)
    if not root.is_dir():
        logger.warning('Success media dir missing: %s', media_dir)
        return []

    ts = None
    if captured_at:
        ts = parse_datetime(captured_at)
        if ts is not None and timezone.is_naive(ts):
            ts = timezone.make_aware(ts, timezone.utc)
    if ts is None:
        ts = timezone.now()

    gate_event = None
    if gate_event_id:
        gate_event = GateEvent.objects.filter(pk=gate_event_id).first()

    created: List[EventMedia] = []
    for image_type, filename in IMAGE_FILES.items():
        path = root / filename
        if files_present is not None and not files_present.get(image_type):
            continue
        if not path.is_file():
            continue
        try:
            content_hash = _file_hash(path)
            size_bytes = path.stat().st_size
        except OSError:
            logger.exception('Failed reading media file %s', path)
            continue

        with transaction.atomic():
            obj, _ = EventMedia.objects.update_or_create(
                event_uuid=event_uuid,
                image_type=image_type,
                defaults={
                    'session_uuid': session_uuid,
                    'gate_event': gate_event,
                    'local_path': str(path),
                    'content_hash': content_hash,
                    'size_bytes': size_bytes,
                    'upload_status': 'pending',
                    'captured_at': ts,
                },
            )
        created.append(obj)
        try:
            enqueue_event_media(obj)
        except Exception:
            logger.exception('Outbox enqueue failed for EventMedia %s', obj.id)
    return created


def register_media_from_meta(meta: Dict[str, Any], *, gate_event_id: Optional[int] = None) -> List[EventMedia]:
    event_uuid = uuid.UUID(str(meta['event_uuid']))
    session_uuid = None
    if meta.get('session_uuid'):
        session_uuid = uuid.UUID(str(meta['session_uuid']))
    ge_id = gate_event_id if gate_event_id is not None else meta.get('gate_event_id')
    return register_media_from_finalize(
        event_uuid=event_uuid,
        session_uuid=session_uuid,
        gate_event_id=ge_id,
        media_dir=meta.get('media_dir') or meta.get('dir') or '',
        captured_at=meta.get('captured_at') or meta.get('timestamp'),
        files_present=meta.get('files'),
    )


def default_parking_media_root() -> Path:
    """Core/parking_media next to the repo backend/ tree."""
    return Path(__file__).resolve().parents[2] / 'Core' / 'parking_media'


def recover_media_from_disk(media_root: Optional[Path] = None) -> Dict[str, int]:
    """
    Scan parking_media/*/meta.json and register orphan EventMedia rows.

    Only metas with buffer_miss=false and at least one real file are considered.
    Existing EventMedia for an event_uuid are left in place (register is upsert).
    """
    root = Path(media_root) if media_root else default_parking_media_root()
    stats = {'scanned': 0, 'registered_events': 0, 'registered_rows': 0, 'skipped': 0}
    if not root.is_dir():
        logger.warning('parking_media root missing: %s', root)
        return stats

    for meta_path in sorted(root.glob('*/*/meta.json')):
        stats['scanned'] += 1
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('Invalid meta.json at %s', meta_path, exc_info=True)
            stats['skipped'] += 1
            continue

        if meta.get('buffer_miss'):
            stats['skipped'] += 1
            continue

        files = meta.get('files') or {}
        media_dir = Path(meta.get('media_dir') or meta_path.parent)
        if not media_dir.is_dir():
            media_dir = meta_path.parent
            meta['media_dir'] = str(media_dir)

        has_files = False
        for image_type, filename in IMAGE_FILES.items():
            if files and not files.get(image_type):
                continue
            if (media_dir / filename).is_file():
                has_files = True
                break
        if not has_files:
            stats['skipped'] += 1
            continue

        try:
            event_uuid = uuid.UUID(str(meta['event_uuid']))
        except (KeyError, ValueError, TypeError):
            stats['skipped'] += 1
            continue

        already = EventMedia.objects.filter(event_uuid=event_uuid).exists()
        try:
            created = register_media_from_meta(meta)
        except Exception:
            logger.exception('recover register failed for %s', meta_path)
            stats['skipped'] += 1
            continue

        if created and not already:
            stats['registered_events'] += 1
        stats['registered_rows'] += len(created)

    return stats


def force_requeue_event_media(*, only_pending: bool = False) -> int:
    """
    Re-enqueue EventMedia rows for cloud upload.

    By default requeues all rows with a readable local file (including
    previously uploaded ones) so cloud can be repaired after hash cleanup.
    """
    qs = EventMedia.objects.all()
    if only_pending:
        qs = qs.filter(upload_status__in=('pending', 'failed'))
    count = 0
    for media in qs.iterator(chunk_size=200):
        path = Path(media.local_path or '')
        if not path.is_file():
            continue
        try:
            EventMedia.objects.filter(pk=media.pk).update(upload_status='pending')
            media.upload_status = 'pending'
            enqueue_event_media(media)
            count += 1
        except Exception:
            logger.exception('Force requeue failed for EventMedia %s', media.id)
    return count

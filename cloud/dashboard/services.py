"""Dashboard query helpers against replica models."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from replica.models import (
    ReplicaDetectionFail,
    ReplicaEventMedia,
    ReplicaGateEvent,
    ReplicaParkingSession,
    Site,
)


def get_site(site_id: str | None = None) -> Site | None:
    sid = site_id or settings.DEFAULT_SITE_ID
    site = Site.objects.filter(site_id=sid).first()
    if site:
        return site
    return Site.objects.order_by('created_at').first()


def tehran_today_range():
    now = timezone.localtime(timezone.now())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def overview_stats(site: Site) -> dict:
    start, end = tehran_today_range()
    sessions = ReplicaParkingSession.objects.filter(site=site)
    parked = sessions.filter(status='parked').count()
    capacity = site.capacity or settings.PARKING_CAPACITY
    today_entries = sessions.filter(entry_time__gte=start, entry_time__lt=end).count()
    today_exits = sessions.filter(exit_time__gte=start, exit_time__lt=end).count()
    revenue = (
        sessions.filter(entry_time__gte=start, entry_time__lt=end, status__in=('completed', 'waived'))
        .aggregate(s=Sum('fee_charged'))['s']
        or 0
    )
    avg_dur = (
        sessions.filter(entry_time__gte=start, entry_time__lt=end, duration_minutes__isnull=False)
        .aggregate(a=Avg('duration_minutes'))['a']
    )
    pending_images = ReplicaEventMedia.objects.filter(
        site=site
    ).exclude(upload_status='uploaded').count()
    pending_fails = ReplicaDetectionFail.objects.filter(
        site=site, review_status='pending'
    ).count()
    # Images may all be uploaded; count sessions missing thumbnail as pending UX signal
    return {
        'parked': parked,
        'capacity': capacity,
        'available': max(0, capacity - parked),
        'today_entries': today_entries,
        'today_exits': today_exits,
        'today_revenue': int(revenue),
        'avg_duration': round(float(avg_dur), 1) if avg_dur is not None else None,
        'last_sync_at': site.last_ingest_at,
        'pending_images': pending_images,
        'pending_fails': pending_fails,
        'gate_events_today': ReplicaGateEvent.objects.filter(
            site=site, occurred_at__gte=start, occurred_at__lt=end
        ).count(),
        'fails_today': ReplicaDetectionFail.objects.filter(
            site=site, created_at__gte=start, created_at__lt=end
        ).count(),
        'corrections_today': ReplicaGateEvent.objects.filter(
            site=site, occurred_at__gte=start, occurred_at__lt=end, was_edited=True
        ).count(),
    }


def filter_sessions(site: Site, params) -> list:
    if site is None:
        return ReplicaParkingSession.objects.none()
    qs = ReplicaParkingSession.objects.filter(site=site).order_by('-entry_time')
    plate = (params.get('plate') or '').strip()
    if plate:
        qs = qs.filter(plate_number__icontains=plate)
    status = params.get('status')
    if status:
        qs = qs.filter(status=status)
    payment = params.get('payment')
    if payment:
        qs = qs.filter(payment_method=payment)
    gate = params.get('gate')
    if gate:
        qs = qs.filter(Q(entry_camera_id__icontains=gate) | Q(exit_camera_id__icontains=gate))
    from .jalali import parse_jalali_date

    date_from = params.get('from')
    date_to = params.get('to')
    focus = (params.get('focus') or '').strip().lower()
    # Prefer Jalali fields; fall back to Gregorian ISO if still used
    start_f, _ = parse_jalali_date(date_from or '')
    _, end_t = parse_jalali_date(date_to or '')
    time_field = 'exit_time' if focus == 'exits' else 'entry_time'
    if focus == 'exits':
        qs = qs.filter(exit_time__isnull=False)
    if start_f:
        qs = qs.filter(**{f'{time_field}__gte': start_f})
    elif date_from and '-' in str(date_from) and '/' not in str(date_from):
        qs = qs.filter(**{f'{time_field}__date__gte': date_from})
    if end_t:
        qs = qs.filter(**{f'{time_field}__lt': end_t})
    elif date_to and '-' in str(date_to) and '/' not in str(date_to):
        qs = qs.filter(**{f'{time_field}__date__lte': date_to})
    if focus == 'exits':
        qs = qs.order_by('-exit_time')
    min_dur = params.get('min_duration')
    max_dur = params.get('max_duration')
    if min_dur:
        qs = qs.filter(duration_minutes__gte=int(min_dur))
    if max_dur:
        qs = qs.filter(duration_minutes__lte=int(max_dur))
    return qs


def media_map_for_events(site: Site, event_uuids) -> dict:
    rows = ReplicaEventMedia.objects.filter(site=site, event_uuid__in=event_uuids)
    out = {}
    for m in rows:
        out.setdefault(str(m.event_uuid), {})[m.image_type] = m
    return out


def analytics_payload(site: Site, days: int = 7) -> dict:
    end = timezone.localtime(timezone.now())
    start = end - timedelta(days=days)
    sessions = ReplicaParkingSession.objects.filter(site=site, entry_time__gte=start)
    events = ReplicaGateEvent.objects.filter(site=site, occurred_at__gte=start)

    by_hour_entry = [0] * 24
    by_hour_exit = [0] * 24
    for e in events.only('direction', 'occurred_at'):
        if not e.occurred_at:
            continue
        h = timezone.localtime(e.occurred_at).hour
        if e.direction == 'entry':
            by_hour_entry[h] += 1
        elif e.direction == 'exit':
            by_hour_exit[h] += 1

    from .jalali import to_jalali_str

    daily = {}
    for s in sessions.only('entry_time', 'exit_time', 'fee_charged', 'status', 'duration_minutes', 'payment_method'):
        if not s.entry_time:
            continue
        d = to_jalali_str(timezone.localtime(s.entry_time))
        bucket = daily.setdefault(d, {'entries': 0, 'exits': 0, 'revenue': 0})
        bucket['entries'] += 1
        if s.exit_time:
            bucket['exits'] += 1
        if s.status in ('completed', 'waived'):
            bucket['revenue'] += int(s.fee_charged or 0)

    payment_mix = (
        sessions.exclude(payment_method='')
        .values('payment_method')
        .annotate(c=Count('id'), revenue=Sum('fee_charged'))
    )
    durations = list(
        sessions.filter(duration_minutes__isnull=False).values_list('duration_minutes', flat=True)[:2000]
    )
    gate_counts = (
        events.values('camera_id').annotate(c=Count('id')).order_by('-c')
    )
    fails_qs = ReplicaDetectionFail.objects.filter(site=site, created_at__gte=start)
    fails_by_day = {}
    for f in fails_qs.only('created_at'):
        if not f.created_at:
            continue
        d = to_jalali_str(timezone.localtime(f.created_at))
        fails_by_day[d] = fails_by_day.get(d, 0) + 1
    fails = [{'day': k, 'c': v} for k, v in sorted(fails_by_day.items())]
    corrections = events.filter(was_edited=True).count()
    long_stay = sessions.filter(status='parked', entry_time__lte=end - timedelta(hours=8)).count()
    plates = list(sessions.values_list('plate_number', flat=True))
    from collections import Counter

    repeats = Counter(p for p in plates if p).most_common(10)
    fees = [int(x) for x in sessions.filter(status='completed').values_list('fee_charged', flat=True) if x]
    avg_fee = round(sum(fees) / len(fees), 0) if fees else 0

    # occupancy samples: parked count approximation by day end
    occupancy = []
    for i in range(days):
        day = (start + timedelta(days=i)).date()
        # rough: entries that day still open or exited later
        count = sessions.filter(entry_time__date__lte=day).filter(
            Q(exit_time__isnull=True) | Q(exit_time__date__gte=day)
        ).count()
        occupancy.append({'date': to_jalali_str(day), 'parked': count})

    heatmap = [[0 for _ in range(24)] for _ in range(7)]
    for e in events.only('occurred_at', 'direction'):
        if not e.occurred_at or e.direction != 'entry':
            continue
        local = timezone.localtime(e.occurred_at)
        heatmap[local.weekday()][local.hour] += 1

    return {
        'hours': list(range(24)),
        'entries_by_hour': by_hour_entry,
        'exits_by_hour': by_hour_exit,
        'daily_labels': sorted(daily.keys()),
        'daily_entries': [daily[d]['entries'] for d in sorted(daily.keys())],
        'daily_exits': [daily[d]['exits'] for d in sorted(daily.keys())],
        'daily_revenue': [daily[d]['revenue'] for d in sorted(daily.keys())],
        'payment_mix': list(payment_mix),
        'durations': durations,
        'gate_counts': list(gate_counts),
        'fails_by_day': list(fails),
        'corrections': corrections,
        'long_stay': long_stay,
        'repeats': repeats,
        'avg_fee': avg_fee,
        'occupancy': occupancy,
        'heatmap': heatmap,
        'capacity': site.capacity or settings.PARKING_CAPACITY,
        'parked_now': sessions.filter(status='parked').count(),
    }

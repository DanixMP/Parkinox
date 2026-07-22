"""Cloud management dashboard views (HTML, RTL)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from replica.models import (
    ReplicaDetectionFail,
    ReplicaEventMedia,
    ReplicaGateEvent,
    ReplicaParkingSession,
    Site,
)
from .auth import (
    dashboard_login_required,
    is_dashboard_authenticated,
    login_dashboard,
    logout_dashboard,
)
from . import reports as report_mod
from .jalali import to_jalali_str
from .local_site import local_season_configured, reset_local_season
from .season_service import apply_replica_season_reset
from .services import (
    analytics_payload,
    filter_sessions,
    get_site,
    media_map_for_events,
    overview_stats,
)


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if is_dashboard_authenticated(request):
        return redirect('/')
    error = ''
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        if login_dashboard(request, username, password):
            return redirect(request.GET.get('next') or '/')
        error = 'نام کاربری یا رمز عبور نادرست است'
    return render(request, 'dashboard/login.html', {'error': error})


@require_http_methods(['POST', 'GET'])
def logout_view(request):
    logout_dashboard(request)
    return redirect('/login/')


@dashboard_login_required
def overview(request):
    from datetime import date

    site = get_site(request.GET.get('site'))
    if not site:
        return render(
            request,
            'dashboard/overview.html',
            {
                'no_site': True,
                'stats': {},
                'today_jalali': to_jalali_str(date.today()),
                'local_proxy_configured': local_season_configured(),
            },
        )
    stats = overview_stats(site)
    return render(
        request,
        'dashboard/overview.html',
        {
            'site': site,
            'stats': stats,
            'sites': Site.objects.all(),
            'today_jalali': to_jalali_str(date.today()),
            'local_proxy_configured': local_season_configured(),
        },
    )


def _attach_thumbs(sessions, media):
    for s in sessions:
        imgs = media.get(str(s.entry_event_uuid), {}) if s.entry_event_uuid else {}
        thumb = imgs.get('thumbnail') or imgs.get('scene_a') or imgs.get('crop')
        s.thumb_media_id = thumb.id if thumb else None
        exit_imgs = media.get(str(s.exit_event_uuid), {}) if s.exit_event_uuid else {}
        exit_thumb = exit_imgs.get('thumbnail') or exit_imgs.get('scene_a')
        s.exit_thumb_media_id = exit_thumb.id if exit_thumb else None
    return sessions


@dashboard_login_required
def parked(request):
    site = get_site(request.GET.get('site'))
    if not site:
        return render(request, 'dashboard/parked.html', {'site': None, 'sessions': [], 'sites': Site.objects.all()})
    qs = list(ReplicaParkingSession.objects.filter(site=site, status='parked').order_by('entry_time'))
    entry_uuids = [s.entry_event_uuid for s in qs if s.entry_event_uuid]
    media = media_map_for_events(site, entry_uuids)
    _attach_thumbs(qs, media)
    return render(
        request,
        'dashboard/parked.html',
        {'site': site, 'sessions': qs, 'sites': Site.objects.all()},
    )


@dashboard_login_required
def history(request):
    site = get_site(request.GET.get('site'))
    qs = list(filter_sessions(site, request.GET)[:500])
    entry_uuids = [s.entry_event_uuid for s in qs if s.entry_event_uuid]
    exit_uuids = [s.exit_event_uuid for s in qs if s.exit_event_uuid]
    media = media_map_for_events(site, entry_uuids + exit_uuids) if site else {}
    _attach_thumbs(qs, media)
    return render(
        request,
        'dashboard/history.html',
        {
            'site': site,
            'sessions': qs,
            'params': request.GET,
            'sites': Site.objects.all(),
        },
    )


@dashboard_login_required
def session_detail(request, session_uuid):
    site = get_site(request.GET.get('site'))
    session = get_object_or_404(ReplicaParkingSession, site=site, session_uuid=session_uuid)
    events = ReplicaGateEvent.objects.filter(site=site, session_uuid=session.session_uuid).order_by(
        'occurred_at'
    )
    uuids = []
    if session.entry_event_uuid:
        uuids.append(session.entry_event_uuid)
    if session.exit_event_uuid:
        uuids.append(session.exit_event_uuid)
    media = media_map_for_events(site, uuids)
    return render(
        request,
        'dashboard/session_detail.html',
        {'site': site, 'session': session, 'events': events, 'media': media},
    )


@dashboard_login_required
def search(request):
    site = get_site(request.GET.get('site'))
    plate = (request.GET.get('plate') or '').strip()
    sessions = []
    events = []
    if plate:
        sessions = list(
            ReplicaParkingSession.objects.filter(site=site, plate_number__icontains=plate).order_by(
                '-entry_time'
            )[:100]
        )
        events = list(
            ReplicaGateEvent.objects.filter(site=site, plate_confirmed__icontains=plate).order_by(
                '-occurred_at'
            )[:100]
        )
    return render(
        request,
        'dashboard/search.html',
        {'site': site, 'plate': plate, 'sessions': sessions, 'events': events},
    )


@dashboard_login_required
def fails(request):
    site = get_site(request.GET.get('site'))
    status = request.GET.get('status') or 'pending'
    qs = ReplicaDetectionFail.objects.filter(site=site).order_by('-created_at')
    if status != 'all':
        qs = qs.filter(review_status=status)
    qs = list(qs[:200])
    fail_uuids = [f.fail_uuid for f in qs]
    media = media_map_for_events(site, fail_uuids) if site else {}
    for f in qs:
        imgs = media.get(str(f.fail_uuid), {})
        thumb = imgs.get('fail_full') or imgs.get('fail_crop') or imgs.get('thumbnail')
        f.thumb_media_id = thumb.id if thumb else None
    return render(
        request,
        'dashboard/fails.html',
        {
            'site': site,
            'fails': qs,
            'status': status,
            'sites': Site.objects.all(),
            'pending_count': ReplicaDetectionFail.objects.filter(
                site=site, review_status='pending'
            ).count()
            if site
            else 0,
        },
    )


@dashboard_login_required
def sync_health(request):
    site = get_site(request.GET.get('site'))
    cursor = getattr(site, 'sync_cursor', None) if site else None
    pending_media = (
        ReplicaEventMedia.objects.filter(site=site).exclude(upload_status='uploaded')[:100]
        if site
        else []
    )
    gate_total = ReplicaGateEvent.objects.filter(site=site).count() if site else 0
    session_total = ReplicaParkingSession.objects.filter(site=site).count() if site else 0
    fail_total = ReplicaDetectionFail.objects.filter(site=site).count() if site else 0
    return render(
        request,
        'dashboard/sync.html',
        {
            'site': site,
            'cursor': cursor,
            'pending_media': pending_media,
            'sites': Site.objects.all(),
            'gate_total': gate_total,
            'session_total': session_total,
            'fail_total': fail_total,
            'local_proxy_configured': local_season_configured(),
        },
    )


@dashboard_login_required
@require_http_methods(['POST'])
def season_reset(request):
    """Apply cloud replica season reset; optionally proxy to local SoR."""
    password = (request.POST.get('password') or '').strip()
    next_url = request.POST.get('next') or '/'
    if not password or not login_dashboard(
        request, settings.DASHBOARD_USERNAME, password
    ):
        messages.error(request, 'رمز عبور داشبورد نادرست است')
        return redirect(next_url)

    site = get_site(request.POST.get('site') or request.GET.get('site'))
    if not site:
        messages.error(request, 'سایتی برای بازنشانی یافت نشد')
        return redirect(next_url)

    result = apply_replica_season_reset(site)
    closed = result.get('closed_sessions', 0)
    deleted_fails = result.get('deleted_detection_fails', 0)
    msg = (
        f'فصل عملیاتی روی ابر بازنشانی شد · جلسات بسته‌شده: {closed} · '
        f'حذف تشخیص‌های در انتظار: {deleted_fails}'
    )

    if local_season_configured():
        ok, local_msg, payload = reset_local_season()
        if ok:
            local_closed = (payload or {}).get('closed_sessions', '—')
            messages.success(
                request,
                f'{msg} · سایت محلی: {local_msg} (جلسات: {local_closed})',
            )
        else:
            messages.warning(
                request,
                f'{msg} · پروکسی محلی ناموفق: {local_msg}',
            )
    else:
        messages.success(request, msg)

    return redirect(next_url)

@dashboard_login_required
@require_http_methods(['POST'])
def requeue_media(request):
    """Mark missing/failed media as pending (extension point for site re-push)."""
    site = get_site(request.POST.get('site'))
    media_id = request.POST.get('media_id')
    if site and media_id:
        ReplicaEventMedia.objects.filter(site=site, id=media_id).update(upload_status='pending')
    return redirect(f"/sync/?site={site.site_id if site else ''}")


@dashboard_login_required
def reports_page(request):
    site = get_site(request.GET.get('site'))
    return render(
        request,
        'dashboard/reports.html',
        {'site': site, 'sites': Site.objects.all(), 'params': request.GET},
    )


@dashboard_login_required
@require_GET
def export_excel(request):
    site = get_site(request.GET.get('site'))
    report_type = request.GET.get('type', 'sessions')
    content = report_mod.build_excel(site, report_type, request.GET)
    resp = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="parkinox_{report_type}.xlsx"'
    return resp


@dashboard_login_required
@require_GET
def export_pdf(request):
    site = get_site(request.GET.get('site'))
    report_type = request.GET.get('type', 'summary')
    content = report_mod.build_pdf(site, report_type, request.GET)
    resp = HttpResponse(content, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="parkinox_{report_type}.pdf"'
    return resp


@dashboard_login_required
@require_GET
def export_csv(request):
    site = get_site(request.GET.get('site'))
    content = report_mod.build_csv_sessions(site, request.GET)
    resp = HttpResponse(content, content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="parkinox_sessions.csv"'
    return resp


@dashboard_login_required
def analytics(request):
    site = get_site(request.GET.get('site'))
    days = int(request.GET.get('days') or 7)
    data = analytics_payload(site, days=days) if site else {}
    return render(
        request,
        'dashboard/analytics.html',
        {'site': site, 'data': data, 'days': days, 'sites': Site.objects.all()},
    )


@dashboard_login_required
@require_GET
def media_file(request, media_id: int):
    media = get_object_or_404(ReplicaEventMedia, pk=media_id)
    path = Path(settings.MEDIA_ROOT) / media.object_key
    if not path.is_file():
        raise Http404('Image not found')
    return FileResponse(path.open('rb'), content_type='image/jpeg')


@dashboard_login_required
@require_GET
def session_images_zip(request, session_uuid):
    site = get_site(request.GET.get('site'))
    session = get_object_or_404(ReplicaParkingSession, site=site, session_uuid=session_uuid)
    uuids = [u for u in (session.entry_event_uuid, session.exit_event_uuid) if u]
    media_rows = ReplicaEventMedia.objects.filter(site=site, event_uuid__in=uuids)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for m in media_rows:
            path = Path(settings.MEDIA_ROOT) / m.object_key
            if path.is_file():
                zf.write(path, arcname=f'{m.event_uuid}_{m.image_type}.jpg')
    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="session_{session_uuid}_images.zip"'
    return resp

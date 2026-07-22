from .auth import is_dashboard_authenticated


def pilot_auth(request):
    return {
        'dashboard_user': request.session.get('cloud_dashboard_auth'),
        'is_dashboard_auth': is_dashboard_authenticated(request),
    }

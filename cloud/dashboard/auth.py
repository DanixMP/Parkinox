"""Pilot dashboard session auth (env username/password)."""

from functools import wraps

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect


SESSION_KEY = 'cloud_dashboard_auth'


def is_dashboard_authenticated(request) -> bool:
    return bool(request.session.get(SESSION_KEY))


def login_dashboard(request, username: str, password: str) -> bool:
    expected_user = settings.DASHBOARD_USERNAME
    expected_pass = settings.DASHBOARD_PASSWORD
    if username != expected_user:
        return False
    # Support either plain env password or hashed value starting with algorithm marker
    if expected_pass.startswith('pbkdf2_') or expected_pass.startswith('argon2'):
        ok = check_password(password, expected_pass)
    else:
        ok = password == expected_pass
    if ok:
        request.session[SESSION_KEY] = username
        request.session.cycle_key()
        return True
    return False


def logout_dashboard(request) -> None:
    request.session.pop(SESSION_KEY, None)


def dashboard_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_dashboard_authenticated(request):
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        return view_func(request, *args, **kwargs)

    return wrapper


def hash_password_for_env(plain: str) -> str:
    """Helper for ops docs — not used at runtime unless env stores hash."""
    return make_password(plain)

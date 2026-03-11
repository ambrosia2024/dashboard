# lumenix/security.py

import hashlib
import random

from django.core.cache import cache
from django.conf import settings
import requests


def get_client_ip(request) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "unknown").strip()


def _safe_identifier(identifier: str) -> str:
    if not identifier:
        return "unknown"
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


def _cache_incr(key: str, timeout: int) -> int:
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def _key(prefix: str, value: str, scope: str = "login") -> str:
    return f"auth:{scope}:{prefix}:{value}"


def is_locked(request, identifier: str = "", scope: str = "login") -> bool:
    ip = get_client_ip(request)
    ident = _safe_identifier(identifier)
    return bool(cache.get(_key("ip_lock", ip, scope)) or cache.get(_key("ident_lock", ident, scope)))


def register_attempt(request, window_seconds: int = 60, scope: str = "login") -> int:
    ip = get_client_ip(request)
    return _cache_incr(_key("burst", ip, scope), timeout=window_seconds)


def record_failure(
    request,
    identifier: str = "",
    scope: str = "login",
    failure_window_seconds: int = 15 * 60,
    lock_seconds: int = 15 * 60,
    max_ip_failures: int = 15,
    max_identifier_failures: int = 8,
) -> None:
    ip = get_client_ip(request)
    ident = _safe_identifier(identifier)

    ip_fails = _cache_incr(_key("fail_ip", ip, scope), timeout=failure_window_seconds)
    ident_fails = _cache_incr(_key("fail_ident", ident, scope), timeout=failure_window_seconds)

    if ip_fails >= max_ip_failures:
        cache.set(_key("ip_lock", ip, scope), 1, timeout=lock_seconds)
    if identifier and ident_fails >= max_identifier_failures:
        cache.set(_key("ident_lock", ident, scope), 1, timeout=lock_seconds)


def record_success(request, identifier: str = "", scope: str = "login") -> None:
    ip = get_client_ip(request)
    ident = _safe_identifier(identifier)

    cache.delete(_key("burst", ip, scope))
    cache.delete(_key("fail_ip", ip, scope))
    cache.delete(_key("ip_lock", ip, scope))
    if identifier:
        cache.delete(_key("fail_ident", ident, scope))
        cache.delete(_key("ident_lock", ident, scope))


def should_require_challenge(request, identifier: str = "", scope: str = "login") -> bool:
    ip = get_client_ip(request)
    ident = _safe_identifier(identifier)

    ip_fails = int(cache.get(_key("fail_ip", ip, scope)) or 0)
    ident_fails = int(cache.get(_key("fail_ident", ident, scope)) or 0)
    burst = int(cache.get(_key("burst", ip, scope)) or 0)

    return ip_fails >= 3 or ident_fails >= 2 or burst >= 10


def get_or_create_challenge(request, *, rotate: bool = False) -> tuple[str, int]:
    session_key = "login_challenge"
    payload = request.session.get(session_key)

    if rotate or not payload:
        a = random.randint(2, 12)
        b = random.randint(2, 12)
        payload = {"question": f"{a} + {b}", "answer": a + b}
        request.session[session_key] = payload

    return payload["question"], int(payload["answer"])


def validate_challenge(request, submitted_answer: str) -> bool:
    payload = request.session.get("login_challenge")
    if not payload:
        return False
    try:
        return int(str(submitted_answer).strip()) == int(payload["answer"])
    except (TypeError, ValueError):
        return False


def verify_recaptcha(token: str, remote_ip: str = "") -> bool:
    """
    Verify Google reCAPTCHA token.
    Disabled unless RECAPTCHA_ENABLED=true and keys are configured.
    """
    if not getattr(settings, "RECAPTCHA_ENABLED", False):
        return True

    secret = (getattr(settings, "RECAPTCHA_SECRET_KEY", "") or "").strip()
    if not secret or not token:
        return False

    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data=payload,
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        return bool(data.get("success"))
    except Exception:
        return False

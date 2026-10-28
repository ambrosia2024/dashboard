"""
Workshop evaluation event log (T5.2 Phase 2).

One helper, used from the views. Everything it touches is best-effort: a
failure here must never be able to break a page while a workshop is running,
so the whole body is guarded and only logged.
"""

import logging

from lumenix.models import UserEvent

logger = logging.getLogger(__name__)


def log_event(request, event, **payload):
    """
    Record one user action. Safe to call from any view.

    payload holds only what the event needs - concept ids, a NUTS2 code, the
    names of the form fields that failed. Never free text the participant
    typed, and never coordinates finer than the resolved region.
    """
    try:
        user = getattr(request, "user", None)
        if user is not None and not user.is_authenticated:
            user = None

        session = getattr(request, "session", None)
        session_key = getattr(session, "session_key", "") or "" if session is not None else ""

        UserEvent.objects.create(
            user=user,
            session_key=session_key[:40],
            cohort=cohort_for(user),
            event=event,
            url_name=getattr(getattr(request, "resolver_match", None), "url_name", "") or "",
            payload=payload,
        )
    except Exception:  # noqa: BLE001 - evaluation logging is never worth an error page
        logger.warning("Could not record user event %s", event, exc_info=True)


def cohort_for(user):
    """The evaluation group on the user's profile, or an empty string."""
    if user is None:
        return ""
    return (getattr(getattr(user, "profile", None), "cohort", "") or "")[:40]

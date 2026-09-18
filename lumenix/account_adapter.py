# lumenix/account_adapter.py

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """Allow or block public signup via settings flag; tag outgoing mail for Postmark."""

    def is_open_for_signup(self, request):
        return bool(getattr(settings, "PUBLIC_SIGNUP_ENABLED", False))

    def render_mail(self, template_prefix, email, context, headers=None):
        headers = dict(headers or {})
        stream = getattr(settings, "POSTMARK_MESSAGE_STREAM", "")
        if stream:
            headers.setdefault("X-PM-Message-Stream", stream)
        msg = super().render_mail(template_prefix, email, context, headers=headers)
        reply_to = getattr(settings, "EMAIL_REPLY_TO", "")
        if reply_to and not msg.reply_to:
            msg.reply_to = [reply_to]
        return msg

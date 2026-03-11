# lumenix/forms.py

from allauth.account.forms import LoginForm
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model

from lumenix.security import (
    get_client_ip,
    get_or_create_challenge,
    is_locked,
    record_failure,
    record_success,
    register_attempt,
    should_require_challenge,
    validate_challenge,
    verify_recaptcha,
)

User = get_user_model()


class ProfileCompletionForm(forms.ModelForm):
    """
    Simple form for forcing users to fill in first and last name.
    """
    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
        }


class SecureLoginForm(LoginForm):
    """
    Hardened allauth login form:
    - Honeypot trap for basic bots.
    - Adaptive challenge after suspicious/failed attempts.
    - Cache-backed lockouts for brute-force bursts.
    """

    honey_field = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "aria-hidden": "true",
                "style": "position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;",
            }
        ),
        label="Leave this field empty",
    )

    challenge_answer = forms.CharField(
        required=False,
        label="Security check",
        widget=forms.TextInput(attrs={"autocomplete": "off", "inputmode": "numeric"}),
    )
    recaptcha_token = forms.CharField(required=False, widget=forms.HiddenInput())

    error_messages = {
        "blocked": "Too many sign-in attempts. Please wait and try again.",
        "challenge": "Security verification failed. Please try again.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        login_value = ""
        if hasattr(self, "data"):
            login_value = (self.data.get("login") or "").strip().lower()

        self.challenge_required = should_require_challenge(self.request, login_value)
        if self.challenge_required:
            question, _ = get_or_create_challenge(self.request)
            self.fields["challenge_answer"].required = True
            self.fields["challenge_answer"].label = f"Security check: {question} = ?"
        else:
            self.fields["challenge_answer"].widget = forms.HiddenInput()

        # Keep this hidden for humans, visible for simplistic bots.
        self.fields["honey_field"].help_text = ""

        recaptcha_site_key = (getattr(settings, "RECAPTCHA_SITE_KEY", "") or "").strip()
        self.recaptcha_enabled = bool(getattr(settings, "RECAPTCHA_ENABLED", False) and recaptcha_site_key)
        self.fields["recaptcha_token"].widget.attrs["data-site-key"] = recaptcha_site_key

    def clean(self):
        login_value = (self.data.get("login") or "").strip().lower()

        # Burst counter on each POST, even before credential validation.
        attempts = register_attempt(self.request)
        if attempts > getattr(settings, "LOGIN_BURST_LIMIT_PER_MINUTE", 20) or is_locked(self.request, login_value):
            raise forms.ValidationError(self.error_messages["blocked"])

        # Honeypot must remain empty.
        if (self.data.get("honey_field") or "").strip():
            record_failure(self.request, login_value)
            raise forms.ValidationError(self.error_messages["challenge"])

        try:
            cleaned_data = super().clean()
        except forms.ValidationError:
            record_failure(self.request, login_value)
            # Rotate challenge so replayed answers do not work.
            get_or_create_challenge(self.request, rotate=True)
            raise

        # Adaptive security check after suspicious behavior.
        if self.challenge_required:
            answer = self.data.get("challenge_answer")
            if not validate_challenge(self.request, answer):
                record_failure(self.request, login_value)
                get_or_create_challenge(self.request, rotate=True)
                raise forms.ValidationError(self.error_messages["challenge"])

        if self.recaptcha_enabled:
            token = (self.data.get("recaptcha_token") or "").strip()
            if not verify_recaptcha(token, get_client_ip(self.request)):
                record_failure(self.request, login_value)
                raise forms.ValidationError("CAPTCHA verification failed. Please try again.")

        record_success(self.request, cleaned_data.get("login") or login_value)
        self.request.session.pop("login_challenge", None)
        return cleaned_data

# from allauth.account.forms import SignupForm, LoginForm
#
# from .models import RoleMaster, UserProfile
#
#
# class CustomSignupForm(SignupForm):
#     """
#     Allauth signup form with an extra required Role dropdown.
#     Email + password1 + password2 remain mandatory from the base form.
#     """
#     role = forms.ModelChoiceField(
#         queryset=RoleMaster.objects.all(),
#         required=True,
#         empty_label=None,
#         label="Role",
#     )
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#         # Set default to "Farmer" if it exists
#         try:
#             default_role = RoleMaster.objects.get(name__iexact="Farmer")
#             self.fields["role"].initial = default_role.pk
#         except RoleMaster.DoesNotExist:
#             pass
#
#     def save(self, request):
#         # Save the user first (email + password)
#         user = super().save(request)
#
#         # Attach role in UserProfile
#         role = self.cleaned_data["role"]
#         UserProfile.objects.update_or_create(
#             user=user,
#             defaults={"role": role},
#         )
#         return user
#
# class CustomLoginForm(LoginForm):
#     """
#     Allauth login form with an extra required Role dropdown.
#     We still authenticate by email + password, but also verify
#     the selected role matches the user's stored role.
#     """
#     role = forms.ModelChoiceField(
#         queryset=RoleMaster.objects.none(),
#         required=True,
#         empty_label=None,
#         label="Role",
#     )
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#         role_field = self.fields["role"]
#         role_field.queryset = RoleMaster.objects.all()
#
#         try:
#             default_role = RoleMaster.objects.get(name__iexact="Farmer")
#             role_field.initial = default_role.pk
#         except RoleMaster.DoesNotExist:
#             pass
#
#     def clean(self):
#         # Let allauth do normal email+password auth first
#         cleaned_data = super().clean()
#
#         # user_cache is set by LoginForm.clean() if credentials are valid
#         user = getattr(self, "user_cache", None)
#         role = self.cleaned_data.get("role")
#
#         if user and role:
#             try:
#                 profile = user.profile
#             except UserProfile.DoesNotExist:
#                 raise forms.ValidationError(
#                     "No role is assigned to this account. Please contact support."
#                 )
#
#             if profile.role_id != role.id:
#                 raise forms.ValidationError(
#                     "The selected role does not match your account."
#                 )
#
#         return cleaned_data

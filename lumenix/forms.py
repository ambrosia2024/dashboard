# lumenix/forms.py

from django import forms
from django.contrib.auth import get_user_model

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

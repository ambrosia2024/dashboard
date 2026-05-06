from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticate against either username or email.
    Keeps Django's normal password and active-user checks intact.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get(get_user_model().USERNAME_FIELD)
        if not identifier or not password:
            return None

        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            )
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Email should be unique, but username/email collisions should not
            # make auth ambiguous. Prefer exact username match, then exact email.
            user = (
                UserModel._default_manager.filter(username__iexact=identifier).first()
                or UserModel._default_manager.filter(email__iexact=identifier).first()
            )

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


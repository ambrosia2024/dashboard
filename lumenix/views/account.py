# lumenix/views/account.py

from allauth.account.views import SignupView as AllauthSignupView


class SignupView(AllauthSignupView):
    """
    Allauth signup view that, while public registration is closed, still shows
    the registration form (read-only) together with a "closed" notice instead
    of a bare status page. ``CloseableSignupMixin.dispatch`` guarantees that no
    GET or POST reaches the real form handling while the adapter reports
    registration as closed.
    """

    def closed(self):
        form = self.get_form_class()()
        for field in form.fields.values():
            field.widget.attrs["disabled"] = True
            field.widget.attrs["aria-disabled"] = "true"

        context = {
            "form": form,
            "signup_closed": True,
            "login_url": self.get_login_url() if hasattr(self, "get_login_url") else "/accounts/login/",
        }
        return self.response_class(
            request=self.request,
            template=self.template_name_signup_closed,
            context=context,
        )

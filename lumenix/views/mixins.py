# lumenix/views/mixins.py

from lumenix.services.dashboard_modes import get_active_mode, is_mode_locked


class DashboardModeMixin:
    """Resolve the active dashboard view mode for a class-based view."""

    def get_active_mode(self):
        return get_active_mode(self.request)

    def is_mode_locked(self):
        return is_mode_locked(self.request)

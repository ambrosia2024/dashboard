# lumenix/admin.py

from django.contrib import admin, messages
from django.db.models import JSONField
from django_json_widget.widgets import JSONEditorWidget
# from django.utils.html import format_html
# from django.utils import timezone

from .models import (Vocabulary, Scheme, Concept, PlantConcept, PathogenConcept, ConceptHistory, DashboardChart,
                     DashboardViewChart, DashboardViewMode)


# Hidden from admin panel (temporarily)
# @admin.register(Vocabulary)
class VocabularyAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")

# Hidden from admin panel (temporarily)
# @admin.register(Scheme)
class SchemeAdmin(admin.ModelAdmin):
    list_display = ("uri", "vocabulary")
    search_fields = ("uri", "title__en")
    list_filter = ("vocabulary",)

# Hidden from admin panel (temporarily)
# @admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    list_display = ("uri", "vocabulary", "scheme", "updated_at")
    search_fields = ("uri", "pref_label__en")
    list_filter = ("vocabulary",)

# Proxies for convenience - Hidden from admin panel (temporarily)
# @admin.register(PlantConcept)
class PlantConceptAdmin(ConceptAdmin):
    pass

# @admin.register(PathogenConcept)
class PathogenConceptAdmin(ConceptAdmin):
    pass

# @admin.register(ConceptHistory)
class ConceptHistoryAdmin(admin.ModelAdmin):
    list_display = ("concept", "change_type", "changed_at")
    list_filter = ("change_type",)
    search_fields = ("concept__uri",)

# @admin.register(CropMaster)
# class CropMasterAdmin(admin.ModelAdmin):
#     """
#     Comprehensive admin for CropMaster:
#     - Nice list view with status badge and timestamps
#     - Search, filters, ordering, date_hierarchy
#     - Safe soft-delete workflow (no hard delete)
#     - Bulk actions: activate / deactivate / soft-delete / restore / export CSV
#     - Makes ontology_id immutable after first save (helps keep references stable)
#     """
#
#     # ----- List / Search / Filters -----
#     list_display = ("crop_name", "status_badge", "created_at", "updated_at")
#     list_display_links = ("crop_name",)
#     ordering = ("crop_name",)
#     search_fields = ("crop_name",)
#     list_filter = ("status", "created_at", "updated_at")
#     date_hierarchy = "created_at"
#     list_per_page = 50
#
#     # ----- Form layout -----
#     fieldsets = (
#         ("Crop", {"fields": ("crop_name",)}),
#         ("Lifecycle", {"fields": ("status", "deleted_at", "created_at", "updated_at")}),
#     )
#     # System fields are read-only; deleted_at is set via soft delete
#     readonly_fields = ("deleted_at", "created_at", "updated_at")
#
#     # ----- Pretty status badge -----
#     @admin.display(description="Status")
#     def status_badge(self, obj):
#         colours = {1: "#16a34a", 0: "#ef4444", 2: "#6b7280"}  # green / red / grey
#         labels = dict(obj.STATUS_CHOICES)
#         return format_html(
#             '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;">{}</span>',
#             colours.get(obj.status, "#6b7280"),
#             labels.get(obj.status, obj.status),
#         )
#
#     # ----- Bulk actions -----
#     actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
#
#     @admin.action(description="Mark selected as Active")
#     def mark_active(self, request, queryset):
#         updated = queryset.update(status=1, deleted_at=None)
#         self.message_user(request, f"{updated} crop(s) marked Active.", level=messages.SUCCESS)
#
#     @admin.action(description="Mark selected as Inactive")
#     def mark_inactive(self, request, queryset):
#         updated = queryset.update(status=0)
#         self.message_user(request, f"{updated} crop(s) marked Inactive.", level=messages.SUCCESS)
#
#     @admin.action(description="Soft delete selected")
#     def soft_delete_selected(self, request, queryset):
#         updated = queryset.update(status=2, deleted_at=timezone.now())
#         self.message_user(request, f"{updated} crop(s) soft-deleted.", level=messages.WARNING)
#
#     @admin.action(description="Restore selected (set Active)")
#     def restore_selected(self, request, queryset):
#         updated = queryset.update(status=1, deleted_at=None)
#         self.message_user(request, f"{updated} crop(s) restored.", level=messages.SUCCESS)
#
#     @admin.action(description="Export selected to CSV")
#     def export_as_csv(self, request, queryset):
#         """
#         Minimal CSV export (crop_name, status, created_at, updated_at).
#         Returns an HTTP response so the browser downloads the file immediately.
#         """
#         import csv
#         from django.http import HttpResponse
#
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = 'attachment; filename="crops_export.csv"'
#         writer = csv.writer(response)
#         writer.writerow(["crop_name", "status", "created_at", "updated_at"])
#         for obj in queryset:
#             writer.writerow([obj.crop_name, obj.status, obj.created_at, obj.updated_at])
#         return response
#
#     # Remove the default hard delete (dangerous) - nudges admins to use soft delete instead
#     def get_actions(self, request):
#         actions = super().get_actions(request)
#         if "delete_selected" in actions:
#             del actions["delete_selected"]
#         return actions
#
#     # Admin should use the default manager (objects)
#     def get_queryset(self, request):
#         qs = super().get_queryset(request)
#         return qs


# @admin.register(RoleMaster)
# class RoleMasterAdmin(admin.ModelAdmin):
#     list_display = ("name",)
#     search_fields = ("name",)
#
#
# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ("user", "role")
#     search_fields = ("user__username", "user__email", "role__name")
#     autocomplete_fields = ("user", "role")

@admin.register(DashboardViewMode)
class DashboardViewModeAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_default", "status", "created_at")
    list_filter = ("status", "is_default")
    search_fields = ("label", "code")


@admin.register(DashboardChart)
class DashboardChartAdmin(admin.ModelAdmin):
    list_display = ("label", "identifier", "template_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("label", "identifier", "template_name")

    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget(width="100%", height="300px")},
    }


@admin.register(DashboardViewChart)
class DashboardViewChartAdmin(admin.ModelAdmin):
    list_display = ("mode", "chart", "order", "status")
    list_filter = ("mode", "chart", "status")
    search_fields = ("mode__label", "chart__label")
    ordering = ("mode", "order")

    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget(width="100%", height="300px")},
    }


admin.site.site_header = "Ambrosia Dashboard Admin"
admin.site.site_title = "Ambrosia Admin"
admin.site.index_title = "Administration"

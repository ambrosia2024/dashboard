# lumenix/admin.py

from django.contrib import admin, messages
from django.db.models import Count, JSONField
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django_json_widget.widgets import JSONEditorWidget
# from django.utils import timezone

from .models import (Vocabulary, Scheme, Concept, PlantConcept, PathogenConcept, ConceptHistory, DashboardChart,
                     DashboardViewChart, DashboardViewMode, SidebarChartLink, NutsRegion, ScioModel)
from .services.models_sync import sync_models
from .services.nuts_sync import sync_nuts
from .services.vocabulary_sync import sync_vocabulary


class ApiSyncedReadOnlyAdmin(admin.ModelAdmin):
    """
    SCiO-backed models are API-owned and must not be modified manually in admin.
    """
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and request.user.is_staff)


class ScioModelNameDuplicateFilter(admin.SimpleListFilter):
    title = "duplicate name"
    parameter_name = "name_dup"

    def lookups(self, request, model_admin):
        return (
            ("dup", "Duplicate"),
            ("unique", "Unique"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value not in {"dup", "unique"}:
            return queryset

        dup_names = (
            queryset.values("name")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .values_list("name", flat=True)
        )
        if value == "dup":
            return queryset.filter(name__in=dup_names)
        return queryset.exclude(name__in=dup_names)


@admin.register(Vocabulary)
class VocabularyAdmin(ApiSyncedReadOnlyAdmin):
    list_display = ("id", "status", "created_at")
    list_filter = ("status",)

@admin.register(Scheme)
class SchemeAdmin(ApiSyncedReadOnlyAdmin):
    list_display = ("uri", "vocabulary", "status")
    search_fields = ("uri", "title__en")
    list_filter = ("vocabulary", "status")

@admin.register(Concept)
class ConceptAdmin(ApiSyncedReadOnlyAdmin):
    list_display = ("uri", "vocabulary", "scheme", "ambrosia_supported_badge", "status", "updated_at")
    search_fields = ("uri", "pref_label__en")
    list_filter = ("vocabulary", "status", "ambrosia_supported")

    @admin.display(description="Ambrosia Supported", ordering="ambrosia_supported")
    def ambrosia_supported_badge(self, obj):
        if obj.ambrosia_supported:
            return format_html('<span style="color:#16a34a;font-weight:700;">✓</span>')
        return format_html('<span style="color:#ef4444;font-weight:700;">✗</span>')

@admin.register(PlantConcept)
class PlantConceptAdmin(ConceptAdmin):
    def get_ordering(self, request):
        return ("-ambrosia_supported", "uri")

@admin.register(PathogenConcept)
class PathogenConceptAdmin(ConceptAdmin):
    def get_ordering(self, request):
        return ("-ambrosia_supported", "uri")

@admin.register(ConceptHistory)
class ConceptHistoryAdmin(ApiSyncedReadOnlyAdmin):
    list_display = ("concept", "change_type", "changed_at")
    list_filter = ("change_type",)
    search_fields = ("concept__uri",)


@admin.register(NutsRegion)
class NutsRegionAdmin(ApiSyncedReadOnlyAdmin):
    list_display = ("notation", "level", "pref_label", "status", "updated_at")
    list_filter = ("level", "status")
    search_fields = ("notation", "pref_label", "alt_labels_en")
    ordering = ("level", "notation")


@admin.register(ScioModel)
class ScioModelAdmin(ApiSyncedReadOnlyAdmin):
    list_display = ("name", "external_id", "duplicate_name_badge", "status", "cpu_cores_required", "ram_gb_required", "updated_at")
    search_fields = ("name", "external_id", "source_url", "image_tag")
    list_filter = ("status", ScioModelNameDuplicateFilter)
    ordering = ("name",)

    @admin.display(description="Duplicate Name")
    def duplicate_name_badge(self, obj):
        is_dup = ScioModel.objects.filter(name=obj.name).exclude(pk=obj.pk).exists()
        if is_dup:
            return format_html('<span style="color:#ef4444;font-weight:700;">Duplicate</span>')
        return format_html('<span style="color:#16a34a;font-weight:700;">Unique</span>')

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


@admin.register(SidebarChartLink)
class SidebarChartLinkAdmin(admin.ModelAdmin):
    list_display = ("menu_label", "menu_code", "display_label", "chart", "order", "status")
    list_filter = ("menu_code", "status")
    search_fields = ("menu_label", "menu_code", "label_override", "chart__label", "chart__identifier")
    ordering = ("menu_code", "order")


admin.site.site_header = "Ambrosia Dashboard Admin"
admin.site.site_title = "Ambrosia Admin"
admin.site.index_title = "Administration"


# Split SCiO vocabulary models into their own section on admin index.
_ORIGINAL_GET_APP_LIST = admin.site.get_app_list


def _custom_get_app_list(request, app_label=None):
    # Keep default behavior for app-specific pages (/admin/<app_label>/).
    if app_label:
        return _ORIGINAL_GET_APP_LIST(request, app_label=app_label)

    app_list = _ORIGINAL_GET_APP_LIST(request, app_label=app_label)

    scio_object_names = {
        "ScioModel",
        "NutsRegion",
        "Vocabulary",
        "Scheme",
        "Concept",
        "ConceptHistory",
        "PlantConcept",
        "PathogenConcept",
    }
    scio_order = {
        "ScioModel": 1,
        "NutsRegion": 2,
        "Scheme": 3,
        "Vocabulary": 4,
        "Concept": 5,
        "ConceptHistory": 6,
        "PlantConcept": 7,
        "PathogenConcept": 8,
    }

    scio_models = []
    for app in app_list:
        if app.get("app_label") != "lumenix":
            continue

        kept_models = []
        for model in app.get("models", []):
            if model.get("object_name") in scio_object_names:
                scio_models.append(model)
            else:
                kept_models.append(model)
        app["models"] = kept_models

    if scio_models:
        scio_models.sort(key=lambda m: scio_order.get(m.get("object_name"), 999))
        scio_app = {
            "name": "SCiO",
            "app_label": "scio",
            "app_url": "",
            "has_module_perms": True,
            "models": scio_models,
        }
        app_list.insert(0, scio_app)

    return app_list


admin.site.get_app_list = _custom_get_app_list


def _sync_vocab_from_admin(request, vocab_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        res = sync_vocabulary(vocab_id=vocab_id, reset=False)
        messages.success(
            request,
            f"{vocab_id} sync completed: created={res['created']}, updated={res['updated']}, unchanged={res['unchanged']}, "
            f"deleted_concepts={res.get('deleted_concepts', 0)}, deleted_schemes={res.get('deleted_schemes', 0)}",
        )
    except Exception as exc:
        messages.error(request, f"{vocab_id} sync failed: {exc}")

    return redirect("admin:index")


def _sync_plants_view(request):
    return _sync_vocab_from_admin(request, "plants")


def _sync_pathogens_view(request):
    return _sync_vocab_from_admin(request, "pathogens")


def _sync_all_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    totals = {"created": 0, "updated": 0, "unchanged": 0, "deleted_concepts": 0, "deleted_schemes": 0}
    try:
        for vocab_id in ("plants", "pathogens"):
            res = sync_vocabulary(vocab_id=vocab_id, reset=False)
            for k in totals:
                totals[k] += res[k]
        messages.success(
            request,
            f"all sync completed: created={totals['created']}, updated={totals['updated']}, unchanged={totals['unchanged']}, "
            f"deleted_concepts={totals['deleted_concepts']}, deleted_schemes={totals['deleted_schemes']}",
        )
    except Exception as exc:
        messages.error(request, f"all sync failed: {exc}")

    return redirect("admin:index")


def _sync_nuts_level_view(request, level):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        res = sync_nuts(level=level, reset=False)
        messages.success(
            request,
            f"NUTS L{level} sync completed: created={res['created']}, updated={res['updated']}, unchanged={res['unchanged']}, deleted={res.get('deleted', 0)}",
        )
    except Exception as exc:
        messages.error(request, f"NUTS L{level} sync failed: {exc}")

    return redirect("admin:index")


def _sync_nuts_l0_view(request):
    return _sync_nuts_level_view(request, 0)


def _sync_nuts_l1_view(request):
    return _sync_nuts_level_view(request, 1)


def _sync_nuts_l2_view(request):
    return _sync_nuts_level_view(request, 2)


def _sync_nuts_l3_view(request):
    return _sync_nuts_level_view(request, 3)


def _sync_nuts_all_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    totals = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    try:
        for level in (0, 1, 2, 3):
            res = sync_nuts(level=level, reset=False)
            for k in totals:
                totals[k] += res[k]
        messages.success(
            request,
            f"NUTS all-level sync completed: created={totals['created']}, updated={totals['updated']}, unchanged={totals['unchanged']}, deleted={totals['deleted']}",
        )
    except Exception as exc:
        messages.error(request, f"NUTS all-level sync failed: {exc}")

    return redirect("admin:index")


def _sync_models_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        res = sync_models(reset=False)
        messages.success(
            request,
            f"models sync completed: created={res['created']}, updated={res['updated']}, unchanged={res['unchanged']}, "
            f"deleted={res.get('deleted', 0)}, deduped={res['deduped']}",
        )
    except Exception as exc:
        messages.error(request, f"models sync failed: {exc}")

    return redirect("admin:index")


_ORIGINAL_GET_URLS = admin.site.get_urls


def _custom_get_urls():
    custom_urls = [
        path(
            "sync-vocabulary/plants/",
            admin.site.admin_view(_sync_plants_view),
            name="sync-vocabulary-plants",
        ),
        path(
            "sync-vocabulary/pathogens/",
            admin.site.admin_view(_sync_pathogens_view),
            name="sync-vocabulary-pathogens",
        ),
        path(
            "sync-vocabulary/all/",
            admin.site.admin_view(_sync_all_view),
            name="sync-vocabulary-all",
        ),
        path(
            "sync-nuts/0/",
            admin.site.admin_view(_sync_nuts_l0_view),
            name="sync-nuts-0",
        ),
        path(
            "sync-nuts/1/",
            admin.site.admin_view(_sync_nuts_l1_view),
            name="sync-nuts-1",
        ),
        path(
            "sync-nuts/2/",
            admin.site.admin_view(_sync_nuts_l2_view),
            name="sync-nuts-2",
        ),
        path(
            "sync-nuts/3/",
            admin.site.admin_view(_sync_nuts_l3_view),
            name="sync-nuts-3",
        ),
        path(
            "sync-nuts/all/",
            admin.site.admin_view(_sync_nuts_all_view),
            name="sync-nuts-all",
        ),
        path(
            "sync-models/",
            admin.site.admin_view(_sync_models_view),
            name="sync-models",
        ),
    ]
    return custom_urls + _ORIGINAL_GET_URLS()


admin.site.get_urls = _custom_get_urls

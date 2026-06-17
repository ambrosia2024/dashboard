# lumenix/admin.py

from datetime import date
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.contrib import admin, messages
from django.db.models import Count, JSONField
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html, format_html_join
from django_json_widget.widgets import JSONEditorWidget
# from django.utils import timezone

from .forms import EmailOrUsernameAdminAuthenticationForm
from .models import (Vocabulary, Scheme, Concept, PlantConcept, PathogenConcept, ConceptHistory, DashboardChart,
                     DashboardViewChart, DashboardViewMode, SidebarChartLink, NutsRegion, ScioModel, UserProfile,
                     PathogenQuerySpec, PathogenConcentrationRecord, AdminMenuMaster)
from .services.models_sync import sync_models
from .services.nuts_sync import sync_nuts
from .services.pathogen_query import sync_pathogen_query_spec
from .services.vocabulary_sync import sync_vocabulary
from .tasks import sync_pathogen_query_spec_task, sync_pathogen_query_specs_batch_task


class ApiSyncedReadOnlyAdmin(admin.ModelAdmin):
    """
    Source API-backed models are read-only and must not be modified manually in admin.
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


def _pathogen_sync_queue_available():
    return bool(getattr(settings, "CELERY_BROKER_URL", "").strip())


def _sync_lock_timeout_seconds():
    return max(60, int(getattr(settings, "ADMIN_SYNC_LOCK_TIMEOUT_SECONDS", 7 * 24 * 60 * 60)))


def _admin_sync_lock_key(name):
    return "admin-sync-lock:global"


def _acquire_admin_sync_lock(request, name, label):
    key = _admin_sync_lock_key(name)
    acquired = cache.add(key, label, timeout=_sync_lock_timeout_seconds())
    if not acquired:
        running_label = cache.get(key) or "A sync job"
        messages.warning(request, f"{running_label} is already running or queued. Please wait for it to finish before starting another sync.")
        return None
    return key


def _release_admin_sync_lock(key):
    if key:
        cache.delete(key)


class DatalistTextInput(forms.TextInput):
    def __init__(self, options=(), datalist_id="choices-list", attrs=None):
        super().__init__(attrs)
        self.options = list(options)
        self.datalist_id = datalist_id

    def get_context(self, name, value, attrs):
        attrs = attrs or {}
        attrs["list"] = self.datalist_id
        return super().get_context(name, value, attrs)

    def render(self, name, value, attrs=None, renderer=None):
        input_html = super().render(name, value, attrs, renderer)
        options_html = format_html_join(
            "",
            '<option value="{}">{}</option>',
            ((option_value, option_label) for option_value, option_label in self.options),
        )
        datalist_html = format_html('<datalist id="{}">{}</datalist>', self.datalist_id, options_html)
        return format_html("{}{}", input_html, datalist_html)


def _concept_api_identifier(concept):
    parsed = urlparse(concept.uri or "")
    fragment = (parsed.fragment or "").rstrip("/")
    source = fragment or parsed.path
    tail = source.rstrip("/").split("/")[-1]
    return tail or concept.uri


def _concept_choice_label(concept):
    label = concept.pref_label.get("en") or concept.uri
    identifier = _concept_api_identifier(concept)
    support = "supported" if concept.ambrosia_supported else "not marked supported"
    return f"{label} ({identifier}, {support})"


def _build_pathogen_spec_name(plant: str, pathogen: str, nuts_code: str, start_date, end_date, time_scale: str = "daily") -> str:
    return f"{plant}_{pathogen}_{nuts_code}_{time_scale}_{start_date.isoformat()}_{end_date.isoformat()}"


def _queue_pathogen_specs_in_background(spec_ids, lock_key=None):
    spec_ids = [int(spec_id) for spec_id in spec_ids]
    if not spec_ids:
        return None
    if len(spec_ids) == 1:
        return sync_pathogen_query_spec_task.delay(spec_ids[0], lock_key=lock_key)
    return sync_pathogen_query_specs_batch_task.delay(spec_ids, lock_key=lock_key)


def _parse_iso_date_setting(value, fallback):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return fallback


def _pathogen_supported_date_range():
    start = _parse_iso_date_setting(
        getattr(settings, "SCIO_PATHOGEN_AVAILABLE_START_DATE", ""),
        date(1971, 1, 1),
    )
    end = _parse_iso_date_setting(
        getattr(settings, "SCIO_PATHOGEN_AVAILABLE_END_DATE", ""),
        date(2095, 12, 31),
    )
    return start, end


class PathogenQuerySpecAdminForm(forms.ModelForm):
    name = forms.CharField(required=False, widget=forms.HiddenInput())
    plant = forms.ChoiceField()
    pathogen = forms.ChoiceField()
    nuts_code = forms.CharField(label="NUTS code")
    start_date = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    class Meta:
        model = PathogenQuerySpec
        fields = "__all__"

    @staticmethod
    def _build_spec_name(cleaned_data):
        plant = (cleaned_data.get("plant") or "").strip()
        pathogen = (cleaned_data.get("pathogen") or "").strip()
        nuts_code = (cleaned_data.get("nuts_code") or "").strip()
        time_scale = (cleaned_data.get("time_scale") or "").strip()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if not (plant and pathogen and nuts_code and time_scale and start_date and end_date):
            return ""

        return (
            f"{plant}_{pathogen}_{nuts_code}_{time_scale}_"
            f"{start_date.isoformat()}_{end_date.isoformat()}"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        supported_plants = PlantConcept.objects.filter(ambrosia_supported=True).order_by("uri")
        supported_pathogens = PathogenConcept.objects.filter(ambrosia_supported=True).order_by("uri")
        if not supported_plants.exists():
            supported_plants = PlantConcept.objects.order_by("uri")
        if not supported_pathogens.exists():
            supported_pathogens = PathogenConcept.objects.order_by("uri")

        plant_choices = [
            (_concept_api_identifier(concept), _concept_choice_label(concept))
            for concept in supported_plants
        ]
        pathogen_choices = [
            (_concept_api_identifier(concept), _concept_choice_label(concept))
            for concept in supported_pathogens
        ]
        nuts_choices = [
            (region.notation, f"L{region.level} {region.notation} - {region.pref_label}")
            for region in NutsRegion.objects.filter(status=1, level=2).order_by("notation")
        ]

        range_start, range_end = _pathogen_supported_date_range()
        self.fields["start_date"].initial = range_start
        self.fields["end_date"].initial = range_end
        self.fields["start_date"].help_text = f"Pathogen concentration data is currently available from {range_start.isoformat()}."
        self.fields["end_date"].help_text = f"Pathogen concentration data is currently available until {range_end.isoformat()}."

        self.fields["plant"].choices = plant_choices
        self.fields["pathogen"].choices = pathogen_choices
        self.fields["nuts_code"].widget = DatalistTextInput(
            options=nuts_choices,
            datalist_id="nuts-code-options",
            attrs={"placeholder": "Type NUTS2 code or region name"},
        )

        self.fields["plant"].help_text = "Choose from synced plant concepts marked as Ambrosia supported."
        self.fields["pathogen"].help_text = "Choose from synced pathogen concepts marked as Ambrosia supported."
        self.fields["nuts_code"].help_text = "Choose from synced NUTS level 2 regions."

        if not plant_choices:
            self.fields["plant"].help_text = "No synced plant concepts found. Run plant sync first."
        if not pathogen_choices:
            self.fields["pathogen"].help_text = "No synced pathogen concepts found. Run pathogen sync first."
        if not nuts_choices:
            self.fields["nuts_code"].help_text = "No synced NUTS level 2 regions found. Run NUTS sync first."

        self._valid_nuts_codes = {value for value, _label in nuts_choices}

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["name"] = self._build_spec_name(cleaned_data)
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = self._build_spec_name(self.cleaned_data)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def clean_nuts_code(self):
        value = (self.cleaned_data.get("nuts_code") or "").strip()
        if not value:
            raise forms.ValidationError("Select a NUTS level 2 region.")
        if hasattr(self, "_valid_nuts_codes") and value not in self._valid_nuts_codes:
            raise forms.ValidationError("Choose a valid synced NUTS level 2 code from the suggestions.")
        return value


class PathogenBulkGenerateForm(forms.Form):
    NUTS_SCOPE_CHOICES = (
        ("all_nuts2", "All synced NUTS level 2 regions"),
        ("single_nuts2", "One NUTS level 2 region"),
    )

    plant = forms.ChoiceField()
    pathogen = forms.ChoiceField()
    nuts_scope = forms.ChoiceField(choices=NUTS_SCOPE_CHOICES, initial="all_nuts2")
    nuts_code = forms.CharField(required=False, label="NUTS code")
    start_date = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    queue_sync = forms.BooleanField(required=False, initial=True, label="Queue sync after creating specs")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        supported_plants = PlantConcept.objects.filter(ambrosia_supported=True).order_by("uri")
        supported_pathogens = PathogenConcept.objects.filter(ambrosia_supported=True).order_by("uri")
        if not supported_plants.exists():
            supported_plants = PlantConcept.objects.order_by("uri")
        if not supported_pathogens.exists():
            supported_pathogens = PathogenConcept.objects.order_by("uri")

        plant_choices = [
            (_concept_api_identifier(concept), _concept_choice_label(concept))
            for concept in supported_plants
        ]
        pathogen_choices = [
            (_concept_api_identifier(concept), _concept_choice_label(concept))
            for concept in supported_pathogens
        ]
        nuts_choices = [
            (region.notation, f"L{region.level} {region.notation} - {region.pref_label}")
            for region in NutsRegion.objects.filter(status=1, level=2).order_by("notation")
        ]

        range_start, range_end = _pathogen_supported_date_range()
        self.fields["start_date"].initial = range_start
        self.fields["end_date"].initial = range_end
        self.fields["start_date"].help_text = f"Pathogen concentration data is currently available from {range_start.isoformat()}."
        self.fields["end_date"].help_text = f"Pathogen concentration data is currently available until {range_end.isoformat()}."

        self.fields["plant"].choices = plant_choices
        self.fields["pathogen"].choices = pathogen_choices
        self.fields["nuts_code"].widget = DatalistTextInput(
            options=nuts_choices,
            datalist_id="bulk-generate-nuts-code-options",
            attrs={"placeholder": "Type NUTS2 code or region name"},
        )
        self.fields["plant"].help_text = "Choose from synced plant concepts."
        self.fields["pathogen"].help_text = "Choose from synced pathogen concepts."
        self.fields["nuts_scope"].help_text = "Create specs either for all synced NUTS2 regions or for one specific NUTS2 region."
        self.fields["nuts_code"].help_text = "Only required when generating for a single NUTS2 region."
        self._valid_nuts_codes = {value for value, _label in nuts_choices}

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        nuts_scope = cleaned_data.get("nuts_scope")
        nuts_code = (cleaned_data.get("nuts_code") or "").strip()

        range_start, range_end = _pathogen_supported_date_range()
        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "End date must be on or after start date.")
        if start_date and start_date < range_start:
            self.add_error("start_date", f"Start date cannot be before {range_start.isoformat()} for pathogen data.")
        if end_date and end_date > range_end:
            self.add_error("end_date", f"End date cannot be after {range_end.isoformat()} for pathogen data.")

        if nuts_scope == "single_nuts2":
            if not nuts_code:
                self.add_error("nuts_code", "Select a NUTS level 2 region.")
            elif nuts_code not in self._valid_nuts_codes:
                self.add_error("nuts_code", "Choose a valid synced NUTS level 2 code from the suggestions.")

        return cleaned_data


class PathogenBulkDeleteForm(forms.Form):
    DELETE_TARGET_CHOICES = (
        ("records", "Delete pathogen concentration records only"),
        ("specs", "Delete pathogen query specs only"),
        ("both", "Delete both specs and records"),
    )

    plant = forms.ChoiceField(required=False)
    pathogen = forms.ChoiceField(required=False)
    nuts_code = forms.CharField(required=False, label="NUTS code")
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    delete_target = forms.ChoiceField(choices=DELETE_TARGET_CHOICES, initial="records")
    confirm_delete = forms.BooleanField(required=True, label="I understand this deletion is irreversible")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        supported_plants = PlantConcept.objects.filter(ambrosia_supported=True).order_by("uri")
        supported_pathogens = PathogenConcept.objects.filter(ambrosia_supported=True).order_by("uri")
        if not supported_plants.exists():
            supported_plants = PlantConcept.objects.order_by("uri")
        if not supported_pathogens.exists():
            supported_pathogens = PathogenConcept.objects.order_by("uri")

        plant_choices = [("", "Any plant")] + [
            (_concept_api_identifier(concept), _concept_choice_label(concept))
            for concept in supported_plants
        ]
        pathogen_choices = [("", "Any pathogen")] + [
            (_concept_api_identifier(concept), _concept_choice_label(concept))
            for concept in supported_pathogens
        ]
        nuts_choices = [
            (region.notation, f"L{region.level} {region.notation} - {region.pref_label}")
            for region in NutsRegion.objects.filter(status=1, level=2).order_by("notation")
        ]

        self.fields["plant"].choices = plant_choices
        self.fields["pathogen"].choices = pathogen_choices
        self.fields["nuts_code"].widget = DatalistTextInput(
            options=nuts_choices,
            datalist_id="bulk-delete-nuts-code-options",
            attrs={"placeholder": "Leave blank for all NUTS2 regions"},
        )
        self.fields["plant"].help_text = "Leave blank to target all plants."
        self.fields["pathogen"].help_text = "Leave blank to target all pathogens."
        self.fields["nuts_code"].help_text = "Leave blank to target all NUTS2 regions."
        self.fields["start_date"].help_text = "Optional lower bound for observed dates/spec ranges."
        self.fields["end_date"].help_text = "Optional upper bound for observed dates/spec ranges."
        self._valid_nuts_codes = {value for value, _label in nuts_choices}

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        nuts_code = (cleaned_data.get("nuts_code") or "").strip()

        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "End date must be on or after start date.")

        if nuts_code and nuts_code not in self._valid_nuts_codes:
            self.add_error("nuts_code", "Choose a valid synced NUTS level 2 code from the suggestions.")

        filters_present = any(
            [
                cleaned_data.get("plant"),
                cleaned_data.get("pathogen"),
                nuts_code,
                start_date,
                end_date,
            ]
        )
        if not filters_present:
            self.fields["confirm_delete"].help_text = "No filters selected: this will delete all matching pathogen data in the chosen target."
        return cleaned_data


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
            return format_html('<span style="color:#16a34a;font-weight:700;">{}</span>', "✓")
        return format_html('<span style="color:#ef4444;font-weight:700;">{}</span>', "✗")

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
            return format_html('<span style="color:#ef4444;font-weight:700;">{}</span>', "Duplicate")
        return format_html('<span style="color:#16a34a;font-weight:700;">{}</span>', "Unique")

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
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "dashboard_mode")
    search_fields = ("user__username", "user__email", "dashboard_mode__label", "dashboard_mode__code")
    autocomplete_fields = ("user", "dashboard_mode")

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


@admin.register(PathogenQuerySpec)
class PathogenQuerySpecAdmin(admin.ModelAdmin):
    form = PathogenQuerySpecAdminForm
    list_display = ("name", "plant", "pathogen", "nuts_code", "start_date", "end_date", "last_synced_at", "status")
    list_filter = ("status", "nuts_code", "plant", "pathogen")
    search_fields = ("name", "plant", "pathogen", "nuts_code")
    actions = ("sync_selected_specs", "delete_selected_specs_and_records", "delete_selected_specs_only")
    readonly_fields = ("last_synced_at",)
    exclude = ("deleted_at",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "status",
                    "plant",
                    "pathogen",
                    "nuts_code",
                    "start_date",
                    "end_date",
                    "time_scale",
                    "last_synced_at",
                )
            },
        ),
    )

    @admin.action(description="Sync selected pathogen datasets")
    def sync_selected_specs(self, request, queryset):
        if not _pathogen_sync_queue_available():
            self.message_user(
                request,
                "Background pathogen sync is not configured. Set CELERY_BROKER_URL and start a Celery worker.",
                level=messages.ERROR,
            )
            return

        spec_ids = list(queryset.values_list("pk", flat=True))
        if not spec_ids:
            self.message_user(request, "No pathogen datasets were queued.", level=messages.WARNING)
            return

        lock_key = _acquire_admin_sync_lock(request, "pathogen-datasets", "Pathogen dataset sync")
        if not lock_key:
            return

        try:
            _queue_pathogen_specs_in_background(spec_ids, lock_key=lock_key)
        except Exception as exc:
            _release_admin_sync_lock(lock_key)
            self.message_user(request, f"Pathogen sync batch could not be queued: {exc}", level=messages.ERROR)
            return

        self.message_user(
            request,
            f"Queued {len(spec_ids)} pathogen dataset(s) in one serial background batch.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Delete selected specs and matching pathogen records")
    def delete_selected_specs_and_records(self, request, queryset):
        total_specs = 0
        total_records = 0
        for spec in queryset:
            total_records += PathogenConcentrationRecord.objects.filter(
                plant=spec.plant,
                pathogen=spec.pathogen,
                nuts_code=spec.nuts_code,
                observed_on__gte=spec.start_date,
                observed_on__lte=spec.end_date,
            ).delete()[0]
            spec.delete()
            total_specs += 1
        self.message_user(
            request,
            f"Deleted {total_specs} pathogen query spec(s) and {total_records} matching pathogen record(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="Delete selected specs only")
    def delete_selected_specs_only(self, request, queryset):
        deleted = queryset.count()
        queryset.delete()
        self.message_user(request, f"Deleted {deleted} pathogen query spec(s).", level=messages.SUCCESS)


@admin.register(PathogenConcentrationRecord)
class PathogenConcentrationRecordAdmin(admin.ModelAdmin):
    list_display = ("plant", "pathogen", "nuts_code", "observed_on", "pathogen_model_value", "temperature_c", "status", "updated_at")
    list_filter = ("status", "plant", "pathogen", "nuts_code")
    search_fields = ("plant", "pathogen", "nuts_code", "source_time", "source_period", "provenance_model_title")
    actions = ("delete_selected_records",)
    readonly_fields = (
        "plant", "pathogen", "nuts_code", "observed_on", "source_time", "source_period",
        "pathogen_model_value", "temperature_c", "outcome", "provenance_model_id", "provenance_model_title",
        "provenance_variable_name", "provenance_fetched_at_ms", "source_payload", "status",
        "deleted_at", "created_at", "updated_at",
    )

    @admin.display(description="Pathogen model value")
    def pathogen_model_value(self, obj):
        return obj.pathogen_model_value

    def has_add_permission(self, request):
        return False

    @admin.action(description="Delete selected pathogen concentration records")
    def delete_selected_records(self, request, queryset):
        deleted = queryset.count()
        queryset.delete()
        self.message_user(request, f"Deleted {deleted} pathogen concentration record(s).", level=messages.SUCCESS)


admin.site.site_header = "Ambrosia Dashboard Admin"
admin.site.site_title = "Ambrosia Admin"
admin.site.index_title = "Administration"
admin.site.login_form = EmailOrUsernameAdminAuthenticationForm


# Split API-backed vocabulary models into their own section on admin index.
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
        "PathogenQuerySpec",
        "PathogenConcentrationRecord",
    }
    scio_order = {
        "ScioModel": 1,
        "NutsRegion": 2,
        "PathogenQuerySpec": 3,
        "PathogenConcentrationRecord": 4,
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
            "name": "Data Sources",
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

    lock_key = _acquire_admin_sync_lock(request, f"vocabulary:{vocab_id}", f"{vocab_id} sync")
    if not lock_key:
        return redirect("admin:index")

    try:
        res = sync_vocabulary(vocab_id=vocab_id, reset=False)
        messages.success(
            request,
            f"{vocab_id} sync completed: created={res['created']}, updated={res['updated']}, unchanged={res['unchanged']}, "
            f"deleted_concepts={res.get('deleted_concepts', 0)}, deleted_schemes={res.get('deleted_schemes', 0)}",
        )
    except Exception as exc:
        messages.error(request, f"{vocab_id} sync failed: {exc}")
    finally:
        _release_admin_sync_lock(lock_key)

    return redirect("admin:index")


def _sync_plants_view(request):
    return _sync_vocab_from_admin(request, "plants")


def _sync_pathogens_view(request):
    return _sync_vocab_from_admin(request, "pathogens")


def _sync_all_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    lock_key = _acquire_admin_sync_lock(request, "vocabulary:all", "Vocabulary sync")
    if not lock_key:
        return redirect("admin:index")

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
    finally:
        _release_admin_sync_lock(lock_key)

    return redirect("admin:index")


def _sync_nuts_level_view(request, level):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    lock_key = _acquire_admin_sync_lock(request, f"nuts:{level}", f"NUTS L{level} sync")
    if not lock_key:
        return redirect("admin:index")

    try:
        res = sync_nuts(level=level, reset=False)
        messages.success(
            request,
            f"NUTS L{level} sync completed: created={res['created']}, updated={res['updated']}, unchanged={res['unchanged']}, deleted={res.get('deleted', 0)}",
        )
    except Exception as exc:
        messages.error(request, f"NUTS L{level} sync failed: {exc}")
    finally:
        _release_admin_sync_lock(lock_key)

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

    lock_key = _acquire_admin_sync_lock(request, "nuts:all", "NUTS all-level sync")
    if not lock_key:
        return redirect("admin:index")

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
    finally:
        _release_admin_sync_lock(lock_key)

    return redirect("admin:index")


def _sync_models_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    lock_key = _acquire_admin_sync_lock(request, "models", "Models sync")
    if not lock_key:
        return redirect("admin:index")

    try:
        res = sync_models(reset=False)
        messages.success(
            request,
            f"models sync completed: created={res['created']}, updated={res['updated']}, unchanged={res['unchanged']}, "
            f"deleted={res.get('deleted', 0)}, deduped={res['deduped']}",
        )
    except Exception as exc:
        messages.error(request, f"models sync failed: {exc}")
    finally:
        _release_admin_sync_lock(lock_key)

    return redirect("admin:index")


def _sync_pathogen_specs_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not _pathogen_sync_queue_available():
        messages.error(request, "Background pathogen sync is not configured. Set CELERY_BROKER_URL and start a Celery worker.")
        return redirect("admin:index")

    specs = PathogenQuerySpec.active_objects.all()
    if not specs.exists():
        messages.warning(request, "No active pathogen query specs are configured.")
        return redirect("admin:index")

    spec_ids = list(specs.values_list("pk", flat=True))
    lock_key = _acquire_admin_sync_lock(request, "pathogen-datasets", "Pathogen dataset sync")
    if not lock_key:
        return redirect("admin:index")

    try:
        _queue_pathogen_specs_in_background(spec_ids, lock_key=lock_key)
    except Exception as exc:
        _release_admin_sync_lock(lock_key)
        messages.error(request, f"pathogen sync queueing failed: {exc}")
        return redirect("admin:index")

    if spec_ids:
        messages.success(request, f"Queued {len(spec_ids)} pathogen sync spec(s) in one serial background batch.")
    else:
        messages.warning(request, "No pathogen datasets were queued.")

    return redirect("admin:index")


def _bulk_generate_pathogen_specs_view(request):
    if request.method == "POST":
        form = PathogenBulkGenerateForm(request.POST)
        if form.is_valid():
            plant = form.cleaned_data["plant"]
            pathogen = form.cleaned_data["pathogen"]
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            queue_sync = form.cleaned_data["queue_sync"]
            nuts_scope = form.cleaned_data["nuts_scope"]

            if nuts_scope == "all_nuts2":
                nuts_codes = list(
                    NutsRegion.objects.filter(status=1, level=2)
                    .order_by("notation")
                    .values_list("notation", flat=True)
                )
            else:
                nuts_codes = [form.cleaned_data["nuts_code"]]

            if not nuts_codes:
                messages.warning(request, "No synced NUTS level 2 regions were found.")
                return redirect("admin:pathogen-bulk-generate")

            created_count = 0
            existing_count = 0
            specs_to_queue = []
            for nuts_code in nuts_codes:
                spec_name = _build_pathogen_spec_name(plant, pathogen, nuts_code, start_date, end_date)
                spec, created = PathogenQuerySpec.objects.get_or_create(
                    plant=plant,
                    pathogen=pathogen,
                    nuts_code=nuts_code,
                    start_date=start_date,
                    end_date=end_date,
                    time_scale="daily",
                    defaults={"name": spec_name, "status": 1},
                )
                if not created:
                    existing_count += 1
                    changed = False
                    if spec.name != spec_name:
                        spec.name = spec_name
                        changed = True
                    if spec.status != 1:
                        spec.status = 1
                        changed = True
                    if changed:
                        spec.save(update_fields=["name", "status", "updated_at"])
                else:
                    created_count += 1

                if queue_sync:
                    if not _pathogen_sync_queue_available():
                        messages.error(
                            request,
                            "Specs were created, but background sync is not configured. Set CELERY_BROKER_URL and start a Celery worker.",
                        )
                        queue_sync = False
                    else:
                        specs_to_queue.append(spec.pk)

            queued_count = 0
            if queue_sync and specs_to_queue:
                lock_key = _acquire_admin_sync_lock(request, "pathogen-datasets", "Pathogen dataset sync")
                if lock_key:
                    try:
                        _queue_pathogen_specs_in_background(specs_to_queue, lock_key=lock_key)
                        queued_count = len(specs_to_queue)
                    except Exception as exc:
                        _release_admin_sync_lock(lock_key)
                        messages.error(request, f"pathogen sync queueing failed: {exc}")

            messages.success(
                request,
                f"Prepared {created_count + existing_count} pathogen query spec(s): created={created_count}, existing={existing_count}, queued={queued_count}.",
            )
            return redirect("admin:lumenix_pathogenqueryspec_changelist")
    else:
        form = PathogenBulkGenerateForm()

    context = {
        **admin.site.each_context(request),
        "title": "Bulk generate pathogen query specs",
        "opts": PathogenQuerySpec._meta,
        "form": form,
        "subtitle": "Create pathogen query specs for one or all synced NUTS2 regions and optionally queue background sync. The default range is the source-data period: 1971-01-01 to 2095-12-31.",
    }
    return TemplateResponse(request, "admin/pathogen_bulk_generate.html", context)


def _filter_pathogen_records(*, plant="", pathogen="", nuts_code="", start_date=None, end_date=None):
    queryset = PathogenConcentrationRecord.objects.all()
    if plant:
        queryset = queryset.filter(plant=plant)
    if pathogen:
        queryset = queryset.filter(pathogen=pathogen)
    if nuts_code:
        queryset = queryset.filter(nuts_code=nuts_code)
    if start_date:
        queryset = queryset.filter(observed_on__gte=start_date)
    if end_date:
        queryset = queryset.filter(observed_on__lte=end_date)
    return queryset


def _filter_pathogen_specs(*, plant="", pathogen="", nuts_code="", start_date=None, end_date=None):
    queryset = PathogenQuerySpec.objects.all()
    if plant:
        queryset = queryset.filter(plant=plant)
    if pathogen:
        queryset = queryset.filter(pathogen=pathogen)
    if nuts_code:
        queryset = queryset.filter(nuts_code=nuts_code)
    if start_date:
        queryset = queryset.filter(end_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(start_date__lte=end_date)
    return queryset


def _bulk_delete_pathogen_data_view(request):
    if request.method == "POST":
        form = PathogenBulkDeleteForm(request.POST)
        if form.is_valid():
            plant = form.cleaned_data.get("plant") or ""
            pathogen = form.cleaned_data.get("pathogen") or ""
            nuts_code = (form.cleaned_data.get("nuts_code") or "").strip()
            start_date = form.cleaned_data.get("start_date")
            end_date = form.cleaned_data.get("end_date")
            target = form.cleaned_data["delete_target"]

            deleted_records = deleted_specs = 0
            if target in {"records", "both"}:
                record_qs = _filter_pathogen_records(
                    plant=plant,
                    pathogen=pathogen,
                    nuts_code=nuts_code,
                    start_date=start_date,
                    end_date=end_date,
                )
                deleted_records = record_qs.count()
                record_qs.delete()

            if target in {"specs", "both"}:
                spec_qs = _filter_pathogen_specs(
                    plant=plant,
                    pathogen=pathogen,
                    nuts_code=nuts_code,
                    start_date=start_date,
                    end_date=end_date,
                )
                deleted_specs = spec_qs.count()
                spec_qs.delete()

            messages.success(
                request,
                f"Deleted pathogen data: specs={deleted_specs}, records={deleted_records}.",
            )
            return redirect("admin:index")
    else:
        form = PathogenBulkDeleteForm()

    context = {
        **admin.site.each_context(request),
        "title": "Delete pathogen specs and records",
        "opts": PathogenConcentrationRecord._meta,
        "form": form,
        "subtitle": "Delete pathogen records, pathogen query specs, or both for a selected date range, plant, pathogen, and location. Leave filters blank to delete all.",
    }
    return TemplateResponse(request, "admin/pathogen_bulk_delete.html", context)


@admin.register(AdminMenuMaster)
class AdminMenuMasterAdmin(admin.ModelAdmin):
    list_display = (
        "menu_name",
        "menu_type",
        "parent",
        "menu_route",
        "menu_icon",
        "open_in_new_tab",
        "order",
        "status",
        "updated_at",
    )
    list_display_links = ("menu_name",)
    list_editable = ("order", "status")
    list_filter = ("menu_type", "status", "open_in_new_tab")
    search_fields = ("menu_name", "menu_route", "menu_icon")
    ordering = ("order", "id")
    autocomplete_fields = ("parent",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        (None, {
            "fields": ("menu_name", "menu_type", "parent", "menu_route", "open_in_new_tab", "menu_icon", "order"),
        }),
        ("Status & audit", {
            "fields": ("status", "created_at", "updated_at", "deleted_at"),
        }),
    )


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
        path(
            "sync-pathogen/",
            admin.site.admin_view(_sync_pathogen_specs_view),
            name="sync-pathogen",
        ),
        path(
            "pathogen/generate/",
            admin.site.admin_view(_bulk_generate_pathogen_specs_view),
            name="pathogen-bulk-generate",
        ),
        path(
            "pathogen/delete/",
            admin.site.admin_view(_bulk_delete_pathogen_data_view),
            name="pathogen-bulk-delete",
        ),
    ]
    return custom_urls + _ORIGINAL_GET_URLS()


admin.site.get_urls = _custom_get_urls

# lumenix/models.py

import hashlib
import json

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.db.models import Index as GISIndex
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class ActivePageManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=1)


class BaseModel(models.Model):
    STATUS_CHOICES = [
        (1, 'Active'),
        (0, 'Inactive'),
        (2, 'Deleted'),
    ]

    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name='Status')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Deleted At')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    objects = models.Manager()  # Default manager.
    active_objects = ActivePageManager()  # Custom manager for active objects.

    class Meta:
        abstract = True

    def soft_delete(self):
        self.status = 2
        self.deleted_at = timezone.now()
        self.save()


class Vocabulary(models.Model):
    """
    A top-level vocabulary: e.g. 'plants' or 'pathogens'.
    Keeping it generic so the same tables serve both vocabs.
    """
    VOCAB_IDS = (
        ("plants", "Plants"),
        ("pathogens", "Pathogens"),
    )
    id = models.CharField(primary_key=True, max_length=32, choices=VOCAB_IDS)  # 'plants' / 'pathogens'
    status = models.SmallIntegerField(default=1, choices=((1, "Active"), (0, "Inactive"), (2, "Deleted")), db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "vocabulary"
        verbose_name = "Vocabulary"
        verbose_name_plural = "Vocabularies"

    def __str__(self):
        return self.id


class Scheme(models.Model):
    """
    A SKOS ConceptScheme entry as returned by the API.
    """
    vocabulary = models.ForeignKey(Vocabulary, on_delete=models.CASCADE, related_name="schemes")
    uri = models.URLField(unique=True, help_text="ConceptScheme @id, e.g. https://.../vocab/scheme/cereal")
    title = models.JSONField(default=dict, blank=True)        # { "en": "Cereal Vocabulary", ... }
    description = models.JSONField(default=dict, blank=True)  # { "en": "..." }
    status = models.SmallIntegerField(default=1, choices=((1, "Active"), (0, "Inactive"), (2, "Deleted")), db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "vocabulary_scheme"
        indexes = [models.Index(fields=["vocabulary"])]
        verbose_name = "Schema"
        verbose_name_plural = "Schemas"

    def __str__(self):
        return self.title.get("en") or self.uri


class Concept(models.Model):
    """
    A SKOS Concept. We key by 'uri' which is globally unique.
    """
    vocabulary = models.ForeignKey(Vocabulary, on_delete=models.CASCADE, related_name="concepts")
    scheme = models.ForeignKey(Scheme, on_delete=models.SET_NULL, null=True, blank=True, related_name="concepts")

    uri = models.URLField(unique=True, help_text="Concept @id, e.g. https://.../vocab/concept/cereal/barley")

    # Labels & definitions are multilingual JSON blobs as in the API
    pref_label = models.JSONField(default=dict, blank=True)
    alt_label = models.JSONField(default=dict, blank=True)
    definition = models.JSONField(default=dict, blank=True)
    notation   = models.JSONField(default=dict, blank=True)

    ambrosia_supported = models.BooleanField(default=False)
    status = models.SmallIntegerField(default=1, choices=((1, "Active"), (0, "Inactive"), (2, "Deleted")), db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Relationship lists are URIs: keep as JSON array(s) to avoid cross-row integrity headaches
    broader     = models.JSONField(default=list, blank=True)
    narrower    = models.JSONField(default=list, blank=True)
    exact_match = models.JSONField(default=list, blank=True)
    close_match = models.JSONField(default=list, blank=True)
    related     = models.JSONField(default=list, blank=True)
    in_scheme   = models.JSONField(default=list, blank=True)

    # Normalised fingerprint of the fields; lets us detect substantive change efficiently
    content_hash = models.CharField(max_length=64, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vocabulary_concept"
        indexes = [
            models.Index(fields=["vocabulary"]),
            models.Index(fields=["scheme"]),
            models.Index(fields=["content_hash"]),
        ]
        verbose_name = "Concept"
        verbose_name_plural = "Concepts"

    def __str__(self):
        return self.pref_label.get("en") or self.uri


class PlantConceptManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(vocabulary_id="plants", status=1)


class PathogenConceptManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(vocabulary_id="pathogens", status=1)


class PlantConcept(Concept):
    objects = PlantConceptManager()
    class Meta:
        proxy = True
        verbose_name = "Plant Concept"
        verbose_name_plural = "Plant Concepts"


class PathogenConcept(Concept):
    objects = PathogenConceptManager()
    class Meta:
        proxy = True
        verbose_name = "Pathogen Concept"
        verbose_name_plural = "Pathogen Concepts"


class ConceptHistory(models.Model):
    """
    Append-only snapshot of a Concept whenever it changes.
    Stores the full JSON payload (+ hash) so we can diff later.
    """
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="history")
    change_type = models.CharField(max_length=16, choices=(("created","created"),("updated","updated")))
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)
    content_hash = models.CharField(max_length=64)
    snapshot = models.JSONField()  # full concept dict as we persisted it

    class Meta:
        db_table = "vocabulary_concept_history"
        indexes = [models.Index(fields=["concept", "changed_at"])]
        verbose_name = "Concept History"
        verbose_name_plural = "Concept History"


class NutsRegion(models.Model):
    """
    NUTS region entry fetched from /api/nuts/{level}.
    """
    iri = models.URLField(unique=True, help_text="NUTS IRI, e.g. http://data.europa.eu/nuts/code/NL42")
    notation = models.CharField(max_length=16, db_index=True, help_text="NUTS code, e.g. NL42")
    level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        db_index=True,
        help_text="NUTS level: 0, 1, 2, 3",
    )
    pref_label = models.CharField(max_length=255, db_index=True, help_text="Primary label from API")
    alt_labels_en = models.JSONField(default=list, blank=True, help_text="English alternative labels")
    status = models.SmallIntegerField(default=1, choices=((1, "Active"), (0, "Inactive"), (2, "Deleted")), db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "nuts_regions"
        indexes = [
            models.Index(fields=["level", "notation"]),
            models.Index(fields=["level", "pref_label"]),
        ]
        unique_together = [("level", "notation")]
        verbose_name = "NUTS Region"
        verbose_name_plural = "NUTS Regions"

    def __str__(self):
        return f"L{self.level} {self.notation} - {self.pref_label}"


class ScioModel(models.Model):
    """
    Model registry entry fetched from /api/models.
    """
    external_id = models.CharField(max_length=64, unique=True, db_index=True, help_text="Model id from API payload")
    name = models.CharField(max_length=1024, db_index=True)
    source_url = models.TextField(help_text="Model download/source URL")
    image_tag = models.CharField(max_length=512, blank=True, default="")
    cpu_cores_required = models.FloatField(default=0.0)
    ram_gb_required = models.FloatField(default=0.0)
    gpu_count_required = models.PositiveIntegerField(default=0)
    gpu_memory_gb_required = models.FloatField(default=0.0)
    min_cuda_version_required = models.CharField(max_length=64, null=True, blank=True)
    source_timestamp = models.BigIntegerField(null=True, blank=True, help_text="models[n]._id.timestamp")
    source_date_ms = models.BigIntegerField(null=True, blank=True, help_text="models[n]._id.date")
    status = models.SmallIntegerField(default=1, choices=((1, "Active"), (0, "Inactive"), (2, "Deleted")), db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scio_models"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["updated_at"]),
        ]
        verbose_name = "SCiO Model"
        verbose_name_plural = "SCiO Models"

    def __str__(self):
        return f"{self.name} ({self.external_id})"


class ClimateData(BaseModel):
    timestamp = models.DateTimeField(verbose_name="Timestamp")
    location = gis_models.PointField(geography=True, null=True, blank=True)
    temperature_2m = models.FloatField(verbose_name="2m Temperature (°C)", default=0.0)
    sea_surface_temperature = models.FloatField(
        verbose_name="Sea Surface Temperature (°C)",
        default=0.0, null=True, blank=True
    )
    max_temperature_2m = models.FloatField(
        verbose_name="Max 2m Temperature (°C)",
        default=0.0, null=True, blank=True
    )
    min_temperature_2m = models.FloatField(
        verbose_name="Min 2m Temperature (°C)",
        default=0.0, null=True, blank=True
    )
    skin_temperature = models.FloatField(
        verbose_name="Skin Temperature (°C)",
        default=0.0, null=True, blank=True
    )

    class Meta:
        db_table = "climate_data"
        verbose_name = "Climate Data"
        verbose_name_plural = "Climate Data Records"
        indexes = [
            models.Index(fields=["timestamp"]),
            GISIndex(fields=["location"]),
            # models.Index(fields=["latitude", "longitude"]),
        ]

    def clean(self):
        """Ensure temperature values are within a reasonable range."""
        for field in ["temperature_2m", "sea_surface_temperature", "max_temperature_2m", "min_temperature_2m",
                      "skin_temperature"]:
            value = getattr(self, field, None)
            if value is not None and not (-100 <= value <= 100):
                raise ValidationError({field: f"{field} must be within the range of -100 to 100°C."})

    def __str__(self):
        if self.location:
            return f"{self.timestamp} - {self.temperature_2m}°C at ({self.location.y}, {self.location.x})"
        return f"{self.timestamp} - {self.temperature_2m}°C (No location)"


class TimeScale(models.TextChoices):
    WEEKLY = "weekly", _("Weekly")
    MONTHLY = "monthly", _("Monthly")
    QUARTERLY = "quarterly", _("Quarterly")
    YEARLY = "yearly", _("Yearly")
    DECADE = "decade", _("Decade")

class ClimateModelChoices(models.TextChoices):
    RCP26 = "RCP2.6", "RCP2.6"
    RCP45 = "RCP4.5", "RCP4.5"
    RCP6  = "RCP6",   "RCP6"
    RCP85 = "RCP8.5", "RCP8.5"

class SimulationKey(BaseModel):
    """
    Defines a unique simulation REQUEST (used for caching).
    Multiple runs (job_ids) can reference the same key.
    """
    simulation_type = models.CharField(max_length=64)  # e.g. "disease-risk"
    crop = models.CharField(max_length=255)
    nuts_id = models.CharField(
        max_length=8,
        validators=[RegexValidator(r"^[A-Z]{2}\d{1,2}$", message="NUTS code like NL4 or NL42")],
    )
    climate_model = models.CharField(max_length=16, choices=ClimateModelChoices.choices)
    time_period_start = models.DateField()
    time_period_end = models.DateField()
    time_scale = models.CharField(max_length=16, choices=TimeScale.choices)

    # Stable hash over the above fields – unique cache key.
    request_hash = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        db_table = "simulation_keys"
        indexes = [
            models.Index(fields=[
                "simulation_type", "crop", "nuts_id", "climate_model",
                "time_scale", "time_period_start", "time_period_end"
            ], name="idx_simkey_fields"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["simulation_type", "crop", "nuts_id", "climate_model",
                        "time_scale", "time_period_start", "time_period_end"],
                name="uq_simkey_fields"
            ),
        ]

    def clean(self):
        # Ensure start <= end
        if self.time_period_start and self.time_period_end:
            if self.time_period_start > self.time_period_end:
                raise ValidationError({"time_period_start": "Start date must be before end date."})

    def save(self, *args, **kwargs):
        # Compute stable request_hash before save
        key_fields = {
            "simulation_type": self.simulation_type,
            "crop": self.crop,
            "nuts_id": self.nuts_id,
            "climate_model": self.climate_model,
            "time_scale": self.time_scale,
            "time_period_start": self.time_period_start.isoformat() if self.time_period_start else "",
            "time_period_end": self.time_period_end.isoformat() if self.time_period_end else "",
        }
        s = json.dumps(key_fields, sort_keys=True, separators=(",", ":"))
        self.request_hash = hashlib.sha256(s.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.simulation_type}:{self.crop}:{self.nuts_id} [{self.time_period_start}→{self.time_period_end}]"


class SimulationRun(BaseModel):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("queued", "Queued"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    job_id = models.CharField(max_length=128, primary_key=True)
    sim_key = models.ForeignKey(SimulationKey, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)

    submission_timestamp = models.BigIntegerField(null=True, blank=True)
    completion_timestamp = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "simulation_runs"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["sim_key", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.job_id} ({self.status})"


class SimulationResult(models.Model):
    """
    Result series for a run. Current API returns two numeric columns per row.
    """
    job = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name="results")
    idx = models.PositiveIntegerField()  # 0..N order
    x = models.FloatField(null=True, blank=True)  # e.g., time index
    y = models.FloatField(null=True, blank=True)  # e.g., risk score

    class Meta:
        db_table = "simulation_results"
        constraints = [
            models.UniqueConstraint(fields=["job", "idx"], name="uq_result_job_idx"),
        ]
        indexes = [
            models.Index(fields=["job", "idx"]),
        ]

    def __str__(self):
        return f"{self.job.job_id}#{self.idx}: ({self.x}, {self.y})"


# class RoleMaster(models.Model):
#     """
#     User role (Farmer, Policy advisor, Distributor, ...)
#     """
#     name = models.CharField(max_length=100, unique=True)
#
#     class Meta:
#         db_table = "user_roles"
#         verbose_name = "Role Master"
#         verbose_name_plural = "Roles Master"
#
#     def __str__(self):
#         return self.name
#
#
# class UserProfile(models.Model):
#     """
#     One-to-one extension of the Django user storing the selected role.
#     """
#     user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="profile",
#     )
#     role = models.ForeignKey(RoleMaster, on_delete=models.PROTECT, related_name="users")
#
#     class Meta:
#         db_table = "user_profiles"
#
#     def __str__(self):
#         return f"{self.user} ({self.role})"

class DashboardViewMode(BaseModel):
    """
    A named dashboard mode, e.g. 'Default', 'Farmer View', 'Distributor View'.
    Not tied to users; the single user can switch between them.
    """
    code = models.SlugField(max_length=50, unique=True,
                            help_text="Stable identifier, e.g. 'default', 'farmer', 'distributor', 'admin'.",)
    label = models.CharField(max_length=100, help_text="Human-readable label, e.g. 'Farmer View'.",)
    description = models.TextField(blank=True, help_text="Optional description for this view/mode.",)
    is_default = models.BooleanField(default=False,
                                     help_text="If true, this is the fallback mode when none is explicitly chosen.",)

    class Meta:
        db_table = "dashboard_view_modes"

    def __str__(self):
        return self.label

    def clean(self):
        # Only one default mode allowed
        if self.is_default:
            qs = DashboardViewMode.objects.filter(is_default=True).exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_default": "Only one dashboard view mode can be default."})

    def save(self, *args, **kwargs):
        self.full_clean()  # ensures clean() runs
        super().save(*args, **kwargs)

class DashboardChart(BaseModel):
    """
    One chart/widget that can be placed onto the dashboard in one or more modes.
    """
    PAGE_CHOICES = [
        ("landing", "Dashboard landing page"),
        ("risk", "Risk charts page"),
    ]

    identifier = models.SlugField(max_length=100, unique=True,
                                  help_text="Stable key, e.g. 'climate_map', 'disease_risk_timeseries'.",)
    label = models.CharField(max_length=200, help_text="Name shown in admin, e.g. 'Climate Map (Europe)'.",)
    template_name = models.CharField(max_length=255,
                                     help_text="Django template to include for this chart, e.g. 'lumenix/charts/climate_map.html'.",)
    page_code = models.CharField(max_length=20, choices=PAGE_CHOICES, default="landing",
                                 help_text="Which high-level page this chart belongs to.",)

    # Open-ended “how”: layout, default filters, chart options, etc.
    default_config = models.JSONField(default=dict, blank=True,
                                      help_text="Optional default config (layout, filters, options...) for this chart.",)

    class Meta:
        db_table = "dashboard_charts"

    def __str__(self):
        return self.label


class DashboardViewChart(BaseModel):
    """
    Through model: which charts appear in which mode, with ordering and per-mode config overrides.
    """
    mode = models.ForeignKey(DashboardViewMode, on_delete=models.CASCADE, related_name="view_charts",)
    chart = models.ForeignKey(DashboardChart, on_delete=models.CASCADE, related_name="view_modes",)
    order = models.PositiveIntegerField(default=0, help_text="Ordering of charts within a mode.",)

    config_override = models.JSONField(default=dict, blank=True,
                                       help_text="Optional per-mode override of chart config (the 'how').",)

    class Meta:
        db_table = "dashboard_view_charts"
        ordering = ["order"]
        unique_together = [("mode", "chart")]

    def __str__(self):
        return f"{self.mode} → {self.chart} (#{self.order})"

    @property
    def effective_config(self) -> dict:
        """
        Merge default_config from the chart with any overrides defined here.
        """
        base = dict(self.chart.default_config or {})
        base.update(self.config_override or {})
        return base


class SidebarChartLink(BaseModel):
    """
    Configures dynamic sidebar menus and chart submenus.
    """

    menu_code = models.SlugField(
        max_length=50,
        default="charts",
        help_text="Stable menu code, e.g. 'charts', 'exposure', 'alerts'.",
    )
    menu_label = models.CharField(
        max_length=100,
        default="Charts",
        help_text="Top-level menu label shown in sidebar, e.g. 'Charts'.",
    )
    menu_icon = models.CharField(
        max_length=40,
        blank=True,
        default="grid",
        help_text="Feather icon name for this menu, e.g. 'grid', 'bar-chart-2'.",
    )
    chart = models.ForeignKey(
        DashboardChart,
        on_delete=models.CASCADE,
        related_name="sidebar_links",
        help_text="Chart target for this sidebar entry.",
    )
    label_override = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional submenu label. If blank, chart label is used.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Order of submenu items within the same top-level menu.",
    )

    class Meta:
        db_table = "sidebar_chart_links"
        ordering = ["menu_code", "order", "id"]
        unique_together = [("menu_code", "chart")]
        verbose_name = "Sidebar Chart"
        verbose_name_plural = "Sidebar Charts"

    def __str__(self):
        return f"{self.menu_label} -> {self.display_label}"

    @property
    def display_label(self) -> str:
        return self.label_override or self.chart.label

    def clean(self):
        reserved = {"dashboard", "ipcc-dashboard", "risk-charts"}
        if (self.menu_code or "").strip().lower() in reserved:
            raise ValidationError({"menu_code": "This menu code is reserved by built-in sidebar menus."})

# models.py

import hashlib
import json

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


class CropMaster(BaseModel):
    ontology_id = models.CharField(max_length=10, unique=True, verbose_name="Ontology ID",
                                   validators=[RegexValidator(
                                       regex=r"^CO_\d{3}$",
                                       message="Ontology ID must be in the format 'CO_XXX' where XXX is a 3-digit number.",
                                       code="invalid_ontology_id"
                                   )
                                   ])
    crop_name = models.CharField(max_length=255, verbose_name="Crop Name",
                                 validators=[
                                     RegexValidator(
                                         regex=r"^[A-Za-z\s\-]+$",
                                         message="Crop name must only contain letters, spaces, and hyphens.",
                                         code="invalid_crop_name"
                                     )
                                 ])
    agrovoc_uri = models.URLField(null=True, blank=True, unique=True, verbose_name="AGROVOC URI")
    agrovoc_notation = models.CharField(
        max_length=32, null=True, blank=True, unique=True,
        help_text="AGROVOC local ID like c_12151"
    )

    class Meta:
        db_table = "crop_master"
        verbose_name = "Crop Master"
        verbose_name_plural = "Crops Master"

    def clean(self):
        self.crop_name = self.crop_name.strip().title()  # Capitalize first letter
        if CropMaster.objects.filter(crop_name__iexact=self.crop_name).exclude(id=self.id).exists():
            raise ValidationError({"crop_name": "A crop with this name already exists."})

    def __str__(self):
        return f"{self.crop_name} ({self.ontology_id})"


class ClimateData(BaseModel):
    timestamp = models.DateTimeField(verbose_name="Timestamp")
    # latitude = models.FloatField(
    #     verbose_name="Latitude",
    #     validators=[MinValueValidator(-90), MaxValueValidator(90)]
    # )
    # longitude = models.FloatField(
    #     verbose_name="Longitude",
    #     validators=[MinValueValidator(-180), MaxValueValidator(180)]
    # )
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

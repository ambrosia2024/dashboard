from django.contrib.gis.db import models as gis_models
from django.contrib.gis.db.models import Index as GISIndex
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
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


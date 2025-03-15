from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
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

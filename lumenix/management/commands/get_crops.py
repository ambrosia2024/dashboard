import requests
from django.core.management.base import BaseCommand
from lumenix.models import CropMaster

BASE_URL = "https://cropontology.org"

class Command(BaseCommand):
    help = "Fetch crops from Crop Ontology and insert into the database, avoiding duplicates."

    def handle(self, *args, **kwargs):
        """Fetch, check for duplicates, and insert crops into the database."""
        url = f"{BASE_URL}/ontos_stats"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch crops: {e}"))
            return  # Gracefully exit instead of crashing

        data = response.json()
        crops = data.get("summary per crop", [])

        if crops:
            self.stdout.write(self.style.SUCCESS("Processing crops..."))

            for crop in crops:
                ontology_id = crop["Ontology ID"]
                crop_name = crop["Ontology name"].strip().title()  # Standardize name

                # Check if the crop already exists
                if not CropMaster.objects.filter(ontology_id=ontology_id).exists():
                    CropMaster.objects.create(ontology_id=ontology_id, crop_name=crop_name)
                    self.stdout.write(self.style.SUCCESS(f"Inserted: {crop_name} ({ontology_id})"))
                else:
                    self.stdout.write(self.style.WARNING(f"Already exists: {crop_name} ({ontology_id})"))

        else:
            self.stdout.write(self.style.WARNING("No crops found."))

import os
import requests

from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter

from lumenix.models import CropMaster
from urllib3.util import Retry

load_dotenv()

BASE_URL = "https://cropontology.org"
CONNECT_TIMEOUT = float(os.getenv("CROP_ONTO_CONNECT_TIMEOUT", "5"))
READ_TIMEOUT = float(os.getenv("CROP_ONTO_READ_TIMEOUT", "45"))

def make_session() -> requests.Session:
    """
    Create a requests session with sensible retries and backoff.
    Retries only on idempotent GETs and common transient errors.
    """
    s = requests.Session()
    retry = Retry(
        total=5,                    # up to 5 attempts
        backoff_factor=1.5,         # 0, 1.5, 3, 4.5, 6...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"GET"},    # retry only GETs
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({
        # Some endpoints throttle/behave differently without UA
        "User-Agent": "lumenix/1.0 (+https://example.org) requests"
    })
    return s

class Command(BaseCommand):
    help = "Fetch crops from Crop Ontology and insert into the database, avoiding duplicates."

    def handle(self, *args, **kwargs):
        """Fetch, check for duplicates, and insert crops into the database."""

        session = make_session()
        url = f"{BASE_URL}/ontos_stats"
        try:
            # Use separate connect/read timeouts: tolerate slow body
            response = session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch crops: {e}"))
            return  # Gracefully exit instead of crashing

        try:
            data = response.json()
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f"Invalid JSON from {url}: {e}"))
            return

        crops = data.get("summary per crop", []) or []

        if crops:
            self.stdout.write(self.style.SUCCESS(f"Processing {len(crops)} crops..."))

            for crop in crops:
                ontology_id = (crop.get("Ontology ID") or "").strip()
                ontology_name_raw = (crop.get("Ontology name") or "").strip()
                if not ontology_id or not ontology_name_raw:
                    self.stdout.write(self.style.WARNING(f"Skipping malformed row: {crop!r}"))
                    continue
                crop_name = ontology_name_raw.title()

                # Check if the crop already exists
                obj, created = CropMaster.objects.get_or_create(
                    ontology_id=ontology_id,
                    defaults={"crop_name": crop_name},
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Inserted: {obj.crop_name} ({obj.ontology_id})"))
                else:
                    self.stdout.write(self.style.WARNING(f"Already exists: {obj.crop_name} ({obj.ontology_id})"))

        else:
            self.stdout.write(self.style.WARNING("No crops found."))

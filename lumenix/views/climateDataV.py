from django.http import JsonResponse
from django.views import View
from lumenix.models import ClimateData
from django.db.models import Q

import math  # Needed for NaN checks

class ClimateDataGeoJSONView(View):
    """Returns climate data in GeoJSON format filtered for Europe, ensuring valid coordinates."""

    def get(self, request, *args, **kwargs):
        # Define the bounding box for Europe (approx.)
        min_lat, max_lat = 35, 71   # From southern Spain to northern Scandinavia
        min_lon, max_lon = -25, 45  # From Portugal to Western Russia

        # Fetch valid climate data, filtering out invalid values
        climate_data = ClimateData.objects.filter(
            latitude__gte=min_lat, latitude__lte=max_lat,
            longitude__gte=min_lon, longitude__lte=max_lon,
        ).exclude(
            Q(latitude__isnull=True) | Q(longitude__isnull=True) |
            Q(latitude=float("inf")) | Q(longitude=float("inf")) |
            Q(latitude=float("-inf")) | Q(longitude=float("-inf"))
        ).order_by("-timestamp")[:5000]  # Limit results for performance

        # Convert to GeoJSON format
        features = []
        for data in climate_data:
            if data.longitude is None or data.latitude is None:
                continue  # Skip invalid points

            # Ensure coordinates are finite numbers
            if math.isnan(data.longitude) or math.isnan(data.latitude):
                continue

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(data.longitude), float(data.latitude)],
                },
                "properties": {
                    "timestamp": data.timestamp.isoformat(),
                    "temperature": data.temperature,
                }
            })

        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }

        return JsonResponse(geojson_data, safe=False)

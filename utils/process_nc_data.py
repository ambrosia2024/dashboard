import os
import xarray as xr
import pandas as pd

from django.contrib.gis.geos import Point
from django.db import transaction

from concurrent.futures import ThreadPoolExecutor

from lumenix.models import ClimateData


def insert_records(records):
    """Insert records into the database using Django's ORM in a thread-safe way."""
    if records:
        with transaction.atomic():  # Ensures data integrity
            ClimateData.objects.bulk_create(records, ignore_conflicts=True)
        print(f"✅ Inserted {len(records)} records...")


def process_netCDF():
    """Reads NetCDF and saves climate data into the Django database efficiently."""

    # File path for NetCDF data
    nc_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/era5_temp_latest.nc"))

    # Check file existence
    if not os.path.exists(nc_file):
        print(f"❌ ERROR: NetCDF file not found at {nc_file}")
        return

    print(f"Processing NetCDF file: {nc_file}")

    try:
        ds = xr.open_dataset(nc_file)
    except Exception as e:
        print(f"❌ ERROR: Failed to open NetCDF file. {e}")
        return

    # Extract variables
    try:
        print("Available variables in dataset:", list(ds.keys()))

        if "valid_time" in ds:
            time_var = "valid_time"
        elif "time" in ds:
            time_var = "time"
        else:
            raise KeyError("No valid time variable found. Expected 'valid_time' or 'time'.")

        time = ds[time_var].values  # Read correct time variable
        lat = ds["latitude"].values
        lon = ds["longitude"].values

        # Extract temperature variables (Convert Kelvin to Celsius)
        temp_2m = ds["t2m"].values - 273.15
        sst = ds["sst"].values - 273.15 if "sst" in ds else None
        temp_2m_max = ds["t2m_max"].values - 273.15 if "t2m_max" in ds else None
        temp_2m_min = ds["t2m_min"].values - 273.15 if "t2m_min" in ds else None
        skin_temp = ds["skin_temp"].values - 273.15 if "skin_temp" in ds else None
    except KeyError as e:
        print(f"❌ ERROR: Missing expected variable in NetCDF file: {e}")
        return

    records = []
    batch_size = 5000
    count = 0
    max_threads = 4

    with ThreadPoolExecutor(max_threads) as executor:
        futures = []

        for i, t in enumerate(time):
            for j, latitude in enumerate(lat):
                for k, longitude in enumerate(lon):
                    count += 1

                    # Create ClimateData instance with multiple temperature fields
                    record = ClimateData(
                        timestamp=pd.to_datetime(t),
                        location=Point(float(longitude), float(latitude)),  # (x=lon, y=lat)
                        temperature_2m=round(float(temp_2m[i][j][k]), 2),
                        sea_surface_temperature=round(float(sst[i][j][k]), 2) if sst is not None else None,
                        max_temperature_2m=round(float(temp_2m_max[i][j][k]), 2) if temp_2m_max is not None else None,
                        min_temperature_2m=round(float(temp_2m_min[i][j][k]), 2) if temp_2m_min is not None else None,
                        skin_temperature=round(float(skin_temp[i][j][k]), 2) if skin_temp is not None else None,
                    )
                    records.append(record)

                    # Process batch
                    if len(records) >= batch_size:
                        future = executor.submit(insert_records, records[:])
                        futures.append(future)
                        records = []

        # Final batch insert
        if records:
            future = executor.submit(insert_records, records[:])
            futures.append(future)

        # Wait for all threads to complete
        for future in futures:
            future.result()

    print(f"✅ Climate data processing completed. Total records processed: {count}")


if __name__ == "__main__":
    process_netCDF()

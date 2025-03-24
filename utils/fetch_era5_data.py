import cdsapi
import os

def download_era5_data():
    """Downloads ERA5 temperature data for the last 10 years (2015-2024) at 12:00 PM daily."""
    c = cdsapi.Client()

    years = [str(y) for y in range(2015, 2025)]  # Last 10 years
    months = [f"{m:02d}" for m in range(1, 13)]  # 01 to 12
    days = [f"{d:02d}" for d in range(1, 32)]  # 01 to 31

    print(f"Fetching ERA5 temperature data for {years} at 12:00 PM...")

    save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/era5_temp_2015_2024.nc"))
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    result = c.retrieve(
        "reanalysis-era5-single-levels",
        {
            "variable": [
                "2m_temperature",
                "sea_surface_temperature",
                "maximum_2m_temperature_since_previous_post_processing",
                "minimum_2m_temperature_since_previous_post_processing",
                "skin_temperature"
            ],
            "product_type": "reanalysis",
            "year": years,
            "month": months,
            "day": days,
            "time": ["12:00"],  # Only one time per day to reduce data size
            "format": "netcdf",
            "area": [72, -25, 30, 45]  # Europe
        },
        save_path
    )

    if result is not None:
        print("✅ Data request successful.")
    else:
        print("❌ ERROR: Failed to retrieve data from Copernicus API.")
        return

    if os.path.exists(save_path):
        print(f"✅ Download complete: {save_path}")
    else:
        print("❌ ERROR: Downloaded file not found!")

if __name__ == "__main__":
    download_era5_data()

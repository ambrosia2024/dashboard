from django.core.management.base import BaseCommand
from utils.fetch_era5_data import download_era5_data
from utils.process_nc_data import process_netCDF

class Command(BaseCommand):
    help = "Fetch and process ERA5 climate data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Fetching latest climate data...")
        download_era5_data()
        self.stdout.write("Processing NetCDF data...")
        process_netCDF()
        self.stdout.write(self.style.SUCCESS("Climate data updated successfully!"))

import time
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from fskx.risk_ml_models import SimpleKosekiMLModel


def simple_interpolate(key_years, risk_indexes, full_years=30):
    """simple interpolation, just to avoid adding more deps right now"""
    # Initialize an empty list to store the interpolated risk indexes
    interpolated_risks = []

    # Loop through each year from 0 to full_years (e.g., 0 to 30)
    for year in range(full_years + 1):
        # Find the two closest key years for interpolation
        for i in range(len(key_years) - 1):
            if year >= key_years[i] and year <= key_years[i + 1]:
                # Linear interpolation formula
                x0, x1 = key_years[i], key_years[i + 1]
                y0, y1 = risk_indexes[i], risk_indexes[i + 1]
                # Calculate the interpolated risk index
                interpolated_risk = y0 + (y1 - y0) * (year - x0) / (x1 - x0)
                interpolated_risks.append(interpolated_risk)
                break

    return interpolated_risks

class Command(BaseCommand):
    help = "Runs the FSKX model and retrieves the JSON with risk indexes by temperature changes (interpolated with pure Python)"

    def handle(self, *args, **kwargs):
        annual_increase = 0.5
        years = 30

        # Run simulations for years 0, 10, 20, 30
        key_years = [0, 10, 20, 30]
        temperature_anomalies = [y * annual_increase for y in key_years]
        full_temperature_anomalies = [y * annual_increase for y in range(years + 1)]
        initial_temperature = 10.68

        model = SimpleKosekiMLModel()
        model.default_params['temp_celsius'] = initial_temperature

        # Run simulations
        # sims = model.run_risk_by_temp_changes_batch(temperature_anomalies)
        # sims = {0: {'simulation_id': 'b539e073-b436-4c9f-a0be-df657bf61cf1', 'temp_change': 0.0, 'temperature': 10.68}, 1: {'simulation_id': '4a6aace1-4b3b-412c-a87c-21f4991cabe0', 'temp_change': 0.5, 'temperature': 11.18}, 2: {'simulation_id': '2e29c4e7-35b8-4335-b5e5-ef7e9eea9295', 'temp_change': 1.0, 'temperature': 11.68}, 3: {'simulation_id': 'fb19b6f0-4404-471a-a35d-45f643b4d440', 'temp_change': 1.5, 'temperature': 12.18}}
        sims = {0: {'simulation_id': '9b273091-9250-46d9-9f03-0088fd5d42b7', 'temp_change': 0.0, 'temperature': 10.68}, 1: {'simulation_id': 'fc18c5a6-fe49-41cb-ac41-8bd153ce373c', 'temp_change': 5.0, 'temperature': 15.68}, 2: {'simulation_id': '98894fed-2755-42a9-af5f-ec98cb3817bf', 'temp_change': 10.0, 'temperature': 20.68}, 3: {'simulation_id': '3136ae1b-24df-441d-81f4-225672c32397', 'temp_change': 15.0, 'temperature': 25.68}}
        self.stdout.write(self.style.SUCCESS(f'Simulations running... {sims}'))

        while True:
            # Check status and retrieve results
            if model.check_status_batch(sims):
            # if True:
                self.stdout.write(self.style.SUCCESS('Sim results ready..'))
                results = model.get_risk_by_temp_changes_batch(sims)
                if results:
                    self.stdout.write(self.style.SUCCESS('Sim results retrieved, performing interpolation...'))

                    # Extract risk index values
                    temp_changes = results['temp_changes']  # Extracted temp changes (should match key_years)
                    risk_indexes = results['risk']  # Extracted risk values

                    # Interpolate missing years
                    interpolated_risks = simple_interpolate(key_years, risk_indexes, full_years=years)
                    final_results = {
                        'temp_changes':full_temperature_anomalies,  # All years from 0 to 30
                        'risk': interpolated_risks,
                    }

                    # Save to file
                    file_path = settings.FSKX_SETTINGS['TESTING_JSON_RISK_PATH']
                    with open(file_path, 'w') as f:
                        json.dump(final_results, f, indent=4)

                    self.stdout.write(self.style.SUCCESS(f'Risk index simulation results saved to {file_path}'))
                    break
            else:
                self.stdout.write(self.style.WARNING('Results not ready, try again later.'))
                time.sleep(10)

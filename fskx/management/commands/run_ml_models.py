import time
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from fskx.risk_ml_models import SimpleKosekiMLModel


def simple_interpolate(x_known, y_known, x_full):
    """
    Linearly interpolates y-values for a full set of x-values using known (x, y) pairs.
    Also performs simple linear extrapolation for x-values beyond the last known point.
    """
    interpolated_y = []

    for x in x_full:
        # Loop through known x intervals to find the right range for interpolation
        for i in range(len(x_known) - 1):
            if x_known[i] <= x <= x_known[i + 1]:
                # Perform linear interpolation between two known points
                x0, x1 = x_known[i], x_known[i + 1]
                y0, y1 = y_known[i], y_known[i + 1]
                y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                interpolated_y.append(y)
                break
        else:
            # If x exactly matches the last known point, just use the last y
            if x == x_known[-1]:
                interpolated_y.append(y_known[-1])

            # If x is beyond the last known x (i.e., extrapolation), estimate by continuing the slope
            elif x > x_known[-1]:
                # Take the last segment (last two known points) to compute the slope
                x0, x1 = x_known[-2], x_known[-1]
                y0, y1 = y_known[-2], y_known[-1]
                y = y1 + (y1 - y0) / (x1 - x0) * (x - x1)
                interpolated_y.append(y)

    return interpolated_y


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
        self.stdout.write(self.style.SUCCESS('Running simulations...'))
        sims = model.run_risk_by_temp_changes_batch(temperature_anomalies)
        self.stdout.write(self.style.SUCCESS(f'Simulations started: {sims}'))
        # sims = {0: {'simulation_id': 'b539e073-b436-4c9f-a0be-df657bf61cf1', 'temp_change': 0.0, 'temperature': 10.68}, 1: {'simulation_id': '4a6aace1-4b3b-412c-a87c-21f4991cabe0', 'temp_change': 0.5, 'temperature': 11.18}, 2: {'simulation_id': '2e29c4e7-35b8-4335-b5e5-ef7e9eea9295', 'temp_change': 1.0, 'temperature': 11.68}, 3: {'simulation_id': 'fb19b6f0-4404-471a-a35d-45f643b4d440', 'temp_change': 1.5, 'temperature': 12.18}}
        # sims = {0: {'simulation_id': '9b273091-9250-46d9-9f03-0088fd5d42b7', 'temp_change': 0.0, 'temperature': 10.68}, 1: {'simulation_id': 'fc18c5a6-fe49-41cb-ac41-8bd153ce373c', 'temp_change': 5.0, 'temperature': 15.68}, 2: {'simulation_id': '98894fed-2755-42a9-af5f-ec98cb3817bf', 'temp_change': 10.0, 'temperature': 20.68}, 3: {'simulation_id': '3136ae1b-24df-441d-81f4-225672c32397', 'temp_change': 15.0, 'temperature': 25.68}}
        # self.stdout.write(self.style.SUCCESS(f'Simulations running... {sims}'))

        max_attempts = 30
        for attempt in range(max_attempts):
            if model.check_status_batch(sims):
                self.stdout.write(self.style.SUCCESS('Simulation results are ready.'))
                results = model.get_risk_by_temp_changes_batch(sims)
                if results and 'temp_changes' in results and 'risk' in results:
                    temp_changes = results['temp_changes']
                    risk_indexes = results['risk']

                    if len(temp_changes) != len(risk_indexes):
                        self.stdout.write(self.style.ERROR('Mismatch in temp_changes and risk length. Aborting.'))
                        return

                    # interpolated_risks = simple_interpolate(key_years, risk_indexes, full_years=years)
                    interpolated_risks = simple_interpolate(
                        temperature_anomalies,
                        risk_indexes,
                        full_temperature_anomalies
                    )

                    final_results = {
                        'initial_temperature': initial_temperature,
                        'temp_changes': full_temperature_anomalies,
                        'risk': interpolated_risks,
                    }

                    try:
                        file_path = settings.FSKX_SETTINGS['TESTING_JSON_RISK_PATH']
                        with open(file_path, 'w') as f:
                            json.dump(final_results, f, indent=4)
                        self.stdout.write(self.style.SUCCESS(f'Risk index simulation results saved to {file_path}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Failed to save file: {e}'))
                    return
                else:
                    self.stdout.write(self.style.ERROR('Empty or malformed simulation results.'))
                    return
            else:
                self.stdout.write(
                    self.style.WARNING(f'Attempt {attempt + 1}/{max_attempts}: Results not ready. Retrying...'))
                time.sleep(10)

        self.stdout.write(self.style.ERROR('Timed out waiting for simulation results.'))

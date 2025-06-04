import time

from django.conf import settings

from .client import FSKXOAuth2Client


class BaseRiskMLModel():
    def __init__(self):
        self.client = FSKXOAuth2Client()
        self.model_id = None
        self.default_params = {}

    def run_background(self, **kwargs):
        """
        Run the risk model in the background.
        """
        raise NotImplementedError("run_background method not implemented")

    def get_result_sim(self, simulation_id):
        """
        Get the result of the simulation.
        """
        raise NotImplementedError("get_result method not implemented")



class SimpleKosekiMLModel(BaseRiskMLModel):
    def __init__(self):
        super().__init__()
        self.model_id = settings.FSKX_SETTINGS['MODELS']['FSKX_SIMPLE_KOSEKI_ID']
        self.default_params = {
            "temp_celsius": 10,
            "y0": 4,
            "b": 0.033,
            "Tmin": 4.96,
            "alpha0": 0.097,
            "tmax": 72
        }

    def run_background_sim(self, **kwargs):
        params = self.default_params.copy()
        params.update(kwargs)
        simulation_data = self.client.run_simulation(
            self.model_id,
            params=params
        )
        simulation_id = simulation_data.get('simulation_id')
        if simulation_id:
            return simulation_id
        else:
            raise Exception("Failed to start simulation")

    def growth_perc_to_risk_index(self, growth_perc, min_growth=0, max_growth=200):
        """
        Convert growth percentage to risk index.
        The risk index is scaled between 0 and 1.
        Args:
            growth_perc: The growth percentage to convert.
            min_growth: The minimum growth percentage (maps to risk index 0).
            max_growth: The maximum growth percentage (maps to risk index 1).

        Returns:
            float: The risk index between 0 and 1.
        """
        if min_growth >= max_growth:
            raise ValueError("min_growth must be less than max_growth")

        # Normalize the growth percentage between 0 and 1
        normalized = (growth_perc - min_growth) / (max_growth - min_growth)

        # Clip the result to ensure it's between 0 and 1
        return min(max(normalized, 0), 1)

    def calculate_risk_index(self, model_output):
        """
        Calculate a risk index based on Salmonella growth predictions.

        Parameters:
        - model_output (dict): Koseki model output with "model_values".

        Returns:
        - float: Risk index (scaled between 0 and 1).
        """
        N_initial = 10**model_output["model_values"][0]  # Convert log CFU/g to CFU/g
        N_final = 10**model_output["model_values"][-1]

        growth = N_final - N_initial

        growth_perc = growth / N_initial

        risk_index = self.growth_perc_to_risk_index(growth_perc, min_growth=0, max_growth=200)
        return risk_index

    def get_result_sim(self, simulation_id):
        simulation_status = self.client.get_simulation_status(simulation_id)
        clean_result = None
        if simulation_status.get('status') == 'SUCCESS':
            params = self.client.get_simulation_params(simulation_id)
            simulation_res = self.client.get_simulation_result(simulation_id, file_type='json')
            risk_index = self.calculate_risk_index(simulation_res)
            clean_result = {
                'risk_index' : risk_index,
            }

        return clean_result

    def run_risk_by_temp_changes_batch(self, temp_changes):
        """
        Run a batch of simulations with different temperature changes and get the risk index.
        """
        sims = {}
        for index, temp_change in enumerate(temp_changes):
            new_temp = self.default_params['temp_celsius'] + temp_change
            sim_id = self.run_background_sim(temp_celsius=new_temp)
            sims[index]= {
                'simulation_id': sim_id,
                'temp_change': temp_change,
                'temperature': new_temp,
            }
            time.sleep(5) # hardcoded wait time to avoid overloading the server
        return sims

    def check_status_batch(self, sims):
        """
        Check the status of a batch of simulations.
        """
        status = True
        for sim_index, values in sims.items():
            sim_id = values['simulation_id']
            simulation_status = self.client.get_simulation_status(sim_id)
            if simulation_status.get('status') != 'SUCCESS':
                status = False
                break
        return status

    def get_risk_by_temp_changes_batch(self, sims):
        """
        Get the risk index for a batch of simulations.
        """
        # Maybe redundant
        if not self.check_status_batch(sims):
            return None

        temp_changes = []
        risk = []
        for sim_index, sim_values in sims.items():
            sim_id = sim_values['simulation_id']
            temp_change = sim_values['temp_change']
            result = self.get_result_sim(sim_id)
            if result and 'risk_index' in result:
                risk.append(result['risk_index'])
                temp_changes.append(temp_change)
            else:
                raise Exception(f"Missing result for simulation ID: {sim_id}")

        return {
            'temp_changes': temp_changes,
            'risk': risk
        }

#!/usr/bin/env python

from urllib.parse import urlencode, urljoin
from oauthlib.oauth2 import LegacyApplicationClient
from requests_oauthlib import OAuth2Session
from django.conf import settings
import json


class FixedLegacyClient(LegacyApplicationClient):
    def parse_request_body_response(self, body, scope=None):
        """Quick fix: Remove null error before processing"""
        try:
            # Parse the JSON and remove null error if exists
            data = json.loads(body)
            if 'error' in data and data['error'] is None:
                del data['error']
                body = json.dumps(data)

            return super().parse_request_body_response(body, scope)
        except json.JSONDecodeError:
            return super().parse_request_body_response(body, scope)


class FSKXOAuth2Client:
    def __init__(self):
        self.base_url = settings.FSKX_SETTINGS['API']['BASE_URL']
        self.AUTH_URL = urljoin(
            self.base_url,
            settings.FSKX_SETTINGS['API']['AUTH_ENDPOINT']
        )
        self.REFRESH_URL = urljoin(
            self.base_url,
            settings.FSKX_SETTINGS['API']['REFRESH_ENDPOINT']
        )

        self.FSKX_USERNAME = settings.FSKX_SETTINGS['CREDENTIALS']['USERNAME']
        self.FSKX_PASSWORD = settings.FSKX_SETTINGS['CREDENTIALS']['PASSWORD']

        self.client = OAuth2Session(
            client=FixedLegacyClient(client_id=None),
            auto_refresh_url=self.REFRESH_URL,
            token_updater=self._save_token
        )
        self.token = None

    def run_simulation(self, model_id, **params):
        url = urljoin(
            self.base_url,
            settings.FSKX_SETTINGS['API']['RUN_SIMULATION_ENDPOINT']
        )

        query_params = {
            "model_id": model_id,
            "plot_type": "png"
        }
        if params:
            query_params.update({
                "parameters": json.dumps(params)
            })

        full_url = f"{url}?{urlencode(query_params)}"
        try:
            response = self.post(full_url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Simulation failed: {str(e)}")
            raise e

    def get_simulation_status(self, simulation_id):
        url = urljoin(
            self.base_url,
            settings.FSKX_SETTINGS['API']['GET_SIMULATION_ENDPOINT'].format(simulation_id=simulation_id)
        )
        try:
            response = self.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Simulation could not be retrieved: {str(e)}")
            raise e

    def get_simulation_result(self, simulation_id, file_type='json'):
        url = urljoin(
            self.base_url,
            settings.FSKX_SETTINGS['API']['GET_RESULTS_ENDPOINT']
        )
        query_params = {
            "simulation_id": simulation_id,
            "file_type": file_type,
        }
        full_url = f"{url}?{urlencode(query_params)}"
        try:
            response = self.get(full_url)
            response.raise_for_status()
            if file_type == 'json':
                return json.loads(response.json())
            else:
                return response
        except Exception as e:
            print(f"Simulation results could not be retrieved: {str(e)}")
            raise e

    def _save_token(self, token):
        self.token = token
        self.client.token = token

    def _ensure_token(self):
        if not self.token or not self.client.token:
            self.token = self.client.fetch_token(
                token_url=self.AUTH_URL,
                username=self.FSKX_USERNAME,
                password=self.FSKX_PASSWORD,
                include_client_id=True
            )
            self.client.token = self.token

    def request(self, method, url, **kwargs):
        self._ensure_token()
        return self.client.request(method, url, **kwargs)

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def check_auth(self):
        try:
            self._ensure_token()
            return True
        except Exception as e:
            print(f"Authentication failed: {str(e)}")
            raise e

if __name__ == "__main__":

    # adding a butch of hacky hack to setup django,
    # will change this to a actual manage subcommand once its
    # working
    import time
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    sys.path.append(str(project_root))
    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()


    client = FSKXOAuth2Client()
    try:
        if client.check_auth():
            print(" Successfully authenticated!")
            print(f"Access token: {client.token['access_token'][:50]}...")

            # simulation_data = client.run_simulation(settings.FSKX_SETTINGS['MODELS']['SIMPLE_QMRA_ID'])

            # if simulation_data is not None:
            #     print("Simulation Information:")
            #     print(json.dumps(simulation_data, indent=4))

            # for i in range(10):
            #     print('Will get simulation status...')
            #     simulation_id = '99f66458-078b-47ae-897b-b499b81153f5'
            #     simulation_res = client.get_simulation_status(simulation_id)

            #     if simulation_res is not None:
            #         print("Simulation Information:")
            #         print(json.dumps(simulation_res, indent=4))
            #         end_time = simulation_res.get('end_time')
            #         if end_time is not None and end_time != '':
            #             break
            #     time.sleep(10)

            print('Will get simulation result...')
            simulation_id = '99f66458-078b-47ae-897b-b499b81153f5'
            simulation_res = client.get_simulation_result(simulation_id)

            if simulation_res is not None:
                print("Simulation Result:")
                print(json.dumps(simulation_res, indent=4))


    except Exception as e:
        print(f" Error: {str(e)}")

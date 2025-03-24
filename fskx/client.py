#!/usr/bin/env python

from urllib.parse import urljoin
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

    def run_simulation(self, model_id):
        url = urljoin(
            self.base_url,
            settings.FSKX_SETTINGS['API']['RUN_SIMULATION_ENDPOINT']
        )
        # hardcoding payload for this model, just for now, to test the workflow
        payload = {
            "model_id": model_id,
            "plot_type": "png",
            "parameters": {
                "runs": 100,
                "meanTemp": 5.9,
                "sdTemp": 2.9,
                "Tmin": -1.18,
                "Input_prev": "prev_inputs3.csv",
                "Input_conc": "conc_inputs3.csv"
            }
        }
        try:
            response = self.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Simulation failed: {str(e)}")
            raise e


    # def get_model(self, model_id):
    #     url = urljoin(
    #         self.base_url,
    #         settings.FSKX_SETTINGS['API']['GET_MODEL_ENDPOINT']
    #     ).format(model_id=model_id)
    #     payload = {
    #         "model_id": model_id,
    #         "plot_type": "png",
    #         "parameters": {
    #             "additionalProp1": "string",
    #             "additionalProp2": "string",
    #             "additionalProp3": "string"
    #         }
    #     }
    #     self.get(url)

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

            response = client.run_simulation(settings.FSKX_SETTINGS['MODELS']['SIMPLE_QMRA_ID'])

            if response.status_code == 200:
                print("\Simulation Information:")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f" Failed to run simulation (Status {response.status_code}): {response.text}")

    except Exception as e:
        print(f" Error: {str(e)}")

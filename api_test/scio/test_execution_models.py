# api_test/scio/test_execution_models.py

import requests
import os
from dotenv import load_dotenv
from utils import print_model_info

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL")
ENDPOINT = os.getenv("GET_EXECUTION_MODELS_ENDPOINT")

def main():
    url = BASE_URL + ENDPOINT
    print(f"Testing: {url}")

    response = None

    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Raw Response: {response.text}")

        response.raise_for_status()
        if not response.text.strip():
            print("No content returned (empty string). Possibly unconfigured or stubbed.")
            return

        data = response.json()

        if isinstance(data, list):
            print_model_info(data, "Model Execution Service Models")
        else:
            print("Unexpected response format (not a list):")
            print(data)

    except requests.JSONDecodeError:
        print("Response was not valid JSON.")
        print(response.text)
    except requests.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    main()

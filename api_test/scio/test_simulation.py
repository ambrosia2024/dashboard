# api_test/scio/test_simulation.py

import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL")
SIMULATION_ENDPOINT = os.getenv("SIMULATION_ENDPOINT")

def main():
    url = BASE_URL + SIMULATION_ENDPOINT
    print(f"Testing: {url}")

    response = None

    try:
        response = requests.post(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Raw Response: {response.text}")

        response.raise_for_status()
        if not response.text.strip():
            print("No content returned (empty string). Possibly unconfigured or stubbed.")
            return

        data = response.json()

        print("\nParsed JSON Response:")
        print(json.dumps(data, indent=2))

    except requests.JSONDecodeError:
        print("Response was not valid JSON.")
        if response:
            print(response.text)
    except requests.RequestException as e:
        print(f"POST request failed: {e}")

if __name__ == "__main__":
    main()

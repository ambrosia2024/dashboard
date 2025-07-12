# api_test/scio/test_models.py

import argparse
import os
import requests

from dotenv import load_dotenv
from utils import print_model_info

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL")
ENDPOINT = os.getenv("GET_MODELS_ENDPOINT")

def filter_models(models, name_filter=None, max_ram=None, gpu_only=False):
    filtered = []
    for model in models:
        if name_filter and name_filter.lower() not in model.get("name", "").lower():
            continue
        if gpu_only and model.get("gpu_count_required", 0) == 0:
            continue
        if max_ram is not None and model.get("ram_gb_required", 0) > max_ram:
            continue
        filtered.append(model)
    return filtered

def main():
    parser = argparse.ArgumentParser(description="Filter Ambrosia models.")
    parser.add_argument("--name", help="Filter by name substring (case-insensitive)")
    parser.add_argument("--max-ram", type=float, help="Max RAM (in GB)")
    parser.add_argument("--gpu", action="store_true", help="Only show GPU-based models")
    args = parser.parse_args()

    url = BASE_URL + ENDPOINT
    print(f"Testing: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and 'models' in data:
            models = filter_models(data['models'], args.name, args.max_ram, args.gpu)
            print_model_info(models, "Filtered Ambrosia Models")
        else:
            print("Unexpected response format:")
            print(data)

    except requests.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    main()

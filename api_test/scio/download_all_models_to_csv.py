# api_test/scio/download_all_models_to_csv.py

import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")
ENDPOINT = os.getenv("GET_MODELS_ENDPOINT", "").lstrip("/")

def fetch_all_models() -> list[dict]:
    """
    Fetch models from the API
    """
    url = f"{BASE_URL}/{ENDPOINT}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and "models" in data:
        models = data["models"]
    elif isinstance(data, list):
        models = data
    else:
        raise ValueError(f"Unexpected response schema: {type(data)}")

    return models

def main():
    models = fetch_all_models()

    df = pd.DataFrame(models)

    print(df.head().to_string(index=False))

    # Save full dataframe as CSV with timestamp in filename
    out_file = "all_models.csv"
    df.to_csv(out_file, index=False, encoding="utf-8")
    print(f"\nSaved all models to: {out_file}")

if __name__ == "__main__":
    main()

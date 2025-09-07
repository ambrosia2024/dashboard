# pidrive/config.py

import os
from dotenv import load_dotenv

load_dotenv()

PI_USER       = os.getenv("PI_USER")
PI_PASSWORD   = os.getenv("PI_PASSWORD")
PI_REMOTE_DIR = os.getenv("PI_REMOTE_DIR")
NGROK_API_KEY = os.getenv("NGROK_API_KEY")

def check_required():
    missing = [k for k, v in {
        "PI_USER": PI_USER,
        "PI_PASSWORD": PI_PASSWORD,
        "PI_REMOTE_DIR": PI_REMOTE_DIR,
        "NGROK_API_KEY": NGROK_API_KEY,
    }.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

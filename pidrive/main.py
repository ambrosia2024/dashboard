# pidrive/main.py

from fastapi import FastAPI
from .routes import router

app = FastAPI(title="PiDrive API")
app.include_router(router)

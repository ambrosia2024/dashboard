# pidrive/main.py

from fastapi import FastAPI
from .routes import router

app = FastAPI(title="PiDrive API", docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")
app.include_router(router)

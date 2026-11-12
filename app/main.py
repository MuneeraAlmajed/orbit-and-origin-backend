from fastapi import FastAPI
from app.routes.mars import router as mars_router

app = FastAPI(title="Orbit & Origin API")

app.include_router(mars_router)

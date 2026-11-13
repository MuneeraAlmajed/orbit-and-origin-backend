
from fastapi import FastAPI

from app.routes.mars import router as mars_router
from app.routes.hazards import router as hazards_router
from app.routes.science_pois import router as science_pois_router
from app.routes.route_planning import router as route_planning_router

app = FastAPI(title="Orbit & Origin API")

app.include_router(mars_router)
app.include_router(hazards_router)
app.include_router(science_pois_router)
app.include_router(route_planning_router)

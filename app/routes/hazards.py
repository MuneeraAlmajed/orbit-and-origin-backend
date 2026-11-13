
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, HTTPException, Query

from app.data.mock_data import hazards


router = APIRouter(
    prefix="/api/v1/hazards",
    tags=["Hazards"]
)

MARS_RADIUS_KM = 3389.5


def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(
        radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    return 2 * MARS_RADIUS_KM * asin(min(1, sqrt(a)))


def format_hazard(hazard):
    recommendations = {
        "high": "Avoid this area when planning routes.",
        "medium": "Proceed with caution.",
        "low": "Monitor terrain conditions."
    }

    return {
        "id": hazard["id"],
        "name": hazard["name"],
        "type": hazard["type"],
        "severity": hazard["severity"],
        "description": hazard["description"],
        "location": {
            "lat": hazard["lat"],
            "lon": hazard["lon"]
        },
        "radius_km": hazard["radius"],
        "recommendation": recommendations.get(
            hazard["severity"], "Proceed with caution."
        )
    }


@router.get("")
def get_hazards(
    severity: str | None = None,
    type: str | None = None
):
    filtered = hazards

    if severity is not None:
        filtered = [
            hazard for hazard in filtered
            if hazard["severity"] == severity.lower()
        ]

    if type is not None:
        filtered = [
            hazard for hazard in filtered
            if hazard["type"] == type.lower()
        ]

    return {
        "total": len(filtered),
        "hazards": [format_hazard(h) for h in filtered],
        "data_source": "mock"
    }


@router.get("/nearby")
def get_nearby_hazards(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: float = Query(..., gt=0)
):
    nearby = []

    for hazard in hazards:
        distance = calculate_distance(
            lat, lon, hazard["lat"], hazard["lon"]
        )

        if distance <= radius:
            nearby.append({
                "id": hazard["id"],
                "name": hazard["name"],
                "type": hazard["type"],
                "severity": hazard["severity"],
                "location": {
                    "lat": hazard["lat"],
                    "lon": hazard["lon"]
                },
                "distance_km": round(distance, 2)
            })

    nearby.sort(key=lambda h: h["distance_km"])

    return {
        "search_location": {"lat": lat, "lon": lon},
        "search_radius_km": radius,
        "total": len(nearby),
        "hazards": nearby,
        "data_source": "mock"
    }


@router.get("/{hazard_id}")
def get_hazard_by_id(hazard_id: int):
    for hazard in hazards:
        if hazard["id"] == hazard_id:
            return {
                **format_hazard(hazard),
                "data_source": "mock"
            }

    raise HTTPException(
        status_code=404,
        detail="Hazard not found"
    )

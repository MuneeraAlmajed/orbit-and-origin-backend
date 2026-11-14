from typing import Optional
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, HTTPException, Query

from app.data.mock_data import hazards
from app.routes.mars import get_terrain_grid


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
    severity: Optional[str] = None,
   type: Optional[str] = None,
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
def group_adjacent_risks(risks):
    groups = []
    visited = set()

    for index, risk in enumerate(risks):
        if index in visited:
            continue

        group = [risk]
        visited.add(index)

        queue = [index]

        while queue:
            current_index = queue.pop(0)
            current_bounds = risks[current_index]["bounds"]

            current_south = current_bounds[0][0]
            current_west = current_bounds[0][1]
            current_north = current_bounds[1][0]
            current_east = current_bounds[1][1]

            for other_index, other in enumerate(risks):
                if other_index in visited:
                    continue

                other_bounds = other["bounds"]

                other_south = other_bounds[0][0]
                other_west = other_bounds[0][1]
                other_north = other_bounds[1][0]
                other_east = other_bounds[1][1]

                lat_touch = (
                    current_south <= other_north + 1e-9
                    and other_south <= current_north + 1e-9
                )

                lon_touch = (
                    current_west <= other_east + 1e-9
                    and other_west <= current_east + 1e-9
                )

                if lat_touch and lon_touch:
                    group.append(other)
                    visited.add(other_index)
                    queue.append(other_index)

        groups.append(group)

    merged = []

    for group in groups:
        representative = max(
            group,
            key=lambda risk: risk["slope_degrees"]
        )

        merged.append({
            **representative,
            "cell_count": len(group),
            "severity": (
                "high"
                if any(risk["severity"] == "high" for risk in group)
                else "medium"
            )
        })

    return merged


@router.get("/terrain-risk")
def get_terrain_risks():
    grid = get_terrain_grid()
    risks = []

    for index, cell in enumerate(grid["data"], start=1):
        slope = cell["slope"]

        if slope is None or slope < 5:
            continue

        if slope > 15:
            severity = "high"
            recommendation = "Avoid this steep area when planning routes."
        else:
            severity = "medium"
            recommendation = "Proceed with caution."

        south_west = cell["bounds"][0]
        north_east = cell["bounds"][1]

        risks.append({
            "id": index,
            "name": "Potential slope hazard",
            "type": "steep_slope",
            "severity": severity,
            "location": {
                "lat": (south_west[0] + north_east[0]) / 2,
                "lon": (south_west[1] + north_east[1]) / 2
            },
            "bounds": cell["bounds"],
            "elevation_m": cell["elevation"],
            "slope_degrees": slope,
            "recommendation": recommendation
        })

    grouped_risks = group_adjacent_risks(risks)

    return {
    "total": len(grouped_risks),
    "hazards": grouped_risks,
    "data_source": "Derived from USGS/NASA HiRISE DTM"
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

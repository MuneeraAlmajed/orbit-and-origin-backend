
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from math import radians, sin, cos, asin, sqrt
from itertools import count
from functools import lru_cache

from app.data.mock_data import routes
from app.routes.mars import get_terrain_grid
from app.routes.hazards import get_terrain_risks

router = APIRouter(prefix="/api/v1/routes", tags=["Route Planning & Safety"])

MARS_RADIUS = 3389.5
ROVER_SPEED = 4.0
TERRAIN_SOURCE = "USGS/NASA HiRISE DTM and derived slope risks"


saved_routes = {r["id"]: r.copy() for r in routes}
next_id = count(max(saved_routes, default=0) + 1)


class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteInput(BaseModel):
    start: Coordinate
    destination: Coordinate


class AnalysisInput(RouteInput):
    waypoints: list[Coordinate] = Field(min_length=2)


@lru_cache(maxsize=1)
def get_terrain_cells():
    return get_terrain_grid()["data"]


@lru_cache(maxsize=1)
def get_terrain_risk_data():
    return get_terrain_risks()["hazards"]


def distance(a, b):
    lat1, lon1 = radians(a["lat"]), radians(a["lon"])
    lat2, lon2 = radians(b["lat"]), radians(b["lon"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    value = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    return 2 * MARS_RADIUS * asin(min(1, sqrt(value)))


def total_distance(points):
    return round(
        sum(distance(a, b) for a, b in zip(points, points[1:])),
        2
    )


def interpolate(a, b, fraction):
    return {
        "lat": a["lat"] + (b["lat"] - a["lat"]) * fraction,
        "lon": a["lon"] + (b["lon"] - a["lon"]) * fraction,
    }


def get_nearest_terrain_cell(point, cells):
    nearest = None
    shortest_distance = float("inf")

    for cell in cells:
        south_west = cell["bounds"][0]
        north_east = cell["bounds"][1]

        center_lat = (south_west[0] + north_east[0]) / 2
        center_lon = (south_west[1] + north_east[1]) / 2

        current_distance = distance(
            point,
            {"lat": center_lat, "lon": center_lon}
        )

        if current_distance < shortest_distance:
            shortest_distance = current_distance
            nearest = cell

    if shortest_distance > 1.5:
        return None

    return nearest


def hazard_distance(point, a, b):
    scale_y = MARS_RADIUS * 3.141592653589793 / 180
    scale_x = scale_y * cos(radians(point["lat"]))

    ax, ay = a["lon"] * scale_x, a["lat"] * scale_y
    bx, by = b["lon"] * scale_x, b["lat"] * scale_y
    px, py = point["lon"] * scale_x, point["lat"] * scale_y

    dx, dy = bx - ax, by - ay
    denominator = dx * dx + dy * dy

    if denominator == 0:
        return sqrt((px - ax) ** 2 + (py - ay) ** 2)

    t = max(
        0,
        min(1, ((px - ax) * dx + (py - ay) * dy) / denominator)
    )

    return sqrt(
        (px - ax - t * dx) ** 2
        + (py - ay - t * dy) ** 2
    )


def find_hazards(points):
    detected = []
    detected_ids = set()
    terrain_risks = get_terrain_risk_data()

    for hazard in terrain_risks:
        location = hazard["location"]

        closest = min(
            hazard_distance(location, a, b)
            for a, b in zip(points, points[1:])
        )

        if closest <= 1.5 and hazard["id"] not in detected_ids:
            detected_ids.add(hazard["id"])
            detected.append({
                "id": hazard["id"],
                "name": hazard["name"],
                "type": hazard["type"],
                "severity": hazard["severity"],
                "location": location,
                "distance_from_route_km": round(closest, 2),
                "slope_degrees": hazard["slope_degrees"],
                "elevation_m": hazard["elevation_m"],
                "recommendation": hazard["recommendation"],
            })

    return detected


def get_terrain(points):
    cells = get_terrain_cells()
    segments = []

    for index, (a, b) in enumerate(zip(points, points[1:]), 1):
        first_cell = get_nearest_terrain_cell(a, cells)
        second_cell = get_nearest_terrain_cell(b, cells)

        if (
            first_cell is None
            or second_cell is None
            or first_cell["slope"] is None
            or second_cell["slope"] is None
            or first_cell["elevation"] is None
            or second_cell["elevation"] is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Terrain data is unavailable for this route."
            )

        slope = round(
            (first_cell["slope"] + second_cell["slope"]) / 2,
            2
        )

        elevation = round(
            (first_cell["elevation"] + second_cell["elevation"]) / 2,
            2
        )

        terrain_type = (
            "flat" if slope < 6
            else "rocky" if slope < 15
            else "uneven"
        )

        segments.append({
            "segment": index,
            "slope": slope,
            "elevation_m": elevation,
            "terrain_type": terrain_type,
        })

    average_slope = round(
        sum(s["slope"] for s in segments) / len(segments), 2
    )

    average_elevation = round(
        sum(s["elevation_m"] for s in segments) / len(segments), 2
    )

    maximum_slope = max(s["slope"] for s in segments)

    difficulty = (
        "easy" if maximum_slope < 6
        else "moderate" if maximum_slope < 15
        else "hard"
    )

    terrain_type = (
        "flat" if average_slope < 6
        else "rocky" if average_slope < 15
        else "uneven"
    )

    return {
        "terrain_summary": {
            "average_elevation": average_elevation,
            "maximum_slope": maximum_slope,
            "average_slope": average_slope,
            "terrain_type": terrain_type,
            "difficulty": difficulty,
        },
        "segments": segments,
    }

def analyze(points):
    detected = find_hazards(points)
    terrain = get_terrain(points)["terrain_summary"]

    penalties = {"low": 8, "medium": 20, "high": 35}

    if detected:
        highest_penalty = max(
            penalties.get(h["severity"], 10)
            for h in detected
        )

        additional_penalties = min(
            (len(detected) - 1) * 3,
            15
        )

        score = 100 - highest_penalty - additional_penalties
    else:
        score = 100

    if terrain["difficulty"] == "moderate":
        score -= 10
    elif terrain["difficulty"] == "hard":
        score -= 25

    score = max(0, min(100, score))

    risk = (
        "low" if score >= 80
        else "medium" if score >= 50
        else "high"
    )

    warnings = [
    f'{h["name"]}: {h["severity"]} severity '
    f'({h["slope_degrees"]}° slope) near the route.'
    for h in detected
]

    if terrain["difficulty"] == "hard":
        warnings.append("Difficult terrain detected.")

    recommendation = (
        "Recommended route" if risk == "low"
        else "Proceed with caution" if risk == "medium"
        else "Route not recommended"
    )

    length = total_distance(points)

    return {
        "safety_score": score,
        "risk_level": risk,
        "distance_km": length,
        "estimated_duration_hours": round(length / ROVER_SPEED, 2),
        "hazards_detected": len(detected),
        "hazards": [
            {
                "id": h["id"],
                "name": h["name"],
                "severity": h["severity"],
                "distance_from_route_km": h["distance_from_route_km"],
                "slope_degrees": h["slope_degrees"],
                "elevation_m": h["elevation_m"],
            }
            for h in detected
        ],
        "terrain_analysis": {
            "average_slope": terrain["average_slope"],
            "maximum_slope": terrain["maximum_slope"],
            "average_elevation": terrain["average_elevation"],
            "terrain_type": terrain["terrain_type"],
            "difficulty": terrain["difficulty"],
        },
        "warnings": warnings,
        "recommendation": recommendation,
        "data_source": TERRAIN_SOURCE,
    }

def get_saved_route(route_id):
    if route_id not in saved_routes:
        raise HTTPException(
            status_code=404,
            detail="Resource not found"
        )

    return saved_routes[route_id]


@router.post("", status_code=201)
def create_route(request: RouteInput):
    start = request.start.model_dump()
    destination = request.destination.model_dump()

    if start == destination:
        raise HTTPException(
            status_code=400,
            detail="Invalid request parameters"
        )

    direct = [
        interpolate(start, destination, i / 3)
        for i in range(4)
    ]

    midpoint = interpolate(start, destination, 0.5)
    candidates = [direct]

    for offset in (-0.05, 0.05):
        via = {
            "lat": max(-90, min(90, midpoint["lat"] + offset)),
            "lon": midpoint["lon"],
        }

        candidates.append([
            start,
            interpolate(start, via, 0.5),
            via,
            interpolate(via, destination, 0.5),
            destination,
        ])

    points = max(
        candidates,
        key=lambda p: (
            analyze(p)["safety_score"],
            -total_distance(p)
        )
    )

    result = analyze(points)
    route_id = next(next_id)

    status = (
        "recommended" if result["risk_level"] == "low"
        else "caution" if result["risk_level"] == "medium"
        else "not_recommended"
    )

    route = {
        "id": route_id,
        "name": f"Exploration Route {route_id}",
        "start": start,
        "destination": destination,
        "waypoints": points,
        "distance_km": result["distance_km"],
        "estimated_duration_hours": result["estimated_duration_hours"],
        "status": status,
        "data_source": TERRAIN_SOURCE,
    }

    saved_routes[route_id] = route
    return route


@router.get("/{route_id}")
def get_route(route_id: int):
    route = get_saved_route(route_id)
    result = analyze(route["waypoints"])

    return {
        **route,
        "safety_score": result["safety_score"],
        "risk_level": result["risk_level"],
        "terrain_analysis": result["terrain_analysis"],
        "data_source": TERRAIN_SOURCE,
    }


@router.post("/analyze")
def analyze_route(request: AnalysisInput):
    points = [p.model_dump() for p in request.waypoints]

    if (
        points[0] != request.start.model_dump()
        or points[-1] != request.destination.model_dump()
        or len({(p["lat"], p["lon"]) for p in points}) < 2
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid request parameters"
        )

    return analyze(points)


@router.get("/{route_id}/hazards")
def get_route_hazards(route_id: int):
    route = get_saved_route(route_id)
    detected = find_hazards(route["waypoints"])

    return {
        "route_id": route_id,
        "total_hazards": len(detected),
        "hazards": detected,
        "data_source": TERRAIN_SOURCE,
    }


@router.get("/{route_id}/terrain")
def get_route_terrain(route_id: int):
    route = get_saved_route(route_id)

    return {
        "route_id": route_id,
        **get_terrain(route["waypoints"]),
        "data_source": TERRAIN_SOURCE,
    }


@router.delete("/{route_id}")
def delete_route(route_id: int):
    get_saved_route(route_id)
    del saved_routes[route_id]

    return {
        "message": "Route deleted successfully",
        "route_id": route_id,
    }


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from math import radians, sin, cos, asin, sqrt
from itertools import count
from functools import lru_cache

import heapq
import numpy as np
from rasterio.windows import Window
from rasterio.enums import Resampling
from app.data.hirise_reader import load_hirise_data, get_pixel_location

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
            detail="Start and destination must be different."
        )

    points = astar_route(start, destination)

    result = analyze(points)
    route_id = next(next_id)

    status = (
        "recommended" if result["risk_level"] == "low"
        else "caution" if result["risk_level"] == "medium"
        else "not_recommended"
    )

    route = {
        "id": route_id,
        "name": f"A* Mars Exploration Route {route_id}",
        "start": start,
        "destination": destination,
        "waypoints": points,
        "distance_km": result["distance_km"],
        "estimated_duration_hours": result["estimated_duration_hours"],
        "status": status,
        "algorithm": "A*",
        "data_source": "USGS/NASA HiRISE DTM",
    }

    saved_routes[route_id] = route
    return route
def astar_route(start, destination):
    dataset = load_hirise_data()

    start_row, start_col = get_pixel_location(
        dataset, start["lat"], start["lon"]
    )
    end_row, end_col = get_pixel_location(
        dataset, destination["lat"], destination["lon"]
    )

    margin = 3000

    row_min = max(0, min(start_row, end_row) - margin)
    col_min = max(0, min(start_col, end_col) - margin)

    row_max = min(dataset.height, max(start_row, end_row) + margin)
    col_max = min(dataset.width, max(start_col, end_col) + margin)

    height = row_max - row_min
    width = col_max - col_min

    grid_rows = max(2, int(np.ceil(height / 100)))
    grid_cols = max(2, int(np.ceil(width / 100)))

    window = Window(col_min, row_min, width, height)

    elevation = dataset.read(
        1,
        window=window,
        out_shape=(grid_rows, grid_cols),
        resampling=Resampling.average
    ).astype(float)

    valid = np.isfinite(elevation)

    if dataset.nodata is not None:
        valid &= elevation != dataset.nodata

    elevation[~valid] = np.nan

    row_size = height / grid_rows
    col_size = width / grid_cols

    filled = elevation.copy()

    for _ in range(5):
        missing = ~np.isfinite(filled)

        if not missing.any():
            break

        padded = np.pad(filled, 1, mode="edge")

        neighbors = [
            padded[:-2, 1:-1],
            padded[2:, 1:-1],
            padded[1:-1, :-2],
            padded[1:-1, 2:],
        ]

        total = np.zeros_like(filled)
        count = np.zeros_like(filled)

        for neighbor in neighbors:
            available = np.isfinite(neighbor)
            total += np.where(available, neighbor, 0)
            count += available

        fillable = missing & (count > 0)
        filled[fillable] = total[fillable] / count[fillable]

    gradient_y, gradient_x = np.gradient(
        filled, row_size, col_size
    )

    slopes = np.degrees(
        np.arctan(np.sqrt(gradient_x ** 2 + gradient_y ** 2))
    )

    slopes[~valid] = np.inf



    def grid_position(pixel_row, pixel_col):
        row = round((pixel_row - row_min) / row_size)
        col = round((pixel_col - col_min) / col_size)

        return (
            max(0, min(grid_rows - 1, row)),
            max(0, min(grid_cols - 1, col))
        )

    start_node = grid_position(start_row, start_col)
    end_node = grid_position(end_row, end_col)

    def find_valid_node(node):
        r, c = node

        for radius in range(10):
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    nr, nc = r + dr, c + dc

                    if (
                        0 <= nr < grid_rows
                        and 0 <= nc < grid_cols
                        and valid[nr, nc]
                    ):
                        return nr, nc

        raise HTTPException(
            status_code=400,
            detail="No valid HiRISE terrain near start or destination."
        )

    start_node = find_valid_node(start_node)
    end_node = find_valid_node(end_node)

    if start_node == end_node:
        raise HTTPException(
            status_code=400,
            detail="Start and destination are too close."
        )

    hazards = get_terrain_risk_data()

    def hazard_cost(row, col):
        x = col_min + (col + 0.5) * col_size
        y = row_min + (row + 0.5) * row_size
        lon, lat = dataset.xy(y, x)

        point = {
            "lat": y * 0 + lat * 180 / 3396190 / 3.141592653589793,
            "lon": lon * 180 / 3396190 / 3.141592653589793
        }

        penalty = 0

        for hazard in hazards:
            d = distance(point, hazard["location"])
            severity = hazard["severity"].lower()

            radius = {
                "high": 0.25,
                "medium": 0.15,
                "low": 0.075
            }.get(severity, 0.15)

            if d < radius:
                penalty += {
                    "high": 100,
                    "medium": 40,
                    "low": 10
                }.get(severity, 10)

            elif d < 0.5:
                penalty += {
                    "high": 10,
                    "medium": 5,
                    "low": 2
                }.get(severity, 2)

        return penalty

    def heuristic(a, b):
        return (
            np.hypot(a[0] - b[0], a[1] - b[1]) * 100
        )

    open_set = [(0, start_node)]
    came_from = {}
    g_score = {start_node: 0}
    closed = set()

    directions = [
        (-1, 0), (1, 0), (0, -1), (0, 1),
        (-1, -1), (-1, 1), (1, -1), (1, 1)
    ]

    while open_set:
        _, current = heapq.heappop(open_set)

        if current in closed:
            continue

        if current == end_node:
            path = [current]

            while current in came_from:
                current = came_from[current]
                path.append(current)

            path.reverse()
            break

        closed.add(current)

        for dr, dc in directions:
            neighbor = (
                current[0] + dr,
                current[1] + dc
            )

            nr, nc = neighbor

            if (
                not 0 <= nr < grid_rows
                or not 0 <= nc < grid_cols
                or not valid[nr, nc]
                or neighbor in closed
            ):
                continue

            slope = slopes[nr, nc]

            if slope > 45:
                continue
            
            hazard_penalty = hazard_cost(nr, nc)
            
            movement = 100 * (
                np.sqrt(2) if dr and dc else 1
            )

            elevation_change = max(
                0,
                elevation[nr, nc] - elevation[current]
            )

            cost = movement * (
                1 + slope / 30
                + elevation_change / 50
                + hazard_penalty
            )

            tentative = g_score[current] + cost

            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative

                heapq.heappush(
                    open_set,
                    (
                        tentative + heuristic(neighbor, end_node),
                        neighbor
                    )
                )

    else:
        raise HTTPException(
            status_code=400,
            detail="A* could not find a safe path through the available terrain."
        )

    points = []

    for row, col in path:
        pixel_row = row_min + (row + 0.5) * row_size
        pixel_col = col_min + (col + 0.5) * col_size

        x, y = dataset.xy(pixel_row, pixel_col)

        points.append({
            "lat": y * 180 / 3396190 / 3.141592653589793,
            "lon": x * 180 / 3396190 / 3.141592653589793
        })

    points[0] = start
    points[-1] = destination

    return points
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


mars_map = {
    "planet": "Mars",
    "center": {
        "lat": 18.4,
        "lon": 77.7
    },
    "zoom": 5,
    "region": "Jezero Crater",
    "layers": ["satellite", "terrain", "elevation", "hazards", "science_pois"]
}

terrain_layers = [
    {
        "id": 1,
        "name": "Elevation",
        "description": "Simulated elevation data",
        "type": "elevation",
        "min_value": 0,
        "max_value": 500
    },
    {
        "id": 2,
        "name": "Rock Density",
        "description": "Simulated rock density",
        "type": "rock_density",
        "min_value": 0,
        "max_value": 100
    },
    {
        "id": 3,
        "name": "Slope",
        "description": "Simulated surface slope",
        "type": "slope",
        "min_value": 0,
        "max_value": 45
    }
]

hazards = [
    {
        "id": 1,
        "name": "Rock Field",
        "type": "rocks",
        "severity": "high",
        "description": "Area containing large scattered rocks.",
        "lat": 18.42,
        "lon": 77.73,
        "radius": 2.5
    },
    {
        "id": 2,
        "name": "Steep Slope",
        "type": "slope",
        "severity": "medium",
        "description": "Steep terrain that may affect rover movement.",
        "lat": 18.47,
        "lon": 77.79,
        "radius": 1.5
    },
    {
        "id": 3,
        "name": "Uneven Terrain",
        "type": "rough_terrain",
        "severity": "low",
        "description": "Uneven surface with small obstacles.",
        "lat": 18.38,
        "lon": 77.68,
        "radius": 1.0
    }
]

science_pois = [
    {
        "id": 1,
        "name": "Jezero Crater",
        "type": "ancient_lake",
        "importance": "high",
        "description": "A region of interest for studying ancient water activity.",
        "lat": 18.38,
        "lon": 77.58
    },
    {
        "id": 2,
        "name": "Delta Formation",
        "type": "geological",
        "importance": "high",
        "description": "A simulated point of interest for studying sediment deposits.",
        "lat": 18.44,
        "lon": 77.70
    },
    {
        "id": 3,
        "name": "Rock Sample Site",
        "type": "rock_sample",
        "importance": "medium",
        "description": "A potential location for geological sample collection.",
        "lat": 18.35,
        "lon": 77.76
    }
]

routes = [
    {
        "id": 1,
        "name": "Exploration Route A",
        "start": {
            "lat": 18.35,
            "lon": 77.60
        },
        "destination": {
            "lat": 18.50,
            "lon": 77.85
        },
        "waypoints": [
            {"lat": 18.35, "lon": 77.60},
            {"lat": 18.40, "lon": 77.65},
            {"lat": 18.46, "lon": 77.75},
            {"lat": 18.50, "lon": 77.85}
        ],
        "distance_km": 18.5,
        "estimated_duration_hours": 4.5,
        "safety_score": 85,
        "risk_level": "low",
        "status": "recommended"
    },
    {
        "id": 2,
        "name": "Exploration Route B",
        "start": {
            "lat": 18.35,
            "lon": 77.60
        },
        "destination": {
            "lat": 18.50,
            "lon": 77.85
        },
        "waypoints": [
            {"lat": 18.35, "lon": 77.60},
            {"lat": 18.42, "lon": 77.73},
            {"lat": 18.47, "lon": 77.79},
            {"lat": 18.50, "lon": 77.85}
        ],
        "distance_km": 15.2,
        "estimated_duration_hours": 3.8,
        "safety_score": 45,
        "risk_level": "high",
        "status": "not_recommended"
    }
]

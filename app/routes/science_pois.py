
from fastapi import APIRouter, HTTPException, Query

from app.data.mock_data import science_pois
from app.routes.hazards import calculate_distance


router = APIRouter(
    prefix="/api/v1/science-pois",
    tags=["Science POIs"]
)


def format_poi(poi):
    return {
        "id": poi["id"],
        "name": poi["name"],
        "type": poi["type"],
        "importance": poi["importance"],
        "description": poi["description"],
        "location": {
            "lat": poi["lat"],
            "lon": poi["lon"]
        }
    }


@router.get("")
def get_science_pois(
    type: str | None = None,
    importance: str | None = None
):
    filtered = science_pois

    if type is not None:
        filtered = [
            poi for poi in filtered
            if poi["type"] == type.lower()
        ]

    if importance is not None:
        filtered = [
            poi for poi in filtered
            if poi["importance"] == importance.lower()
        ]

    return {
        "total": len(filtered),
        "science_pois": [format_poi(poi) for poi in filtered],
        "data_source": "mock"
    }


@router.get("/nearby")
def get_nearby_science_pois(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: float = Query(..., gt=0)
):
    nearby = []

    for poi in science_pois:
        distance = calculate_distance(
            lat, lon, poi["lat"], poi["lon"]
        )

        if distance <= radius:
            nearby.append({
                "id": poi["id"],
                "name": poi["name"],
                "type": poi["type"],
                "importance": poi["importance"],
                "location": {
                    "lat": poi["lat"],
                    "lon": poi["lon"]
                },
                "distance_km": round(distance, 2)
            })

    nearby.sort(key=lambda poi: poi["distance_km"])

    return {
        "search_location": {
            "lat": lat,
            "lon": lon
        },
        "search_radius_km": radius,
        "total": len(nearby),
        "science_pois": nearby,
        "data_source": "mock"
    }


@router.get("/{poi_id}")
def get_science_poi_by_id(poi_id: int):
    research_interests = {
        1: [
            "Ancient water activity",
            "Crater geology"
        ],
        2: [
            "Sediment deposits",
            "Ancient water activity",
            "Geological history"
        ],
        3: [
            "Rock composition",
            "Sample collection"
        ]
    }

    for poi in science_pois:
        if poi["id"] == poi_id:
            return {
                **format_poi(poi),
                "research_interest": research_interests.get(
                    poi_id, []
                ),
                "data_source": "mock"
            }

    raise HTTPException(
        status_code=404,
        detail="Science POI not found"
    )

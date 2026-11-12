from fastapi import APIRouter, HTTPException
from app.data.mock_data import mars_map, terrain_layers

router = APIRouter(prefix="/api/v1/mars", tags=["Mars Map"])

@router.get("/map")
def get_mars_map():
    return{
        "planet": mars_map["planet"],
        "region": mars_map["region"],
        "center": mars_map["center"],
        "zoom": mars_map["zoom"],
        "available_layers": mars_map["layers"],
        "data_source": "mock"
    }
    
@router.get("/imagery")
def get_mars_imagery(lat: float, lon:float):
    return{
        "location": {
            "lat": lat,
            "lon": lon
        },
        "image": {
            "id": 1,
            "url": "https://example.com/mars-image.jpg",
            "resolution": "simulated",
            "description": "Simulated Mars surface imagery"
        },
        "data_source": "mock"
    }
    
@router.get("/terrain")
def get_mars_terrain(lat: float, lon: float):
    return {
        "location": {
            "lat": lat,
            "lon": lon
        },
        "terrain": {
            "average_elevation": 120,
            "min_elevation": 50,
            "max_elevation": 250,
            "average_slope": 12.5,
            "surface_type": "rocky"
        },
        "unit": {
            "elevation": "meters",
            "slope": "degrees"
        },
        "data_source": "mock"
    }
    
@router.get("/layers")
def get_mars_layers():
    return {
        "total": len(terrain_layers),
        "layers": [
            {
                "id": layer["id"],
                "name": layer["name"],
                "type": layer["type"],
                "description": layer["description"],
                "unit": "meters" if layer["type"] == "elevation" else
                        "percentage" if layer["type"] == "rock_density" else "degrees",
                "enabled": True
            }
            for layer in terrain_layers
        ],
        "data_source": "mock"
    }
    
@router.get("/layers/{layer_id}")
def get_layer_details(layer_id: int):
    for layer in terrain_layers:
        if layer["id"] == layer_id:
            return {
                "id": layer["id"],
                "name": layer["name"],
                "type": layer["type"],
                "unit": "meters" if layer["type"] == "elevation" else "percentage" if layer["type"] == "rock_density" else "degrees",
                "description": layer["description"],
                "min_value": layer["min_value"],
                "max_value": layer["max_value"],
                "data_source": "mock"
            }
            
    raise HTTPException(status_code=404, detail="Layer not found")
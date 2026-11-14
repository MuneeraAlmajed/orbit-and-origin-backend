
from fastapi import APIRouter, HTTPException
from app.data.mock_data import mars_map
from app.data.mola_reader import get_elevation, get_slope
from app.data.hirise_reader import get_hirise_elevation, get_hirise_slope

router = APIRouter(prefix="/api/v1/mars", tags=["Mars Map"])

terrain_layers = [
    {
        "id": 1,
        "name": "Elevation",
        "type": "elevation",
        "description": "Surface elevation from NASA MOLA and HiRISE measurements.",
        "unit": "meters",
        "data_source": "NASA MOLA MEGDR and USGS/NASA HiRISE DTM"
    },
    {
        "id": 2,
        "name": "Slope",
        "type": "slope",
        "description": "Surface slope calculated from neighboring elevation measurements.",
        "unit": "degrees",
        "data_source": "Derived from NASA MOLA MEGDR and USGS/NASA HiRISE DTM"
    }
]


@router.get("/map")
def get_mars_map():
    return {
        "planet": mars_map["planet"],
        "region": mars_map["region"],
        "center": mars_map["center"],
        "zoom": mars_map["zoom"],
        "available_layers": ["satellite", "elevation", "slope"],
        "data_source": "NASA MOLA MEGDR and USGS/NASA HiRISE DTM"
    }


@router.get("/imagery")
def get_mars_imagery(lat: float, lon: float):
    return {
        "location": {
            "lat": lat,
            "lon": lon
        },
        "image": {
            "id": 1,
            "url": "https://trek.nasa.gov/tiles/Mars/EQ/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first_dd/1.0.0/default/default028mm/{z}/{y}/{x}.png",
            "resolution": "25 cm per pixel",
            "description": "NASA HiRISE orthorectified image mosaic"
        },
        "data_source": "NASA HiRISE"
    }


@router.get("/terrain")
def get_mars_terrain(lat: float, lon: float):
    try:
        mola_elevation = get_elevation(lat, lon)
        mola_slope = get_slope(lat, lon)
        hirise_elevation = get_hirise_elevation(lat, lon)
        hirise_slope = get_hirise_slope(lat, lon)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {
        "location": {
            "lat": lat,
            "lon": lon
        },
        "terrain": {
            "elevation": {
                "mola": mola_elevation,
                "hirise": hirise_elevation
            },
            "slope": {
                "mola": mola_slope,
                "hirise": hirise_slope
            }
        },
        "unit": {
            "elevation": "meters",
            "slope": "degrees"
        },
        "data_source": {
            "mola": "NASA MOLA MEGDR",
            "hirise": "USGS/NASA HiRISE DTM",
            "slope": {
                "mola": "Derived from NASA MOLA MEGDR",
                "hirise": "Derived from USGS/NASA HiRISE DTM"
            }
        }
    }


@router.get("/layers")
def get_mars_layers():
    return {
        "total": len(terrain_layers),
        "layers": [
            {
                **layer,
                "enabled": True
            }
            for layer in terrain_layers
        ],
        "data_source": "NASA MOLA MEGDR and USGS/NASA HiRISE DTM"
    }


@router.get("/layers/{layer_id}")
def get_layer_details(layer_id: int):
    for layer in terrain_layers:
        if layer["id"] == layer_id:
            return layer

    raise HTTPException(status_code=404, detail="Layer not found")

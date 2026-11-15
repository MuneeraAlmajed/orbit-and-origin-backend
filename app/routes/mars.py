
from fastapi import APIRouter, HTTPException
from app.data.mock_data import mars_map
from app.data.mola_reader import get_elevation, get_slope
from app.data.hirise_reader import get_hirise_elevation, get_hirise_slope
import math
import numpy as np
from rasterio.enums import Resampling
from app.data.hirise_reader import load_hirise_data

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
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    hirise_elevation = None
    hirise_slope = None
    hirise_errors = []

    try:
        hirise_elevation = get_hirise_elevation(lat, lon)
    except ValueError as error:
        hirise_errors.append(str(error))

    try:
        hirise_slope = get_hirise_slope(lat, lon)
    except ValueError as error:
        hirise_errors.append(str(error))

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
        },
        "hirise_status": "available" if not hirise_errors else "unavailable",
        "hirise_message": hirise_errors
    }
    
@router.get("/terrain/grid")
def get_terrain_grid():
    cells = []

    south = 18.3067994
    north = 18.669315
    west = 77.2229331
    east = 77.85

    rows = 20
    columns = 35

    lat_step = (north - south) / rows
    lon_step = (east - west) / columns

    for row in range(rows):
        for col in range(columns):
            cell_south = south + row * lat_step
            cell_west = west + col * lon_step

            lat = cell_south + lat_step / 2
            lon = cell_west + lon_step / 2

            elevation = None
            slope = None
            source = None

            try:
                elevation = get_hirise_elevation(lat, lon)
                slope = get_hirise_slope(lat, lon)
                source = "USGS/NASA HiRISE DTM"

            except ValueError:
                try:
                    elevation = get_elevation(lat, lon)
                    slope = get_slope(lat, lon)
                    source = "NASA MOLA MEGDR"

                except ValueError:
                    pass

            cells.append({
                "bounds": [
                    [cell_south, cell_west],
                    [cell_south + lat_step, cell_west + lon_step]
                ],
                "elevation": elevation,
                "slope": slope,
                "data_source": source
            })

    return {
        "total_cells": len(cells),
        "data": cells,
        "data_source": "NASA MOLA MEGDR and USGS/NASA HiRISE DTM"
    }
    
@router.get("/terrain/3d")
def get_3d_terrain():
    dataset = load_hirise_data()

    rows = 150
    columns = 150

    terrain = dataset.read(
        1,
        out_shape=(rows, columns),
        resampling=Resampling.average,
        masked=True
    )

    left, bottom, right, top = dataset.bounds

    x_step = (right - left) / columns
    y_step = (top - bottom) / rows

    cells = []

    for row in range(rows):
        for col in range(columns):
            value = terrain[row, col]

            elevation = None

            if not np.ma.is_masked(value):
                if math.isfinite(float(value)):
                    elevation = round(float(value), 2)

            west = left + col * x_step
            east = west + x_step
            north = top - row * y_step
            south = north - y_step

            cells.append({
                "elevation": elevation,
                "bounds": [
                    [
                        math.degrees(south / 3396190),
                        math.degrees(west / 3396190)
                    ],
                    [
                        math.degrees(north / 3396190),
                        math.degrees(east / 3396190)
                    ]
                ]
            })

    return {
        "rows": rows,
        "columns": columns,
        "data": cells,
        "data_source": "USGS/NASA HiRISE DTM",
        "original_resolution_meters": 1
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

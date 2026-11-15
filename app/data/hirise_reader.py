from pathlib import Path
from functools import lru_cache
from rasterio.windows import Window
from rasterio.errors import RasterioIOError
import math
import rasterio

HIRISE_FILE = (
    Path(__file__).parent
    / "nasa"
    / "hirise"
    / "jezero_hirise_dtm_small.tif"
)

MARS_RADIUS = 3396190


@lru_cache(maxsize=1)
def load_hirise_data():
    return rasterio.open(HIRISE_FILE)


def get_pixel_location(dataset, lat, lon):
    x = MARS_RADIUS * math.radians(lon)
    y = MARS_RADIUS * math.radians(lat)

    row, col = dataset.index(x, y)

    if row < 0 or col < 0:
        raise ValueError("Location is outside HiRISE data coverage")

    if row >= dataset.height or col >= dataset.width:
        raise ValueError("Location is outside HiRISE data coverage")

    return row, col


def is_valid_elevation(value, nodata):
    return (
        math.isfinite(float(value))
        and (nodata is None or value != nodata)
    )


def get_hirise_elevation(lat, lon):
    dataset = load_hirise_data()

    try:
        row, col = get_pixel_location(dataset, lat, lon)
        value = dataset.read(
            1,
            window=Window(col, row, 1, 1)
        )[0, 0]
    except (RasterioIOError, ValueError):
        return None

    if not is_valid_elevation(value, dataset.nodata):
        return None

    return round(float(value), 2)


def get_hirise_slope(lat, lon):
    dataset = load_hirise_data()

    try:
        row, col = get_pixel_location(dataset, lat, lon)

        if (
            row <= 0 or col <= 0
            or row >= dataset.height - 1
            or col >= dataset.width - 1
        ):
            return None

        window = Window(col - 1, row - 1, 3, 3)
        values = dataset.read(1, window=window)

    except (RasterioIOError, ValueError):
        return None

    neighbors = [
        values[0, 1],
        values[2, 1],
        values[1, 2],
        values[1, 0]
    ]

    if not all(
        is_valid_elevation(value, dataset.nodata)
        for value in neighbors
    ):
        return None

    pixel_width, pixel_height = dataset.res

    dz_dx = (
        float(values[1, 2]) - float(values[1, 0])
    ) / (2 * pixel_width)

    dz_dy = (
        float(values[2, 1]) - float(values[0, 1])
    ) / (2 * abs(pixel_height))

    slope = math.degrees(
        math.atan(math.sqrt(dz_dx ** 2 + dz_dy ** 2))
    )

    return round(slope, 2)
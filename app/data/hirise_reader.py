
from pathlib import Path
from functools import lru_cache
from rasterio.windows import Window
import math
import rasterio

HIRISE_FILE = (
    Path(__file__).parent
    / "nasa"
    / "hirise"
    / "jezero_hirise_dtm.tif"
)

MARS_RADIUS = 3396190


@lru_cache(maxsize=1)
def load_hirise_data():
    return rasterio.open(HIRISE_FILE)


def get_hirise_elevation(lat, lon):
    dataset = load_hirise_data()

    x = MARS_RADIUS * math.radians(lon)
    y = MARS_RADIUS * math.radians(lat)

    left, bottom, right, top = dataset.bounds

    if not (left <= x <= right and bottom <= y <= top):
        raise ValueError("Location is outside HiRISE data coverage")

    value = next(dataset.sample([(x, y)]))[0]

    if value == dataset.nodata:
        raise ValueError("No elevation data available at this location")

    return round(float(value), 2)


def get_hirise_slope(lat, lon):
    dataset = load_hirise_data()

    x = MARS_RADIUS * math.radians(lon)
    y = MARS_RADIUS * math.radians(lat)

    row, col = dataset.index(x, y)

    if row <= 0 or col <= 0:
        raise ValueError("Not enough neighboring HiRISE data")

    if row >= dataset.height - 1 or col >= dataset.width - 1:
        raise ValueError("Not enough neighboring HiRISE data")

    window = Window(col - 1, row - 1, 3, 3)
    values = dataset.read(1, window=window)

    north = float(values[0, 1])
    south = float(values[2, 1])
    east = float(values[1, 2])
    west = float(values[1, 0])

    neighbors = [north, south, east, west]

    if any(
        not math.isfinite(value) or value == dataset.nodata
        for value in neighbors
    ):
        raise ValueError("Missing neighboring HiRISE elevation data")

    dz_dx = (east - west) / 2
    dz_dy = (south - north) / 2

    slope = math.degrees(
        math.atan(math.sqrt(dz_dx**2 + dz_dy**2))
    )

    return round(slope, 2)
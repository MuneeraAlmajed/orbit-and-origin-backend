from pathlib import Path
from functools import lru_cache
import numpy as np
import math

MOLA_FILE = Path(__file__).parent / "nasa" / "mola" / "megt44n000hb.img"

ROWS = 5632
COLUMNS = 11520
PIXELS_PER_DEGREE = 128
PIXEL_SIZE_METERS = 463.0576672


@lru_cache(maxsize=1)
def load_mola_data():
    return np.memmap(
        MOLA_FILE,
        dtype=">i2",
        mode="r",
        shape=(ROWS, COLUMNS)
    )


def get_indices(lat, lon):
    if not 0 <= lat <= 44 or not 0 <= lon <= 90:
        raise ValueError("Location is outside the MOLA data coverage")

    row = min(int((44 - lat) * PIXELS_PER_DEGREE), ROWS - 1)
    column = min(int(lon * PIXELS_PER_DEGREE), COLUMNS - 1)

    return row, column


def get_elevation(lat, lon):
    row, column = get_indices(lat, lon)
    data = load_mola_data()

    return int(data[row, column])


def get_slope(lat, lon):
    row, column = get_indices(lat, lon)

    if row == 0 or row >= ROWS - 1 or column == 0 or column >= COLUMNS - 1:
        raise ValueError("Not enough neighboring data to calculate slope")

    data = load_mola_data()

    north = int(data[row - 1, column])
    south = int(data[row + 1, column])
    east = int(data[row, column + 1])
    west = int(data[row, column - 1])

    east_west_distance = 2 * PIXEL_SIZE_METERS * math.cos(math.radians(lat))
    north_south_distance = 2 * PIXEL_SIZE_METERS

    dz_dx = (east - west) / east_west_distance
    dz_dy = (south - north) / north_south_distance

    slope = math.degrees(math.atan(math.sqrt(dz_dx**2 + dz_dy**2)))

    return round(slope, 2)
"""Approximate district/market coordinates and road-adjusted distances."""

from __future__ import annotations

import math
from typing import Optional

from config import ROAD_FACTOR
from lexicon import DISTRICTS

# approximate - verify
# District / AMIS market centre coordinates (lat, lon).
COORDS: dict[str, tuple[float, float]] = {
    # AMIS market cities + lexicon districts
    "Lahore": (31.5497, 74.3436),
    "Faisalabad": (31.4504, 73.1350),
    "Multan": (30.1575, 71.5249),
    "Sargodha": (32.0836, 72.6711),
    "Gujranwala": (32.1877, 74.1945),
    "Okara": (30.8081, 73.4458),
    "Rawalpindi": (33.5651, 73.0169),
    "Kasur": (31.1179, 74.4500),
    "Sahiwal": (30.6682, 73.1114),
    "Bahawalpur": (29.3956, 71.6836),
    "Sialkot": (32.4945, 74.5229),
    "Jhang": (31.2781, 72.3317),
    "Sheikhupura": (31.7167, 73.9850),
    "Rahim Yar Khan": (28.4212, 70.2989),
    "Dera Ghazi Khan": (30.0561, 70.6348),
    "Gujrat": (32.5731, 74.0791),
    "Khanewal": (30.3017, 71.9321),
    "Vehari": (30.0451, 72.3489),
    "Muzaffargarh": (30.0703, 71.1933),
    "Pakpattan": (30.3410, 73.3866),
    "Chiniot": (31.7200, 72.9789),
    "Toba Tek Singh": (30.9743, 72.4827),
    "Mandi Bahauddin": (32.5862, 73.4912),
    "Hafizabad": (32.0709, 73.6880),
    "Narowal": (32.1010, 74.8730),
    "Mianwali": (32.5809, 71.5289),
    "Bhakkar": (31.6269, 71.0643),
    "Khushab": (32.2967, 72.3525),
    "Layyah": (30.9693, 70.9428),
    "Lodhran": (29.5405, 71.6336),
    "Rajanpur": (29.1041, 70.3301),
    "Attock": (33.7667, 72.3600),
    "Chakwal": (32.9328, 72.8531),
    "Jhelum": (32.9425, 73.7257),
    "Nankana Sahib": (31.4495, 73.7125),
    "Bahawalnagar": (29.9984, 73.2536),
}

# Ensure every lexicon district has a coordinate entry.
for _name in DISTRICTS:
    if _name not in COORDS:
        raise RuntimeError(f"Missing COORDS for district {_name}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def coords_for(place: str) -> Optional[tuple[float, float]]:
    return COORDS.get(place)


def distance_km(a: str, b: str) -> float:
    """Road-adjusted km between place centres: haversine * ROAD_FACTOR."""
    ca, cb = coords_for(a), coords_for(b)
    if ca is None or cb is None:
        raise KeyError(f"Unknown place for distance: {a!r} / {b!r}")
    return haversine_km(ca[0], ca[1], cb[0], cb[1]) * ROAD_FACTOR

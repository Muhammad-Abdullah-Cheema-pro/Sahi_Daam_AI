"""City re-routing margins from WHOLESALE bands and transport assumptions."""

from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from config import (
    COMMISSION_PCT,
    POTATO_PREFERENCE,
    TARGET_CITIES,
    TOP_N,
    TRANSPORT_RS_PER_MAUND_KM,
)
from geo import distance_km
from model.price_band import BandResult, get_band
from schema import CityMarginResult, ParsedFarmerRequest


def resolve_commodity(crop: str, band_fn: Callable[..., BandResult]) -> Optional[str]:
    """Map farmer crop to AMIS commodity; Potato uses POTATO_PREFERENCE."""
    if crop in {"Wheat", "Tomato", "Onion"}:
        return crop
    if crop == "Potato":
        for pref in POTATO_PREFERENCE:
            # Probe any market city for a usable band
            for city in TARGET_CITIES:
                band = band_fn(city, pref)
                if _usable(band):
                    return pref
        return POTATO_PREFERENCE[0]
    return crop


def _usable(band: BandResult) -> bool:
    return (
        band.basis != "none"
        and band.low is not None
        and band.high is not None
        and band.avg is not None
        and band.avg > 0
    )


def _assumptions_text(distance: float, transport: float) -> str:
    return (
        f"ASSUMPTION transport={TRANSPORT_RS_PER_MAUND_KM} Rs/maund/km; "
        f"commission={COMMISSION_PCT:.0%}; "
        f"distance≈{distance:.1f} km (haversine×ROAD_FACTOR); "
        f"transport_cost≈{transport:.1f} Rs/maund. "
        f"Gross uses WHOLESALE band avg."
    )


def rank_markets(
    request: ParsedFarmerRequest,
    *,
    as_of: Optional[date] = None,
    band_fn: Callable[..., BandResult] = get_band,
    top_n: int = TOP_N,
) -> list[CityMarginResult]:
    """Rank AMIS markets by net price after transport and commission."""
    commodity = resolve_commodity(request.crop, lambda c, com: band_fn(c, com, as_of=as_of))
    if commodity is None:
        return []

    candidates: list[tuple[str, BandResult, float, float, float]] = []
    for city in TARGET_CITIES:
        try:
            dist = distance_km(request.district, city)
        except KeyError:
            continue
        band = band_fn(city, commodity, as_of=as_of)
        if not _usable(band):
            continue
        assert band.avg is not None
        transport = dist * TRANSPORT_RS_PER_MAUND_KM
        net = band.avg * (1.0 - COMMISSION_PCT) - transport
        candidates.append((city, band, dist, transport, net))

    if not candidates:
        return []

    # baseline = farmer quote if given, else nearest usable market's net
    if request.quoted_price_per_maund is not None:
        baseline = float(request.quoted_price_per_maund)
    else:
        nearest = min(candidates, key=lambda x: x[2])
        baseline = nearest[4]

    results: list[CityMarginResult] = []
    for city, band, dist, transport, net in candidates:
        assert band.avg is not None
        break_even = (baseline + transport) / (1.0 - COMMISSION_PCT)
        results.append(
            CityMarginResult(
                city_name=city,
                distance_km=dist,
                gross_price_maund=float(band.avg),
                net_price_maund=float(net),
                net_gain_vs_quote=float(net - baseline),
                break_even_price=float(break_even),
                assumptions=_assumptions_text(dist, transport),
            )
        )

    results.sort(key=lambda r: r.net_price_maund, reverse=True)
    return results[:top_n]

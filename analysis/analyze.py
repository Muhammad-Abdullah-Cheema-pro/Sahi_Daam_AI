"""Orchestrate fair-price verdict + city routing + MusamGuard advisory."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any, Callable, Optional

from advisory_engine import (
    DistrictWeather,
    fetch_district_weather,
    generate_harvest_advice,
)
from analysis.routing import _usable, rank_markets, resolve_commodity
from analysis.trend import get_price_trend
from analysis.verdict import assess_quote
from config import (
    COMMISSION_PCT,
    FARMGATE_ALLOWANCE,
    TARGET_CITIES,
    TRANSPORT_RS_PER_MAUND_KM,
)
from geo import distance_km
from model.price_band import BandResult, get_band
from schema import (
    AnalysisResult,
    DiseaseTriageResult,
    FairPriceVerdict,
    HarvestAdvisory,
    ParsedFarmerRequest,
    VisionTriageResult,
    WeatherSnapshot,
)

logger = logging.getLogger(__name__)

WeatherFn = Callable[[str], Any]
AdviceFn = Callable[..., HarvestAdvisory]
TrendFn = Callable[..., Any]
VisionFn = Callable[..., VisionTriageResult]


def _nearest_usable_market(
    district: str,
    commodity: str,
    *,
    as_of: Optional[date],
    band_fn: Callable[..., BandResult],
) -> tuple[Optional[str], Optional[BandResult]]:
    best_city: Optional[str] = None
    best_band: Optional[BandResult] = None
    best_dist = float("inf")
    for city in TARGET_CITIES:
        try:
            dist = distance_km(district, city)
        except KeyError:
            continue
        band = band_fn(city, commodity, as_of=as_of)
        if not _usable(band):
            continue
        if dist < best_dist:
            best_dist = dist
            best_city = city
            best_band = band
    return best_city, best_band


def _build_advisory(
    request: ParsedFarmerRequest,
    commodity: str,
    ref_city: str,
    *,
    as_of: Optional[date],
    weather_fn: WeatherFn,
    advice_fn: AdviceFn,
    trend_fn: TrendFn,
    disease: Optional[DiseaseTriageResult],
    disclaimers: list[str],
    weather_out: Optional[list] = None,
) -> Optional[HarvestAdvisory]:
    """Build harvest advisory; never raises. Mutates disclaimers in place.

    If ``weather_out`` is a list, a WeatherSnapshot is appended on success.
    """
    try:
        weather = weather_fn(request.district)
        if not isinstance(weather, DistrictWeather):
            if isinstance(weather, dict):
                weather = DistrictWeather(**weather)
            else:
                raise TypeError(f"Unexpected weather type: {type(weather)}")
        if weather_out is not None:
            try:
                weather_out.append(
                    WeatherSnapshot(
                        district=weather.district,
                        forecast_date=str(weather.forecast_date),
                        temp_min_c=float(weather.temp_min_c),
                        temp_max_c=float(weather.temp_max_c),
                        max_precip_prob=float(weather.max_precip_prob),
                        precip_mm_48h=float(weather.precip_mm_48h),
                        wind_max_kmh=float(getattr(weather, "wind_max_kmh", 0.0) or 0.0),
                        source=str(weather.source),
                        from_cache=bool(weather.from_cache),
                    )
                )
            except Exception:  # pragma: no cover
                pass

        trend_result = trend_fn(ref_city, commodity, as_of=as_of)
        label = getattr(trend_result, "label", None)
        if label is None:
            trend = "Flat"
            disclaimers.append("Price trend unavailable; assumed Flat.")
        else:
            trend = label
            disclaimers.append(
                f"Price trend = change in the recent wholesale median at {ref_city} "
                f"over the last ~14 days. Observed, not a forecast."
            )

        advisory = advice_fn(
            request.crop,
            request.crop_stage,
            weather,
            price_trend=trend,
            disease_triage=disease,
        )
        src = getattr(weather, "source", "weather service")
        fdate = getattr(weather, "forecast_date", "unknown")
        cached = getattr(weather, "from_cache", False)
        fetched_at = getattr(weather, "fetched_at", 0.0) or 0.0
        cache_extra = ""
        if cached and fetched_at:
            cache_extra = (
                ", cached forecast from "
                + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(fetched_at))
            )
        elif cached:
            cache_extra = ", cached"
        disclaimers.append(
            f"Weather forecast from {src} for {request.district} "
            f"(forecast_date={fdate}{cache_extra})."
        )
        disclaimers.append(
            "Advice only. Non-chemical/standard extension practice recommendations "
            "based on district-level forecasts."
        )
        return advisory
    except Exception as exc:
        logger.warning("Advisory unavailable: %s", exc)
        disclaimers.append(
            "Weather forecast unavailable; harvest advice not shown."
        )
        return None


def analyze(
    request: ParsedFarmerRequest,
    *,
    as_of: Optional[date] = None,
    image_bytes: Optional[bytes] = None,
    disease_override: Optional[DiseaseTriageResult] = None,
    band_fn: Callable[..., BandResult] = get_band,
    weather_fn: WeatherFn = fetch_district_weather,
    advice_fn: AdviceFn = generate_harvest_advice,
    trend_fn: TrendFn = get_price_trend,
    vision_fn: Optional[VisionFn] = None,
) -> AnalysisResult:
    """Build AnalysisResult for a farmer request. Never raises.

    Optional ``image_bytes`` runs MusamGuard vision triage; ``disease_override``
    wins over vision disease fields when provided.
    """
    vision: Optional[VisionTriageResult] = None
    try:
        if image_bytes:
            if vision_fn is None:
                from vision_engine import analyze_crop_image

                vision_fn = analyze_crop_image
            vision = vision_fn(image_bytes, request.crop)
            # Prefer vision phenology when request stage was default-ish
            if vision and vision.image_quality_ok:
                request = request.model_copy(
                    update={"crop_stage": vision.phenology_stage.value}
                )
    except Exception as exc:  # pragma: no cover
        logger.warning("Vision path failed: %s", exc)
        vision = None

    disease = disease_override
    if disease is None and vision is not None:
        disease = vision.disease_triage

    try:
        commodity = resolve_commodity(
            request.crop, lambda c, com: band_fn(c, com, as_of=as_of)
        )
        if commodity is None:
            verdict = FairPriceVerdict(
                reference_market=request.district,
                verdict_status="Unable to assess",
                basis="none",
                reason=(
                    f"No AMIS commodity mapping for crop {request.crop!r}. "
                    "Comparison is against WHOLESALE prices."
                ),
            )
            return AnalysisResult(
                request=request,
                verdict=verdict,
                advisory=None,
                vision=vision,
                top_cities=[],
                disclaimers=_disclaimers(None, None),
            )

        ref_city, ref_band = _nearest_usable_market(
            request.district, commodity, as_of=as_of, band_fn=band_fn
        )

        if ref_city is None or ref_band is None:
            verdict = FairPriceVerdict(
                reference_market=request.district,
                verdict_status="Unable to assess",
                basis="none",
                reason=(
                    f"No market has usable WHOLESALE data for {commodity}. "
                    "Comparison is against WHOLESALE prices."
                ),
            )
            return AnalysisResult(
                request=request,
                verdict=verdict,
                advisory=None,
                vision=vision,
                top_cities=[],
                disclaimers=_disclaimers(None, commodity),
            )

        verdict = assess_quote(
            request.quoted_price_per_maund,
            ref_band,
            reference_market=ref_city,
        )
        if ref_city != request.district:
            extra = (
                f" Reference market is {ref_city} (nearest AMIS market with a "
                f"usable WHOLESALE band for {commodity}), not {request.district}."
            )
            verdict = verdict.model_copy(
                update={"reason": (verdict.reason or "") + extra}
            )

        top = rank_markets(request, as_of=as_of, band_fn=band_fn)
        disclaimers = _disclaimers(ref_band, commodity)
        if vision is not None and not vision.image_quality_ok:
            disclaimers.append(
                "Photo quality flagged — confirm phenology/disease manually. "
                + (vision.quality_issue_reason or "")
            )
        weather_box: list = []
        advisory = _build_advisory(
            request,
            commodity,
            ref_city,
            as_of=as_of,
            weather_fn=weather_fn,
            advice_fn=advice_fn,
            trend_fn=trend_fn,
            disease=disease,
            disclaimers=disclaimers,
            weather_out=weather_box,
        )
        return AnalysisResult(
            request=request,
            verdict=verdict,
            advisory=advisory,
            vision=vision,
            weather=weather_box[0] if weather_box else None,
            top_cities=top,
            disclaimers=disclaimers,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("analyze failed: %s", exc)
        verdict = FairPriceVerdict(
            reference_market=request.district,
            verdict_status="Unable to assess",
            basis="none",
            reason=(
                f"Analysis error: {exc}. Comparison is against WHOLESALE prices."
            ),
        )
        return AnalysisResult(
            request=request,
            verdict=verdict,
            advisory=None,
            vision=vision,
            top_cities=[],
            disclaimers=_disclaimers(None, None),
        )


def _disclaimers(band: Optional[BandResult], commodity: Optional[str]) -> list[str]:
    lines = [
        "WHOLESALE mandi prices are not farm-gate prices.",
        (
            f"Transport ({TRANSPORT_RS_PER_MAUND_KM} Rs/maund/km), "
            f"commission ({COMMISSION_PCT:.0%}), and farm-gate allowance "
            f"({FARMGATE_ALLOWANCE:.0%}) are ASSUMPTIONS — adjustable in config."
        ),
    ]
    if band is not None:
        as_of = band.data_as_of.isoformat() if band.data_as_of else "unknown"
        lines.append(
            f"Band basis={band.basis}, data_as_of={as_of}, "
            f"sample_days={band.sample_days}"
            + (f", commodity={commodity}" if commodity else "")
            + "."
        )
    else:
        lines.append("No usable price band was available for this request.")
    return lines

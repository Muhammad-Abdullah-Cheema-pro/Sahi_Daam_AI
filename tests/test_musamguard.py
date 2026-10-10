"""MusamGuard phenology × weather matrix + vision fallback (offline)."""

from __future__ import annotations

from advisory_engine import DistrictWeather, generate_harvest_advice
from schema import DiseaseTriageResult, EnhancedHarvestAdvisory, PhenologyStage
from vision_engine import analyze_crop_image


def _wx(**kwargs) -> DistrictWeather:
    base = dict(
        district="Multan",
        forecast_date="2026-10-10",
        precip_mm_48h=0.0,
        max_precip_prob=10.0,
        temp_min_c=20.0,
        temp_max_c=32.0,
        source="toy",
        from_cache=False,
    )
    base.update(kwargs)
    return DistrictWeather(**base)


def test_wheat_grain_filling_heatwave() -> None:
    adv = generate_harvest_advice(
        "Wheat",
        "Grain-Filling",
        _wx(temp_max_c=39.0),
    )
    assert isinstance(adv, EnhancedHarvestAdvisory)
    assert adv.weather_risk == "High"
    assert adv.weather_threat_type == "Heatwave"
    assert "Potassium Nitrate" in adv.mitigation_protocol or "SOP" in adv.mitigation_protocol
    assert "district-level forecasts" in adv.disclaimer


def test_rain_on_harvest_ready_wheat() -> None:
    adv = generate_harvest_advice(
        "Wheat",
        "Ready to harvest",
        _wx(precip_mm_48h=15.0, max_precip_prob=70.0),
    )
    assert adv.weather_threat_type == "Unseasonal Rain"
    assert "tarpaulin" in adv.mitigation_protocol.lower()


def test_frost_on_young_tomato() -> None:
    adv = generate_harvest_advice(
        "Tomato",
        "Growing",
        _wx(temp_min_c=2.0),
    )
    assert adv.weather_threat_type == "Frost"
    assert adv.weather_risk == "High"


def test_disease_tip_appended() -> None:
    disease = DiseaseTriageResult(
        detected_disease="Leaf Spot",
        confidence=0.7,
        symptoms_summary="Brown spots on older leaves.",
        is_healthy=False,
        severity="moderate",
    )
    adv = generate_harvest_advice(
        "Tomato",
        "Nearly ready",
        _wx(),
        disease_triage=disease,
    )
    assert "Leaf Spot" in adv.disease_action_tip
    assert "ventilation" in adv.disease_action_tip.lower()
    assert "pesticide" not in adv.action_advice.lower()


def test_vision_fallback_no_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    out = analyze_crop_image(b"\xff\xd8\xff" + b"\x00" * 3000, "Tomato")
    assert out.image_quality_ok is False
    assert isinstance(out.phenology_stage, PhenologyStage)
    assert out.quality_issue_reason


def test_phenology_enum_values() -> None:
    assert PhenologyStage.GRAIN_FILLING.value == "Grain-Filling"
    assert PhenologyStage.EARLY_FLOWERING.value == "Early Flowering"

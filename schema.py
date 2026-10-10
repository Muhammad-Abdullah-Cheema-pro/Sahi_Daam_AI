"""Pydantic v2 schemas for Sahi Daam AI farmer request analysis."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PhenologyStage(str, Enum):
    """Crop phenology / readiness stages (MusamGuard + harvest flow)."""

    GROWING = "Growing"
    EARLY_FLOWERING = "Early Flowering"
    GRAIN_FILLING = "Grain-Filling"
    NEARLY_READY = "Nearly ready"
    READY_TO_HARVEST = "Ready to harvest"
    HARVESTED_NOT_SOLD = "Harvested, not sold"


WeatherThreatType = Literal[
    "Heatwave",
    "Thermal Night Stress",
    "Unseasonal Rain",
    "Frost",
    "None",
]


class ParsedFarmerRequest(BaseModel):
    """Structured farmer sales request parsed from voice or text input."""

    model_config = ConfigDict(str_strip_whitespace=True)

    crop: str = Field(
        ...,
        min_length=1,
        description="Crop name, e.g. 'Wheat', 'Tomato', 'Potato', 'Onion'.",
    )
    quantity_maunds: float = Field(
        ...,
        gt=0,
        description="Quantity offered for sale, in maunds.",
    )
    district: str = Field(
        ...,
        min_length=1,
        description="Farmer's district / local mandi area.",
    )
    quoted_price_per_maund: Optional[float] = Field(
        default=None,
        gt=0,
        description="Broker or buyer quoted price per maund.",
    )
    crop_stage: str = Field(
        default="Ready to harvest",
        min_length=1,
        description="Phenological or readiness stage of the crop.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Parser confidence score in [0, 1].",
    )
    language_detected: Optional[str] = Field(
        default=None,
        description="Detected language of the farmer input, if known.",
    )
    raw_transcript: Optional[str] = Field(
        default=None,
        description="Original voice/text transcript before structured parsing.",
    )

    @field_validator("crop", "district", "crop_stage")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class FairPriceVerdict(BaseModel):
    """Fair-price assessment against a reference wholesale market range."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reference_market: str = Field(
        ...,
        min_length=1,
        description="Reference mandi or wholesale market used for comparison.",
    )
    predicted_low_maund: Optional[float] = Field(
        default=None,
        ge=0,
        description="Lower bound of predicted wholesale price per maund.",
    )
    predicted_high_maund: Optional[float] = Field(
        default=None,
        ge=0,
        description="Upper bound of predicted wholesale price per maund.",
    )
    predicted_avg_maund: Optional[float] = Field(
        default=None,
        ge=0,
        description="Average predicted wholesale price per maund.",
    )
    verdict_status: Literal["Fair", "Low", "Very low", "Unable to assess"] = Field(
        ...,
        description="One of: 'Fair', 'Low', 'Very low', 'Unable to assess'.",
    )
    percentage_gap: Optional[float] = Field(
        default=None,
        description="Percentage gap of quoted price vs predicted average.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Human-readable explanation when assessment is constrained or unavailable.",
    )
    basis: Literal["model_band", "recent_median_band", "none"] = Field(
        ...,
        description="Basis used for the predicted price band.",
    )
    data_as_of: Optional[date] = Field(
        default=None,
        description="As-of date for the market data used in the verdict.",
    )
    sample_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Days of history used for the verdict band.",
    )

    @field_validator("reference_market")
    @classmethod
    def _non_blank_market(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _validate_verdict_consistency(self) -> FairPriceVerdict:
        if self.verdict_status == "Unable to assess":
            if self.reason is None or not str(self.reason).strip():
                raise ValueError(
                    "reason must be non-empty when verdict_status is 'Unable to assess'"
                )
            # Prices, percentage_gap, and any basis are allowed so a band can
            # still be shown when the farmer gave no quote.
            return self

        missing = [
            name
            for name, value in (
                ("predicted_low_maund", self.predicted_low_maund),
                ("predicted_high_maund", self.predicted_high_maund),
                ("predicted_avg_maund", self.predicted_avg_maund),
                ("percentage_gap", self.percentage_gap),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                "when verdict_status is not 'Unable to assess', these fields are required: "
                + ", ".join(missing)
            )

        low = self.predicted_low_maund
        high = self.predicted_high_maund
        avg = self.predicted_avg_maund
        assert low is not None and high is not None and avg is not None

        if high < low:
            raise ValueError("predicted_high_maund must be >= predicted_low_maund")
        if avg < low or avg > high:
            raise ValueError(
                "predicted_avg_maund must be within [predicted_low_maund, predicted_high_maund]"
            )
        return self


class DiseaseTriageResult(BaseModel):
    """Leaf / canopy disease triage from vision or manual override."""

    model_config = ConfigDict(str_strip_whitespace=True)

    detected_disease: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    symptoms_summary: str = Field(..., min_length=1)
    is_healthy: bool = True
    severity: str = Field(default="none", min_length=1)


class VisionTriageResult(BaseModel):
    """Combined phenology + disease triage from a crop photo."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phenology_stage: PhenologyStage
    disease_triage: DiseaseTriageResult
    image_quality_ok: bool = True
    quality_issue_reason: Optional[str] = None


class HarvestAdvisory(BaseModel):
    """Harvest-or-hold advisory based on weather risk and price trend."""

    model_config = ConfigDict(str_strip_whitespace=True)

    weather_risk: Literal["High", "Medium", "Low"] = Field(
        ...,
        description="One of: 'High', 'Medium', 'Low'.",
    )
    price_trend: Literal["Rising", "Flat", "Falling"] = Field(
        ...,
        description="One of: 'Rising', 'Flat', 'Falling'.",
    )
    action_advice: str = Field(
        ...,
        min_length=1,
        description=(
            "Generic harvest/hold / extension-practice advice "
            "(e.g. shading, ventilation, tarpaulins, harvest timing, SOP spray)."
        ),
    )
    disclaimer: str = Field(
        default=(
            "Advice only. Non-chemical/standard extension practice recommendations "
            "based on district-level forecasts."
        ),
        min_length=1,
        description="Explicit agronomic disclaimer.",
    )

    @field_validator("action_advice", "disclaimer")
    @classmethod
    def _non_blank_advice_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class EnhancedHarvestAdvisory(HarvestAdvisory):
    """MusamGuard-enhanced advisory with threat type and mitigation protocol."""

    weather_threat_type: WeatherThreatType = "None"
    mitigation_protocol: str = Field(default="", description="Step-by-step mitigation.")
    disease_action_tip: str = Field(
        default="",
        description="Non-chemical field hygiene tip from disease triage.",
    )


class CityMarginResult(BaseModel):
    """Net margin estimate for routing produce to an alternate city market."""

    model_config = ConfigDict(str_strip_whitespace=True)

    city_name: str = Field(
        ...,
        min_length=1,
        description="Destination city / mandi name.",
    )
    distance_km: float = Field(
        ...,
        ge=0,
        description=(
            "Approximate straight-line distance between district centres, "
            "in km (estimate)"
        ),
    )
    gross_price_maund: float = Field(
        ...,
        ge=0,
        description="Gross wholesale price per maund in the destination city.",
    )
    net_price_maund: float = Field(
        ...,
        description="Net price per maund after transport and related costs.",
    )
    net_gain_vs_quote: float = Field(
        ...,
        description="Net gain per maund versus the farmer's quoted local price.",
    )
    break_even_price: float = Field(
        ...,
        ge=0,
        description="Break-even destination price per maund covering logistics.",
    )
    assumptions: str = Field(
        ...,
        min_length=1,
        description="Summary of the transport rate and commission used.",
    )

    @field_validator("city_name", "assumptions")
    @classmethod
    def _non_blank_city_fields(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class ParseOutcome(BaseModel):
    """Result of parsing farmer voice/text into a structured request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal["ok", "needs_clarification", "failed"] = Field(
        ...,
        description="Parse pipeline status.",
    )
    request: Optional[ParsedFarmerRequest] = Field(
        default=None,
        description="Parsed request when status is 'ok' (or partial when clarifying).",
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="Field names still needed from the farmer.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Short plain-language prompt asking the farmer for what is missing.",
    )

    @field_validator("message")
    @classmethod
    def _non_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class WeatherSnapshot(BaseModel):
    """Compact 48 h forecast numbers for the results dashboard."""

    district: str
    forecast_date: str
    temp_min_c: float
    temp_max_c: float
    max_precip_prob: float
    precip_mm_48h: float
    wind_max_kmh: float = 0.0
    source: str = "Open-Meteo"
    from_cache: bool = False


class AnalysisResult(BaseModel):
    """Full analysis payload returned to the Streamlit UI."""

    request: ParsedFarmerRequest
    verdict: FairPriceVerdict
    advisory: Optional[HarvestAdvisory] = None
    vision: Optional[VisionTriageResult] = None
    weather: Optional[WeatherSnapshot] = None
    top_cities: List[CityMarginResult] = Field(default_factory=list)
    disclaimers: List[str] = Field(default_factory=list)

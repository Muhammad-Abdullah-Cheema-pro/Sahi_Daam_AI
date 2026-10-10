"""Pure UI formatting helpers (no Streamlit imports)."""

from __future__ import annotations

from typing import Any, Optional

from schema import (
    AnalysisResult,
    CityMarginResult,
    EnhancedHarvestAdvisory,
    FairPriceVerdict,
    HarvestAdvisory,
)

# TODO: native Urdu speaker review
CITY_URDU = {
    "Lahore": "لاہور",
    "Faisalabad": "فیصل آباد",
    "Gujranwala": "گوجرانوالہ",
    "Okara": "اوکاڑہ",
    "Sargodha": "سرگودھا",
    "Rawalpindi": "راولپنڈی",
    "Multan": "ملتان",
}

STATUS_STYLE: dict[str, dict[str, str]] = {
    "Fair": {"color": "green", "emoji": "✅", "label": "Fair"},
    "Low": {"color": "yellow", "emoji": "⚠️", "label": "Low"},
    "Very low": {"color": "red", "emoji": "🚨", "label": "Very low"},
    "Unable to assess": {"color": "gray", "emoji": "❔", "label": "Unable to assess"},
}

WHOLESALE_CAPTION = "Wholesale prices are not farm-gate prices."

_FORBIDDEN = (
    "cheat",
    "fraud",
    "scam",
    "lying",
    "gouging",
    "thief",
    "steal",
    "dishonest",
)


def _round10(value: float) -> int:
    return int(round(float(value) / 10.0) * 10)


def verdict_sentence(verdict: FairPriceVerdict) -> str:
    """Farmer-facing English sentence. Never accuses brokers."""
    status = verdict.verdict_status
    gap = verdict.percentage_gap
    # percentage_gap = (quote - avg) / avg * 100  → negative means below wholesale avg
    gap_txt = ""
    if gap is not None:
        if gap < 0:
            gap_txt = f" About {abs(gap):.0f}% below the wholesale average."
        elif gap > 0:
            gap_txt = f" About {gap:.0f}% above the wholesale average."
        else:
            gap_txt = " About equal to the wholesale average."

    if status == "Fair":
        body = "Quote is within the wholesale range." + gap_txt
    elif status == "Low":
        body = "Quote is below the wholesale range." + gap_txt
    elif status == "Very low":
        body = "Quote is well below the wholesale range." + gap_txt
    else:
        body = (verdict.reason or "Unable to assess the quote right now.").strip()

    text = f"{body} {WHOLESALE_CAPTION}"
    low = text.lower()
    for word in _FORBIDDEN:
        if word in low:
            text = (
                "Quote assessment uses wholesale ranges only. "
                + WHOLESALE_CAPTION
            )
            break
    return text


def band_caption(verdict: FairPriceVerdict) -> str:
    basis_label = {
        "model_band": "ML model band",
        "recent_median_band": "Recent median-and-spread band (fallback)",
        "none": "No band",
    }.get(verdict.basis, verdict.basis)
    parts = []
    if (
        verdict.predicted_low_maund is not None
        and verdict.predicted_avg_maund is not None
        and verdict.predicted_high_maund is not None
    ):
        parts.append(
            f"Band: low {verdict.predicted_low_maund:.0f} / "
            f"avg {verdict.predicted_avg_maund:.0f} / "
            f"high {verdict.predicted_high_maund:.0f} Rs per maund"
        )
    parts.append(f"Basis: {basis_label}")
    if verdict.data_as_of is not None:
        parts.append(f"data_as_of={verdict.data_as_of.isoformat()}")
    if verdict.sample_days is not None:
        parts.append(f"sample_days={verdict.sample_days}")
    return " · ".join(parts)


def format_city_rows(
    top_cities: list[CityMarginResult],
    has_quote: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in top_cities:
        row: dict[str, Any] = {
            "City": c.city_name,
            "Distance (km, approx.)": round(c.distance_km, 1),
            "Gross Rs/maund": round(c.gross_price_maund, 0),
            "Net Rs/maund": round(c.net_price_maund, 0),
            "Break-even Rs/maund": round(c.break_even_price, 0),
        }
        if has_quote:
            row["Net gain vs quote"] = round(c.net_gain_vs_quote, 0)
        rows.append(row)
    return rows


def build_urdu_summary(result: AnalysisResult) -> str:
    """Deterministic Urdu summary for gTTS (no LLM). Skip missing parts."""
    # TODO: native Urdu speaker review
    parts: list[str] = []
    req = result.request
    v = result.verdict
    price = req.quoted_price_per_maund

    if v.verdict_status == "Fair" and price is not None:
        parts.append(
            f"آپ کو ملنے والی قیمت {_round10(price)} روپے فی من ہے، "
            f"جو آج کی ہول سیل رینج کے اندر ہے۔"
        )
    elif v.verdict_status == "Low" and price is not None:
        low = v.predicted_low_maund
        high = v.predicted_high_maund
        if low is not None and high is not None:
            parts.append(
                f"آپ کو بتائی گئی قیمت {_round10(price)} روپے فی من ہے، "
                f"جو ہول سیل رینج سے کم ہے۔ متوقع رینج {_round10(low)} سے "
                f"{_round10(high)} روپے فی من ہے۔"
            )
        else:
            parts.append(
                f"آپ کو بتائی گئی قیمت {_round10(price)} روپے فی من ہے، "
                f"جو ہول سیل رینج سے کم ہے۔"
            )
    elif v.verdict_status == "Very low" and price is not None:
        low = v.predicted_low_maund
        high = v.predicted_high_maund
        if low is not None and high is not None:
            parts.append(
                f"آپ کو بتائی گئی قیمت {_round10(price)} روپے فی من ہے، "
                f"جو ہول سیل رینج سے کافی کم ہے۔ متوقع رینج {_round10(low)} سے "
                f"{_round10(high)} روپے فی من ہے۔"
            )
        else:
            parts.append(
                f"آپ کو بتائی گئی قیمت {_round10(price)} روپے فی من ہے، "
                f"جو ہول سیل رینج سے کافی کم ہے۔"
            )
    elif v.verdict_status == "Unable to assess":
        parts.append("معذرت، اس وقت قیمت کا جائزہ ممکن نہیں۔")

    if result.top_cities:
        best = result.top_cities[0]
        city_ur = CITY_URDU.get(best.city_name, best.city_name)
        if best.net_gain_vs_quote > 0:
            parts.append(
                f"سب سے بہتر منڈی {city_ur} ہے، جہاں خرچ نکال کر تقریباً "
                f"{_round10(best.net_price_maund)} روپے فی من بچتے ہیں۔"
            )
        else:
            parts.append(
                "دوسری منڈیوں میں خرچ نکال کر کوئی واضح فائدہ نظر نہیں آتا۔"
            )

    adv: Optional[HarvestAdvisory] = result.advisory
    if adv is not None:
        if adv.weather_risk == "High":
            parts.append(
                "موسم کا خطرہ زیادہ ہے۔ انتظار کرنے کے بجائے جلد فیصلہ کریں。"
            )
        elif adv.weather_risk == "Medium":
            parts.append(
                "موسم پر روزانہ نظر رکھیں اور دو دن کے اندر فیصلہ کریں。"
            )
        elif adv.weather_risk == "Low" and adv.price_trend == "Rising":
            parts.append(
                "موسم کا خطرہ کم ہے اور قیمتیں بڑھ رہی ہیں، چند دن انتظار کیا جا سکتا ہے۔"
            )
        else:
            parts.append(
                "انتظار کا کوئی فائدہ نظر نہیں آتا، منڈیوں کا موازنہ کر کے فروخت کریں。"
            )
        if isinstance(adv, EnhancedHarvestAdvisory) and adv.mitigation_protocol.strip():
            threat = adv.weather_threat_type
            if threat and threat != "None":
                parts.append(
                    f"موسمی خطرہ کی قسم: {threat}۔ میدان میں احتیاطی قدم اٹھائیں۔"
                )
            if adv.disease_action_tip.strip():
                parts.append("پتوں کی صحت پر نظر رکھیں اور ہوا داری بہتر کریں۔")

    parts.append(
        "یاد رہے کہ ہول سیل قیمتیں کھیت کی قیمت نہیں ہوتیں۔ "
        "یہ صرف مشورہ ہے — غیر کیمیائی ایکسٹینشن رہنمائی؛ مقامی زرعی دفتر سے رائے لیں۔"
    )
    return " ".join(parts).strip()

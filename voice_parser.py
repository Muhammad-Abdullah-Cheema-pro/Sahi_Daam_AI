"""Farmer sale-request parser: LLM first, offline lexicon fallback."""

from __future__ import annotations

import logging
from typing import Any, Optional

from lexicon import (
    LINK_WORDS,
    PRICE_KEYWORDS,
    canonical_crop,
    canonical_district,
    canonical_quantity_unit,
    find_crop,
    find_district,
    find_number_spans,
    normalize_text,
    price_to_per_maund,
    quantity_to_maunds,
)
from llm_client import LLMError, extract_from_audio, extract_from_text
from schema import ParseOutcome, ParsedFarmerRequest

logger = logging.getLogger(__name__)

REQUIRED_ORDER = ["crop", "quantity_maunds", "district"]

_BASIC_NOTE = "(Basic mode: please check these details.)"
_CROPS_NOTE = (
    "Supported crops: Wheat, Tomato, Potato, Onion / "
    "ابھی صرف گندم، ٹماٹر، آلو اور پیاز شامل ہیں۔"
)
_PUNJAB_NOTE = (
    "Only Punjab districts are supported for now / "
    "ابھی صرف پنجاب کے اضلاع شامل ہیں۔"
)


def rule_based_extract(text: str) -> dict[str, Any]:
    """Deterministic offline extraction from free text."""
    norm = normalize_text(text)
    tokens = norm.split()
    spans = find_number_spans(tokens)

    quantity: Optional[float] = None
    quantity_unit: Optional[str] = None
    quantity_span_idx: Optional[int] = None

    for idx, (s, e, val) in enumerate(spans):
        if e < len(tokens):
            unit = canonical_quantity_unit(tokens[e])
            if unit is not None:
                quantity = val
                quantity_unit = unit
                quantity_span_idx = idx
                break

    price: Optional[float] = None
    price_unit: str = "per_maund"
    other_spans = [
        (i, sp) for i, sp in enumerate(spans) if i != quantity_span_idx
    ]

    def _has_price_keyword_near(s: int, e: int) -> bool:
        # immediately before or after, optionally through one link word
        # before: tokens[s-1] or tokens[s-2] link + tokens[s-1] keyword? 
        # "keyword immediately before or after it (optionally through a link word)"
        # before: [keyword] [span] or [keyword] [link] [span] or [link] [keyword] [span]?
        # Interpret: keyword adjacent, or keyword with one link word between.
        left = tokens[max(0, s - 2) : s]
        right = tokens[e : min(len(tokens), e + 2)]
        # check patterns around span
        if s > 0 and tokens[s - 1] in PRICE_KEYWORDS:
            return True
        if s > 1 and tokens[s - 1] in LINK_WORDS and tokens[s - 2] in PRICE_KEYWORDS:
            return True
        if s > 1 and tokens[s - 2] in LINK_WORDS and tokens[s - 1] in PRICE_KEYWORDS:
            return True
        if e < len(tokens) and tokens[e] in PRICE_KEYWORDS:
            return True
        if e + 1 < len(tokens) and tokens[e] in LINK_WORDS and tokens[e + 1] in PRICE_KEYWORDS:
            return True
        if e + 1 < len(tokens) and tokens[e] in PRICE_KEYWORDS and tokens[e + 1] in LINK_WORDS:
            return True
        # also "2800 rupay" — keyword after
        _ = left, right
        return False

    priced: list[tuple[int, tuple[int, int, float]]] = []
    for i, sp in other_spans:
        if _has_price_keyword_near(sp[0], sp[1]):
            priced.append((i, sp))

    chosen: Optional[tuple[int, int, float]] = None
    if len(priced) == 1:
        chosen = priced[0][1]
    elif len(priced) > 1:
        chosen = priced[0][1]
    elif len(other_spans) == 1:
        chosen = other_spans[0][1]

    if chosen is not None:
        s, e, val = chosen
        price = val
        window = tokens[e : e + 3]
        price_unit = "per_maund"
        for tok in window:
            if tok in {"kg", "kilo", "kilogram", "کلو"} or canonical_quantity_unit(tok) == "kg":
                price_unit = "per_kg"
                break
            if tok in {"quintal", "qtl", "کوئنٹل"} or canonical_quantity_unit(tok) == "quintal":
                price_unit = "per_100kg"
                break
            if canonical_quantity_unit(tok) == "maund" or tok in {"maund", "maunds", "man", "من"}:
                price_unit = "per_maund"
                break

    return {
        "crop": find_crop(text),
        "quantity": quantity,
        "quantity_unit": quantity_unit,
        "district": find_district(text),
        "quoted_price": price,
        "price_unit": price_unit if price is not None else None,
        "crop_stage": None,
        "raw_transcript": text,
        "language_detected": None,
        "confidence": 0.5,
    }


def _clarification_message(missing: list[str]) -> str:
    parts: list[str] = []
    if "crop" in missing:
        parts.append("which crop / فصل کون سی ہے؟")
    if "quantity_maunds" in missing:
        parts.append("how many maunds / کتنے من ہیں؟")
    if "district" in missing:
        parts.append("which district / کس ضلع میں ہیں؟")
    msg = "Please tell: " + "; ".join(parts) if parts else "Please clarify your request."
    if "crop" in missing:
        msg += " " + _CROPS_NOTE
    if "district" in missing:
        msg += " " + _PUNJAB_NOTE
    return msg


def build_outcome(extracted: dict[str, Any], *, extra_message: str = "") -> ParseOutcome:
    """Canonicalise, convert units, and build a ParseOutcome. Never raises."""
    try:
        crop_raw = extracted.get("crop")
        district_raw = extracted.get("district")
        crop = canonical_crop(str(crop_raw)) if crop_raw else None
        if crop is None and crop_raw:
            # already canonical English name?
            crop = canonical_crop(str(crop_raw))
        if crop is None and isinstance(crop_raw, str) and crop_raw.strip() in {
            "Wheat", "Tomato", "Potato", "Onion",
        }:
            crop = crop_raw.strip()
        # Also accept find if raw is free text
        if crop is None and crop_raw:
            crop = find_crop(str(crop_raw)) or canonical_crop(str(crop_raw))

        district = None
        if district_raw:
            district = (
                canonical_district(str(district_raw))
                or find_district(str(district_raw))
            )

        qty_maunds: Optional[float] = None
        q_val = extracted.get("quantity")
        q_unit = extracted.get("quantity_unit")
        if q_val is not None:
            try:
                qf = float(q_val)
                if qf > 0 and q_unit:
                    qty_maunds = quantity_to_maunds(qf, str(q_unit))
                elif qf > 0 and not q_unit:
                    qty_maunds = None
                else:
                    qty_maunds = None
            except (TypeError, ValueError):
                qty_maunds = None

        quote: Optional[float] = None
        p_val = extracted.get("quoted_price")
        p_unit = extracted.get("price_unit") or "per_maund"
        if p_val is not None:
            try:
                pf = float(p_val)
                if pf > 0:
                    quote = price_to_per_maund(pf, str(p_unit))
                else:
                    quote = None
            except (TypeError, ValueError):
                quote = None

        missing: list[str] = []
        if not crop:
            missing.append("crop")
        if qty_maunds is None:
            missing.append("quantity_maunds")
        if not district:
            missing.append("district")

        conf_raw = extracted.get("confidence")
        if conf_raw is None:
            conf = 0.8
        else:
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = 0.8
        conf = max(0.0, min(1.0, conf))

        stage = extracted.get("crop_stage") or "Ready to harvest"
        if not str(stage).strip():
            stage = "Ready to harvest"

        if missing:
            msg = _clarification_message(missing)
            if extra_message:
                msg = f"{msg} {extra_message}".strip()
            return ParseOutcome(
                status="needs_clarification",
                request=None,
                missing_fields=missing,
                message=msg,
            )

        missing_optional: list[str] = []
        if quote is None:
            missing_optional.append("quoted_price_per_maund")

        req = ParsedFarmerRequest(
            crop=crop,
            quantity_maunds=float(qty_maunds),
            district=district,
            quoted_price_per_maund=quote,
            crop_stage=str(stage),
            confidence=conf,
            language_detected=extracted.get("language_detected"),
            raw_transcript=extracted.get("raw_transcript"),
        )
        msg = "Request understood."
        if missing_optional:
            msg = (
                "Request understood. Optional: quoted price per maund / "
                "اگر ریٹ معلوم ہو تو بتائیں۔"
            )
        if extra_message:
            msg = f"{msg} {extra_message}".strip()
        return ParseOutcome(
            status="ok",
            request=req,
            missing_fields=missing_optional,
            message=msg,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_outcome failed: %s", exc)
        return ParseOutcome(
            status="failed",
            request=None,
            missing_fields=REQUIRED_ORDER.copy(),
            message="Could not understand the request. Please try again.",
        )


def parse_request(
    text: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    *,
    use_llm: bool = True,
) -> ParseOutcome:
    """Parse spoken/typed farmer sale message into ParseOutcome. Never raises."""
    try:
        if audio_bytes is not None:
            if not use_llm:
                return ParseOutcome(
                    status="failed",
                    request=None,
                    missing_fields=REQUIRED_ORDER.copy(),
                    message=(
                        "Please type your crop, quantity in maunds, and district / "
                        "براہ کرم فصل، من میں مقدار اور ضلع لکھ کر بھیجیں۔"
                    ),
                )
            try:
                extracted = extract_from_audio(audio_bytes, mime_type or "")
                return build_outcome(extracted)
            except LLMError as exc:
                logger.warning("Audio LLM failed: %s", exc)
                if exc.cause == "quota":
                    msg = (
                        "Voice audio needs OpenRouter credits (≥ $0.50) or a clear "
                        "WAV mic recording. Please use the Typed tab / "
                        "آڈیو کے لیے کریڈٹ یا واضح ریکارڈنگ درکار ہے۔ براہ کرم Typed ٹیب استعمال کریں۔"
                    )
                else:
                    msg = (
                        "Could not understand the audio. Please type your crop, "
                        "quantity in maunds, and district / "
                        "آڈیو سمجھ نہیں آئی۔ براہ کرم فصل، من میں مقدار اور ضلع لکھ کر بھیجیں۔"
                    )
                return ParseOutcome(
                    status="failed",
                    request=None,
                    missing_fields=REQUIRED_ORDER.copy(),
                    message=msg,
                )

        if text is None or not str(text).strip():
            return ParseOutcome(
                status="needs_clarification",
                request=None,
                missing_fields=REQUIRED_ORDER.copy(),
                message=_clarification_message(REQUIRED_ORDER.copy()),
            )

        extracted: Optional[dict[str, Any]] = None
        extra = ""
        if use_llm:
            try:
                extracted = extract_from_text(text)
            except LLMError as exc:
                logger.warning("Text LLM failed, using fallback: %s", exc)
                extracted = None

        if extracted is None:
            extracted = rule_based_extract(text)
            conf = extracted.get("confidence")
            try:
                conf_f = float(conf) if conf is not None else 0.5
            except (TypeError, ValueError):
                conf_f = 0.5
            extracted["confidence"] = min(conf_f, 0.6)
            if not extracted.get("raw_transcript"):
                extracted["raw_transcript"] = text
            extra = _BASIC_NOTE
        else:
            if not extracted.get("raw_transcript"):
                extracted["raw_transcript"] = text

        return build_outcome(extracted, extra_message=extra)
    except Exception as exc:
        logger.exception("parse_request failed: %s", exc)
        return ParseOutcome(
            status="failed",
            request=None,
            missing_fields=REQUIRED_ORDER.copy(),
            message=(
                "Something went wrong. Please type crop, maunds, and district / "
                "مسئلہ پیش آیا۔ براہ کرم فصل، من اور ضلع لکھیں۔"
            ),
        )

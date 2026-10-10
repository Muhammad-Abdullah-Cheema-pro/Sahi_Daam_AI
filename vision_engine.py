"""MusamGuard vision: leaf/canopy phenology + disease triage (Gemini multimodal)."""

from __future__ import annotations

import json
import logging
from typing import Any

from config import GEMINI_HTTP_TIMEOUT_MS, MAX_VISION_UPLOAD_BYTES, VISION_MODEL
from llm_client import (
    openrouter_vision_json,
    resolve_api_key,
    resolve_model_name,
    resolve_provider,
)
from schema import DiseaseTriageResult, PhenologyStage, VisionTriageResult

logger = logging.getLogger(__name__)

_FALLBACK_DISEASE = DiseaseTriageResult(
    detected_disease="Unknown / needs manual check",
    confidence=0.0,
    symptoms_summary="Photo triage unavailable — please select stage and disease manually.",
    is_healthy=True,
    severity="none",
)


def _fallback(
    reason: str,
    stage: PhenologyStage = PhenologyStage.READY_TO_HARVEST,
) -> VisionTriageResult:
    return VisionTriageResult(
        phenology_stage=stage,
        disease_triage=_FALLBACK_DISEASE.model_copy(
            update={"symptoms_summary": reason}
        ),
        image_quality_ok=False,
        quality_issue_reason=reason,
    )


def _parse_stage(raw: Any) -> PhenologyStage:
    text = str(raw or "").strip()
    for stage in PhenologyStage:
        if stage.value.lower() == text.lower():
            return stage
    aliases = {
        "flowering": PhenologyStage.EARLY_FLOWERING,
        "early flowering": PhenologyStage.EARLY_FLOWERING,
        "grain filling": PhenologyStage.GRAIN_FILLING,
        "grain-filling": PhenologyStage.GRAIN_FILLING,
        "nearly ready": PhenologyStage.NEARLY_READY,
        "ready": PhenologyStage.READY_TO_HARVEST,
        "harvested": PhenologyStage.HARVESTED_NOT_SOLD,
        "growing": PhenologyStage.GROWING,
    }
    return aliases.get(text.lower(), PhenologyStage.READY_TO_HARVEST)


def _vision_prompt(crop_name: str) -> str:
    return (
        f"Inspect this crop leaf/canopy photo for {crop_name}.\n"
        "1. Check image quality (blurriness/darkness).\n"
        "2. Identify the exact phenological stage "
        "('Growing', 'Early Flowering', 'Grain-Filling', 'Nearly ready', "
        "'Ready to harvest', 'Harvested, not sold').\n"
        "3. Conduct leaf-disease triage: identify visual symptoms or known diseases "
        "(e.g., Rust, Blight, Leaf Spot, Aflatoxin risk, or Healthy).\n"
        "Return strictly raw valid JSON with keys: "
        "phenology_stage (string), "
        "disease_triage (object with detected_disease, confidence, symptoms_summary, "
        "is_healthy, severity), "
        "image_quality_ok (bool), quality_issue_reason (string or null)."
    )


def _parse_vision_json(text: str) -> VisionTriageResult:
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(ln for ln in lines if not ln.strip().startswith("```")).strip()
    data = json.loads(text)
    triage_raw = data.get("disease_triage") or {}
    disease = DiseaseTriageResult(
        detected_disease=str(triage_raw.get("detected_disease") or "Healthy"),
        confidence=float(triage_raw.get("confidence") or 0.0),
        symptoms_summary=str(
            triage_raw.get("symptoms_summary") or "No symptoms summarised."
        ),
        is_healthy=bool(triage_raw.get("is_healthy", True)),
        severity=str(triage_raw.get("severity") or "none"),
    )
    quality_ok = bool(data.get("image_quality_ok", True))
    reason = data.get("quality_issue_reason")
    result = VisionTriageResult(
        phenology_stage=_parse_stage(data.get("phenology_stage")),
        disease_triage=disease,
        image_quality_ok=quality_ok,
        quality_issue_reason=str(reason) if reason else None,
    )
    if not quality_ok:
        result = result.model_copy(
            update={
                "quality_issue_reason": result.quality_issue_reason
                or "Image quality flagged — please confirm stage/disease manually."
            }
        )
    return result


def analyze_crop_image(image_bytes: bytes, crop_name: str) -> VisionTriageResult:
    """Inspect a crop leaf/canopy photo. Never raises — falls back for UI override."""
    try:
        if not image_bytes:
            return _fallback("Empty image.")
        if len(image_bytes) > MAX_VISION_UPLOAD_BYTES:
            return _fallback("Image too large (max 5 MB).")

        key = resolve_api_key()
        if not key:
            return _fallback(
                "No GEMINI_API_KEY / OPENROUTER_API_KEY — use manual stage/disease selectors."
            )

        prompt = _vision_prompt(crop_name)
        mime = "image/jpeg"
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"

        provider = resolve_provider()
        if provider == "openrouter":
            logger.info("Vision model used (OpenRouter): %s", resolve_model_name())
            text = openrouter_vision_json(prompt, image_bytes, mime)
            return _parse_vision_json(text)

        from google import genai
        from google.genai import types

        vision_model = resolve_model_name() or VISION_MODEL
        client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS),
        )
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
        cfg = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
        )
        logger.info("Vision model used: %s", vision_model)
        resp = client.models.generate_content(
            model=vision_model,
            contents=[prompt, part],
            config=cfg,
        )
        text = (getattr(resp, "text", None) or "").strip()
        if not text:
            return _fallback("Empty vision model response.")
        return _parse_vision_json(text)
    except Exception as exc:
        logger.warning("analyze_crop_image failed: %s", exc)
        return _fallback(
            f"Vision unavailable ({type(exc).__name__}). Use manual selectors."
        )

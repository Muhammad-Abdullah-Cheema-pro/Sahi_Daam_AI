"""Sahi Daam AI — Streamlit voice-first mandi + crop-health advisor."""

from __future__ import annotations

import hashlib
import html
import time
from datetime import date
from typing import Any, Optional

import streamlit as st
from pydantic import ValidationError

from advisory_engine import CROP_STAGES, normalize_crop_stage
from analysis.analyze import analyze
from config import (
    CONFIDENCE_WARN,
    MAX_AI_CALLS_PER_SESSION,
    STALE_DATA_DAYS,
)
from geo import COORDS
from llm_client import (
    last_error_cause,
    last_model_used,
    resolve_api_key,
    resolve_model_name,
    resolve_provider,
)
from schema import DiseaseTriageResult, EnhancedHarvestAdvisory, ParsedFarmerRequest
from ui_helpers import (
    STATUS_STYLE,
    WHOLESALE_CAPTION,
    band_caption,
    build_urdu_summary,
    format_city_rows,
    verdict_sentence,
)
from voice_engine import (
    generate_urdu_audio,
    mime_from_upload,
    parse_audio_to_request,
    parse_text_to_request,
    validate_audio,
)

CROPS = ["Wheat", "Tomato", "Potato", "Onion"]
DISTRICTS = sorted(COORDS.keys())
SAMPLE_CASE_IDS = (1, 5, 11)  # tests/voice_cases.csv
DISEASE_OPTIONS = [
    "— From photo / Healthy —",
    "Healthy",
    "Rust",
    "Blight",
    "Leaf Spot",
    "Aflatoxin risk",
    "Other / Unknown",
]

APP_DISCLAIMER = (
    "Advice only. Non-chemical/standard extension practice recommendations "
    "based on district-level forecasts."
)


def _esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=False)


@st.cache_resource(show_spinner=False)
def _warm_engines() -> dict[str, float]:
    """Cold-start warm-up: load price band path once per process."""
    t0 = time.perf_counter()
    try:
        from model.price_band import get_band

        get_band("Lahore", "Tomato")
    except Exception:
        pass
    return {"warm_s": time.perf_counter() - t0}


# Visual tokens (text label always present — never colour alone)
_VERDICT_THEME = {
    "Fair": {"bg": "#143A2B", "border": "#4CAF6A", "ink": "#D7F2DC", "accent": "#5EDB8A"},
    "Low": {"bg": "#3A2E14", "border": "#E0C070", "ink": "#F7E8B8", "accent": "#F2CF6E"},
    "Very low": {"bg": "#3C1C1C", "border": "#E57373", "ink": "#FFD9D9", "accent": "#FF8A8A"},
    "Unable to assess": {"bg": "#233038", "border": "#90A4AE", "ink": "#DCE5EA", "accent": "#B0BEC5"},
}
_RISK_THEME = {
    "High": {"bg": "#3C1C1C", "border": "#E57373", "ink": "#FFD9D9", "accent": "#FF8A8A"},
    "Medium": {"bg": "#3A2E14", "border": "#E0C070", "ink": "#F7E8B8", "accent": "#F2CF6E"},
    "Low": {"bg": "#143A2B", "border": "#4CAF6A", "ink": "#D7F2DC", "accent": "#5EDB8A"},
}


def _inject_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Atkinson+Hyperlegible:wght@400;700&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap');

:root {
  --sd-forest: #1E6B4F;
  --sd-forest-deep: #071A14;
  --sd-wheat: #C4A35A;
  --sd-wheat-bright: #E0C070;
  --sd-ink: #E8F0EB;
  --sd-muted: #9BB0A4;
  --sd-surface: rgba(18, 36, 30, 0.92);
  --sd-surface-2: rgba(12, 28, 22, 0.78);
  --sd-line: rgba(196, 163, 90, 0.18);
  --sd-radius: 18px;
}

html, body, [class*="css"] {
  font-family: "Atkinson Hyperlegible", "Segoe UI", sans-serif;
  color: var(--sd-ink);
}

.stApp {
  background:
    radial-gradient(1100px 560px at 8% -8%, rgba(196, 163, 90, 0.14), transparent 55%),
    radial-gradient(900px 500px at 100% 0%, rgba(30, 107, 79, 0.22), transparent 52%),
    linear-gradient(165deg, #0B1612 0%, #102019 45%, #0E1A16 100%);
  background-attachment: fixed;
  color: var(--sd-ink);
}
.stApp::before {
  content: "";
  position: fixed; inset: 0; pointer-events: none; opacity: 0.06; z-index: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80'%3E%3Cpath d='M0 40h80M40 0v80' stroke='%23C4A35A' stroke-width='1' fill='none'/%3E%3C/svg%3E");
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"], .main { background: transparent !important; }
.block-container { max-width: 1120px; padding-top: 1.1rem; padding-bottom: 3rem; position: relative; z-index: 1; }
#MainMenu, footer { visibility: hidden; }
div[data-testid="stToolbar"] { display: none; }

/* Hero */
.sd-hero {
  position: relative; overflow: hidden; border-radius: 28px;
  padding: 2rem 1.8rem 1.6rem; margin: 0 0 1.1rem 0; color: #F7FBF8;
  background:
    linear-gradient(135deg, rgba(10, 42, 32, 0.96) 0%, rgba(15, 61, 46, 0.9) 55%, rgba(36, 72, 48, 0.92) 100%),
    radial-gradient(circle at 80% 20%, rgba(224, 192, 112, 0.35), transparent 40%);
  box-shadow: 0 18px 40px rgba(5, 20, 15, 0.45);
  border: 1px solid rgba(224, 192, 112, 0.18);
  animation: sd-rise 0.7s ease-out both;
}
.sd-hero::after {
  content: ""; position: absolute; right: -40px; bottom: -50px; width: 260px; height: 260px;
  border-radius: 50%; background: radial-gradient(circle, rgba(196, 163, 90, 0.35), transparent 65%);
  animation: sd-drift 8s ease-in-out infinite alternate;
}
.sd-kicker { display:inline-flex; gap:0.5rem; align-items:center; font-size: 0.76rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--sd-wheat-bright); margin-bottom: 0.6rem; font-weight: 700; }
.sd-kicker .dot { width: 8px; height: 8px; border-radius: 50%; background: #5EDB8A; box-shadow: 0 0 0 4px rgba(94,219,138,0.18); }
.sd-brand { font-family: "Bricolage Grotesque", Georgia, serif; font-weight: 800; font-size: clamp(2.2rem, 5vw, 3.1rem); line-height: 1.02; margin: 0 0 0.5rem 0; letter-spacing: -0.02em; }
.sd-brand span { color: var(--sd-wheat-bright); }
.sd-tagline { font-size: 1.2rem; line-height: 1.35; max-width: 34ch; margin: 0 0 0.6rem 0; color: #E7F0EA; font-weight: 700; }
.sd-sub { margin: 0; font-size: 0.98rem; line-height: 1.5; color: rgba(231, 240, 234, 0.86); max-width: 58ch; }
.sd-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.7rem; margin-top: 1.3rem; position: relative; z-index: 1; }
.sd-stat { background: rgba(7, 26, 20, 0.55); border: 1px solid rgba(224, 192, 112, 0.22); border-radius: 14px; padding: 0.7rem 0.85rem; }
.sd-stat b { display: block; font-family: "Bricolage Grotesque", serif; font-size: 1.35rem; color: #FFF; line-height: 1.1; }
.sd-stat small { color: rgba(231, 240, 234, 0.75); font-size: 0.8rem; }

/* Stepper */
.sd-stepper { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin: 0.4rem 0 1.2rem; }
.sd-stepper .s { display: flex; align-items: center; gap: 0.55rem; padding: 0.6rem 0.75rem; border-radius: 12px; background: var(--sd-surface-2); border: 1px solid var(--sd-line); color: var(--sd-muted); font-size: 0.9rem; font-weight: 700; }
.sd-stepper .s i { display: inline-grid; place-items: center; width: 1.55rem; height: 1.55rem; border-radius: 999px; background: rgba(155,176,164,0.18); font-style: normal; font-size: 0.8rem; color: var(--sd-ink); }
.sd-stepper .s.done { color: var(--sd-ink); border-color: rgba(94,219,138,0.35); }
.sd-stepper .s.done i { background: #1E6B4F; color: #fff; }
.sd-stepper .s.active { color: #fff; background: linear-gradient(180deg, rgba(30,107,79,0.55), rgba(30,107,79,0.3)); border-color: var(--sd-wheat); box-shadow: 0 0 0 3px rgba(224,192,112,0.12); }
.sd-stepper .s.active i { background: var(--sd-wheat-bright); color: #0B1612; }

/* Section header */
.sd-section-head { background: var(--sd-surface); border: 1px solid var(--sd-line); border-radius: var(--sd-radius); padding: 1rem 1.15rem 0.5rem; margin: 1.1rem 0 0.6rem 0; animation: sd-rise 0.55s ease-out both; }
.sd-step { display: inline-flex; align-items: center; gap: 0.5rem; font-family: "Bricolage Grotesque", Georgia, serif; font-weight: 700; font-size: 1.3rem; color: var(--sd-wheat-bright); margin: 0 0 0.3rem 0; }
.sd-step-num { display: inline-grid; place-items: center; width: 1.7rem; height: 1.7rem; border-radius: 999px; background: var(--sd-forest); color: #F7FBF8; font-size: 0.85rem; font-weight: 800; }
.sd-hint { color: var(--sd-muted); font-size: 0.95rem; margin: 0 0 0.6rem 0; line-height: 1.4; }

/* Panels & chips */
.sd-panel { border-radius: 16px; border: 1.5px solid; padding: 1.05rem 1.15rem; margin: 0.5rem 0 0.85rem 0; animation: sd-pop 0.45s ease-out both; }
.sd-panel-title { font-family: "Bricolage Grotesque", Georgia, serif; font-size: 1.55rem; font-weight: 800; margin: 0 0 0.4rem 0; line-height: 1.15; }
.sd-panel p { margin: 0.35rem 0; font-size: 1.02rem; line-height: 1.5; }
.sd-meta { font-size: 0.88rem; color: var(--sd-muted); margin-top: 0.55rem; line-height: 1.45; }
.sd-chip { display: inline-block; padding: 0.26rem 0.7rem; border-radius: 999px; font-weight: 700; font-size: 0.85rem; border: 1.5px solid; margin: 0 0.35rem 0.35rem 0; background: #0F1F19; }

/* KPI tiles */
.sd-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin: 0.4rem 0 0.9rem; }
.sd-kpi { border-radius: 16px; padding: 0.9rem 1rem; background: var(--sd-surface); border: 1px solid var(--sd-line); border-left: 5px solid var(--kpi, var(--sd-wheat)); animation: sd-pop 0.45s ease-out both; }
.sd-kpi small { display: block; color: var(--sd-muted); font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 700; }
.sd-kpi b { display: block; font-family: "Bricolage Grotesque", serif; font-size: 1.45rem; margin-top: 0.2rem; color: #fff; line-height: 1.15; }
.sd-kpi span { display: block; color: var(--sd-ink); font-size: 0.86rem; margin-top: 0.2rem; opacity: 0.85; }

/* Price band visual */
.sd-band { margin: 0.75rem 0 0.2rem; }
.sd-band .track { position: relative; height: 14px; border-radius: 999px; background: linear-gradient(90deg, #E57373 0%, #E0C070 35%, #4CAF6A 50%, #E0C070 65%, #E57373 100%); opacity: 0.9; }
.sd-band .range { position: absolute; top: -4px; height: 22px; border-radius: 999px; border: 2px solid rgba(255,255,255,0.75); background: rgba(94,219,138,0.18); }
.sd-band .marker { position: absolute; top: -10px; width: 4px; height: 34px; background: #fff; border-radius: 2px; box-shadow: 0 0 0 3px rgba(0,0,0,0.35); }
.sd-band .labels { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--sd-muted); margin-top: 0.55rem; }
.sd-band .quote-label { font-size: 0.9rem; color: #fff; font-weight: 700; margin-top: 0.3rem; }

/* Weather grid */
.sd-wx { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.6rem; margin: 0.6rem 0 0.2rem; }
.sd-wx .t { background: rgba(7, 26, 20, 0.55); border: 1px solid var(--sd-line); border-radius: 12px; padding: 0.65rem 0.75rem; }
.sd-wx .t small { display: block; color: var(--sd-muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; }
.sd-wx .t b { display: block; font-family: "Bricolage Grotesque", serif; font-size: 1.25rem; color: #fff; margin-top: 0.15rem; }

/* Protocol steps */
.sd-steps { counter-reset: step; margin: 0.4rem 0 0; padding: 0; list-style: none; }
.sd-steps li { position: relative; padding: 0.45rem 0 0.45rem 2.4rem; font-size: 1.02rem; line-height: 1.5; }
.sd-steps li::before { counter-increment: step; content: counter(step); position: absolute; left: 0; top: 0.45rem; width: 1.7rem; height: 1.7rem; border-radius: 999px; display: grid; place-items: center; background: var(--sd-wheat-bright); color: #0B1612; font-weight: 800; font-size: 0.85rem; }

/* Urdu */
.sd-quote { font-family: "Noto Nastaliq Urdu", "Jameel Noori Nastaleeq", serif; font-size: 1.25rem; line-height: 2.1; direction: rtl; text-align: right; background: linear-gradient(180deg, #162820, #12221C); border-right: 4px solid var(--sd-wheat); border-radius: 12px; padding: 1rem 1.1rem; margin: 0.6rem 0; color: var(--sd-ink); }

.sd-callout { border-radius: 14px; padding: 0.85rem 1rem; background: rgba(30,107,79,0.22); border: 1px solid rgba(94,219,138,0.35); margin: 0.4rem 0 0.8rem; }
.sd-callout b { color: #fff; }
.sd-footer-note { text-align: center; color: var(--sd-muted); font-size: 0.85rem; margin-top: 1.6rem; line-height: 1.6; }

/* Streamlit controls */
.stButton > button, div[data-testid="stFormSubmitButton"] > button {
  background: linear-gradient(180deg, #187553, var(--sd-forest)) !important; color: #F7FBF8 !important;
  border: 1px solid rgba(224,192,112,0.35) !important; border-radius: 14px !important; font-weight: 700 !important;
  font-size: 1.02rem !important; padding: 0.6rem 1.2rem !important; min-height: 2.9rem !important;
  box-shadow: 0 8px 18px rgba(5, 20, 15, 0.35) !important; transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover { transform: translateY(-1px); box-shadow: 0 12px 22px rgba(5, 20, 15, 0.45) !important; }
.stButton > button:focus { outline: 3px solid var(--sd-wheat) !important; }
div[data-testid="stForm"] { border: 1px solid var(--sd-line); border-radius: 16px; padding: 0.6rem 0.8rem 0.9rem; background: var(--sd-surface-2); }
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; background: transparent; }
.stTabs [data-baseweb="tab"] { border-radius: 12px; padding: 0.55rem 1rem; font-weight: 700; background: rgba(30, 107, 79, 0.22); color: var(--sd-ink); }
.stTabs [aria-selected="true"] { background: var(--sd-forest) !important; color: #F7FBF8 !important; }
label, .stSelectbox label, .stNumberInput label, .stTextArea label { font-weight: 700 !important; font-size: 0.98rem !important; color: var(--sd-wheat-bright) !important; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid var(--sd-line); }
.stTextArea textarea, .stTextInput input, div[data-baseweb="select"] > div, .stNumberInput input { background-color: #12221C !important; color: var(--sd-ink) !important; border-color: rgba(196, 163, 90, 0.28) !important; }
div[data-testid="stExpander"] { background: var(--sd-surface); border: 1px solid var(--sd-line); border-radius: 12px; }
[data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"] { color: var(--sd-ink); }
section[data-testid="stSidebar"] { background: #0B1612; border-right: 1px solid var(--sd-line); }
section[data-testid="stSidebar"] * { color: var(--sd-ink); }
div[data-testid="stMetric"] { background: var(--sd-surface); border: 1px solid var(--sd-line); border-radius: 12px; padding: 0.6rem 0.8rem; }

@keyframes sd-rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
@keyframes sd-pop { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
@keyframes sd-drift { from { transform: translate(0, 0); } to { transform: translate(-18px, -10px); } }

@media (max-width: 900px) {
  .sd-stats, .sd-kpis, .sd-wx { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sd-stepper { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .sd-hero { padding: 1.5rem 1.1rem 1.3rem; border-radius: 22px; }
  .sd-tagline { font-size: 1.05rem; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _hero() -> None:
    st.markdown(
        f"""
<div class="sd-hero">
  <div class="sd-kicker"><span class="dot"></span> AICON'26 · Agricultural Operations · MusamGuard inside</div>
  <h1 class="sd-brand">Sahi <span>Daam</span> AI</h1>
  <p class="sd-tagline">Fair price. Crop-health triage. 48-hour weather protocol. One voice note.</p>
  <p class="sd-sub">
    Speak or type in Urdu, Roman Urdu, or English. We check the broker's quote against real
    AMIS wholesale ranges, read your leaf photo, match the crop stage to the Open-Meteo forecast,
    and tell you — in Urdu audio — what to do next.
  </p>
  <div class="sd-stats">
    <div class="sd-stat"><b>{len(DISTRICTS)}</b><small>Punjab mandis tracked</small></div>
    <div class="sd-stat"><b>{len(CROPS)}</b><small>Crops · AMIS wholesale</small></div>
    <div class="sd-stat"><b>48 h</b><small>Forecast × phenology rules</small></div>
    <div class="sd-stat"><b>اردو</b><small>Voice in &amp; voice out</small></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _stepper(active: int) -> None:
    labels = ["Speak or type", "Review", "Confirm", "Verdict & plan"]
    cells = []
    for i, label in enumerate(labels, start=1):
        cls = "done" if i < active else ("active" if i == active else "")
        mark = "✓" if i < active else str(i)
        cells.append(f'<div class="s {cls}"><i>{mark}</i>{label}</div>')
    st.markdown(f'<div class="sd-stepper">{"".join(cells)}</div>', unsafe_allow_html=True)


def _section_header(num: str, title: str, hint: str) -> None:
    """Visual step header only — do not wrap Streamlit widgets in open HTML tags."""
    st.markdown(
        f"""
<div class="sd-section-head">
  <div class="sd-step"><span class="sd-step-num">{num}</span> {title}</div>
  <p class="sd-hint">{hint}</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "parse_outcome": None,
        "form_draft": None,
        "analysis_result": None,
        "audio_cache": {},
        "stage_defaulted": False,
        "ai_calls": 0,
        "ai_mode_label": None,
        "typed_text": "",
        "cold_s": None,
        "warm_s": None,
        "crop_photo_bytes": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_session() -> None:
    for k in (
        "parse_outcome",
        "form_draft",
        "analysis_result",
        "crop_photo_bytes",
        "ai_mode_label",
    ):
        st.session_state[k] = None
    st.session_state.typed_text = ""
    st.session_state.stage_defaulted = False


def _ai_budget_remaining() -> int:
    return max(0, MAX_AI_CALLS_PER_SESSION - int(st.session_state.get("ai_calls") or 0))


def _bump_ai_call() -> None:
    st.session_state.ai_calls = int(st.session_state.get("ai_calls") or 0) + 1


def _set_ai_mode(*, live: bool, reason: str = "") -> None:
    if live:
        model = last_model_used() or resolve_model_name()
        st.session_state.ai_mode_label = f"AI mode: live ({model})"
    else:
        st.session_state.ai_mode_label = (
            f"AI mode: basic offline parser ({reason or 'no live AI'})"
        )


def _load_sample_rows() -> list[dict[str, str]]:
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parent / "tests" / "voice_cases.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        try:
            rid = int(r.get("id") or 0)
        except ValueError:
            continue
        if rid in SAMPLE_CASE_IDS:
            out.append(r)
    return out


def _price_data_as_of() -> str:
    try:
        from data.store import load_prices

        pdf = load_prices()
        if pdf is not None and not pdf.empty:
            return str(pdf["date"].max())
    except Exception:
        pass
    return "unknown"


def _clear_result() -> None:
    st.session_state.analysis_result = None


def _disease_override_from_label(label: str) -> Optional[DiseaseTriageResult]:
    if not label or label.startswith("—"):
        return None
    healthy = label == "Healthy"
    return DiseaseTriageResult(
        detected_disease=label,
        confidence=1.0,
        symptoms_summary=(
            "Manual override selected by farmer."
            if not healthy
            else "Farmer confirmed healthy canopy/leaves."
        ),
        is_healthy=healthy,
        severity="none" if healthy else "moderate",
    )


def _mime_for_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".mp3"):
        return "audio/mpeg"
    return "audio/wav"


def _draft_from_outcome(outcome) -> dict[str, Any]:
    req = outcome.request
    stage, defaulted = normalize_crop_stage(req.crop_stage if req else None)
    st.session_state.stage_defaulted = defaulted
    return {
        "crop": (req.crop if req and req.crop in CROPS else CROPS[0]),
        "quantity_maunds": float(req.quantity_maunds) if req else 1.0,
        "district": req.district if req and req.district in DISTRICTS else "",
        "quoted_price_per_maund": (req.quoted_price_per_maund if req else None),
        "crop_stage": stage,
        "confidence": req.confidence if req else 0.5,
        "language_detected": req.language_detected if req else None,
        "raw_transcript": req.raw_transcript if req else outcome.message,
        "no_quote": req is None or req.quoted_price_per_maund is None,
    }


def _process_text(text: str) -> None:
    _clear_result()
    use_llm = _ai_budget_remaining() > 0 and bool(resolve_api_key())
    if not use_llm:
        reason = "session AI limit reached" if _ai_budget_remaining() <= 0 else "no API key"
        st.info(
            "Using basic offline parser — typed input always works without an API key."
            if reason == "no API key"
            else (
                f"Session AI limit ({MAX_AI_CALLS_PER_SESSION} calls) reached. "
                "Voice is disabled; typed input uses the offline parser."
            )
        )
    try:
        if use_llm:
            _bump_ai_call()
        outcome = parse_text_to_request(text, use_llm=use_llm)
        conf = (
            float(getattr(outcome.request, "confidence", 1.0) or 1.0)
            if outcome.request
            else 0.5
        )
        if use_llm and (last_error_cause() is not None or conf <= 0.6):
            if last_error_cause() is not None:
                cause = last_error_cause()
                st.warning(f"Live AI unavailable ({cause}). Showing Basic mode result.")
                _set_ai_mode(live=False, reason=str(cause))
            else:
                _set_ai_mode(live=True)
        elif use_llm:
            _set_ai_mode(live=True)
        else:
            _set_ai_mode(live=False, reason="offline")
        if not use_llm and outcome.request is not None:
            st.caption("Basic mode (offline parser)")
    except Exception as exc:
        st.error(
            "Could not process text. Try again or use the confirmation form. "
            f"({type(exc).__name__})"
        )
        _set_ai_mode(live=False, reason=type(exc).__name__)
        return
    st.session_state.parse_outcome = outcome
    st.session_state.form_draft = _draft_from_outcome(outcome)


def _process_audio(audio_bytes: bytes, mime: str) -> None:
    _clear_result()
    if _ai_budget_remaining() <= 0:
        st.warning(
            f"Session AI limit ({MAX_AI_CALLS_PER_SESSION} calls) reached. "
            "Voice is disabled for this session — please use the Typed tab."
        )
        return
    if not resolve_api_key():
        st.warning(
            "Voice needs an API key (OPENROUTER_API_KEY or GEMINI_API_KEY). "
            "Please use the Typed tab (works offline with the basic parser)."
        )
        return
    err = validate_audio(audio_bytes, mime)
    if err:
        st.warning(err)
        return
    try:
        _bump_ai_call()
        outcome = parse_audio_to_request(audio_bytes, mime_type=mime, use_llm=True)
        if last_error_cause() is not None and (outcome is None or outcome.status == "failed"):
            cause = last_error_cause()
            if cause == "quota":
                st.error(
                    "Voice needs OpenRouter audio credits (≥ $0.50), or a clear "
                    "WAV mic recording (free speech-to-text). "
                    "Typed tab works with your current key."
                )
            else:
                st.error(f"Voice processing failed ({cause}). Please use the Typed tab.")
            _set_ai_mode(live=False, reason=str(cause))
        elif outcome.status == "ok":
            _set_ai_mode(live=True)
        else:
            _set_ai_mode(live=False, reason=outcome.status)
    except Exception as exc:
        st.error(f"Voice processing failed. Please use the Typed tab. ({type(exc).__name__})")
        _set_ai_mode(live=False, reason=type(exc).__name__)
        return
    st.session_state.parse_outcome = outcome
    st.session_state.form_draft = _draft_from_outcome(outcome)


# --------------------------------------------------------------------------- UI


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🌾 Sahi Daam AI")
        st.caption("Voice-first fair-price, harvest-or-hold & crop-health advisor.")

        provider = resolve_provider()
        key_ok = bool(resolve_api_key())
        model = resolve_model_name()
        st.markdown("**AI engine**")
        st.markdown(
            f"- Provider: `{provider}`\n"
            f"- Model: `{model}`\n"
            f"- Key: {'✅ loaded' if key_ok else '⚠️ missing (offline parser)'}\n"
            f"- Calls left: **{_ai_budget_remaining()} / {MAX_AI_CALLS_PER_SESSION}**"
        )

        st.markdown("**Data sources**")
        st.markdown(
            f"- AMIS Punjab wholesale (as of {_price_data_as_of()})\n"
            "- Open-Meteo 72 h hourly forecast · 5 s timeout · SQLite cache\n"
            "- Gemini multimodal for leaf triage (manual override always available)"
        )

        st.markdown("**How it works**")
        st.markdown(
            "1. Say what you have and the quote you got\n"
            "2. Confirm crop, maunds, district, stage\n"
            "3. Optional: leaf photo for disease + stage\n"
            "4. Get verdict, 48 h risk, mitigation, best mandi — plus Urdu audio"
        )

        st.divider()
        if st.button("↺ Start over", key="reset_btn", width="stretch"):
            _reset_session()
            st.rerun()
        st.caption("Maund = 100 kg ÷ 2.5 · " + WHOLESALE_CAPTION)


def _render_input() -> None:
    _section_header(
        "1",
        "Tell us about your crop",
        "Voice or text in Roman Urdu / Urdu / English. Nothing is analysed until you confirm.",
    )
    samples = _load_sample_rows()
    if samples:
        with st.expander("Try a sample (real AMIS data)"):
            st.caption(f"Prices as of {_price_data_as_of()}.")
            cols = st.columns(len(samples))
            for col, r in zip(cols, samples):
                label = (r.get("spoken_text") or "")[:60]
                with col:
                    if st.button(f"▶ {label}…", key=f"sample_{r.get('id')}", width="stretch"):
                        st.session_state.typed_text = r.get("spoken_text") or ""

    tab_text, tab_voice = st.tabs(["⌨️ Typed", "🎙️ Voice"])

    with tab_text:
        text = st.text_area(
            "Type your message",
            placeholder="40 maund tamatar hain Okara mein, broker 2800 de raha hai",
            height=120,
            key="typed_text",
        )
        if st.button("Process text", key="process_text", width="stretch"):
            with st.spinner("Reading…"):
                typed = (text or st.session_state.get("typed_text") or "").strip()
                if not typed:
                    st.warning("Please type a message.")
                else:
                    _process_text(typed)

    with tab_voice:
        if _ai_budget_remaining() <= 0:
            st.warning(
                f"Voice disabled — session AI limit ({MAX_AI_CALLS_PER_SESSION}) reached. "
                "Use Typed input (offline parser)."
            )
        st.caption(
            "Best results: browser mic (WAV). Short, clear sentence — crop, maunds, "
            "district, broker quote."
        )
        recorded = None
        if hasattr(st, "audio_input"):
            recorded = st.audio_input("Record a short message (HTTPS / localhost)")
        uploaded = st.file_uploader("…or upload WAV / MP3 (max 5 MB)", type=["wav", "mp3"])
        if st.button("Process voice", key="process_voice", width="stretch"):
            with st.spinner("Listening…"):
                if recorded is not None:
                    _process_audio(recorded.getvalue(), mime_from_upload(recorded, "audio/wav"))
                elif uploaded is not None:
                    _process_audio(
                        uploaded.getvalue(),
                        mime_from_upload(uploaded, _mime_for_name(uploaded.name)),
                    )
                else:
                    st.warning("Please record or upload audio first.")


def _render_parse_feedback() -> None:
    outcome = st.session_state.parse_outcome
    if outcome is None:
        return
    _section_header("2", "What we understood", "Check this — you can fix everything in step 3.")
    if outcome.status == "failed":
        st.error(outcome.message)
    elif outcome.status == "needs_clarification":
        st.warning(outcome.message)
        st.caption(f"Still needed: {', '.join(outcome.missing_fields)}")
    else:
        st.success("Parsed — please confirm the details below.")

    draft = st.session_state.form_draft or {}
    if draft.get("raw_transcript"):
        st.markdown(
            f'<div class="sd-callout"><b>What I heard:</b> {_esc(draft["raw_transcript"])}</div>',
            unsafe_allow_html=True,
        )
    bits = []
    if draft.get("language_detected"):
        bits.append(f"Language: {draft['language_detected']}")
    conf = float(draft.get("confidence") or 0.5)
    bits.append(f"Confidence: {conf:.0%}")
    st.caption(" · ".join(bits))
    if conf < CONFIDENCE_WARN:
        st.warning("Low confidence — please check every field carefully.")


def _render_confirmation_form() -> None:
    outcome = st.session_state.parse_outcome
    if outcome is None and st.session_state.form_draft is None:
        return
    if st.session_state.form_draft is None:
        st.session_state.form_draft = _draft_from_outcome(
            outcome or type("O", (), {"request": None, "message": "", "status": "failed"})()
        )

    draft = st.session_state.form_draft
    _section_header(
        "3",
        "Confirm & get verdict",
        "Edit any field, add an optional leaf photo, then run the full analysis.",
    )
    if st.session_state.stage_defaulted:
        st.caption("Crop stage was not clear — defaulted to “Ready to harvest”.")

    with st.expander("📷 Crop Health & Weather Triage — add a leaf / canopy photo (optional)"):
        st.caption(
            "Photo gives phenology stage + leaf-disease triage. Dark or blurry? "
            "Use the manual overrides in the form."
        )
        pt_upload, pt_cam = st.tabs(["Upload", "Camera"])
        photo_bytes: Optional[bytes] = None
        with pt_upload:
            uploaded_img = st.file_uploader(
                "Leaf / canopy photo", type=["jpg", "jpeg", "png", "webp"], key="crop_upload"
            )
            if uploaded_img is not None:
                photo_bytes = uploaded_img.getvalue()
        with pt_cam:
            if hasattr(st, "camera_input"):
                cam = st.camera_input("Take a photo", key="crop_camera")
                if cam is not None:
                    photo_bytes = cam.getvalue()
        if photo_bytes:
            st.session_state.crop_photo_bytes = photo_bytes
        if st.session_state.get("crop_photo_bytes"):
            c_img, c_txt = st.columns([1, 2])
            with c_img:
                st.image(st.session_state.crop_photo_bytes, width=200)
            with c_txt:
                st.success("Photo attached — vision triage runs on confirm.")
                if st.button("Remove photo", key="rm_photo"):
                    st.session_state.crop_photo_bytes = None
                    st.rerun()

    with st.form("confirm_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            crop = st.selectbox(
                "Crop", CROPS, index=CROPS.index(draft["crop"]) if draft.get("crop") in CROPS else 0
            )
            qty = st.number_input(
                "Quantity (maunds)",
                min_value=0.01,
                value=float(draft.get("quantity_maunds") or 1.0),
                step=1.0,
            )
        with c2:
            dist_options = ["— Select —"] + DISTRICTS
            dist_default = draft.get("district") or ""
            dist_index = dist_options.index(dist_default) if dist_default in dist_options else 0
            district = st.selectbox("District", dist_options, index=dist_index)
            stage = st.selectbox(
                "Phenology stage",
                CROP_STAGES,
                index=(
                    CROP_STAGES.index(draft["crop_stage"])
                    if draft.get("crop_stage") in CROP_STAGES
                    else CROP_STAGES.index("Ready to harvest")
                ),
                help="Photo-detected stage will override this when the image is clear.",
            )
        with c3:
            disease_label = st.selectbox(
                "Leaf disease (override)",
                DISEASE_OPTIONS,
                index=0,
                help="Use when photo quality is poor or vision is unavailable.",
            )
            no_quote = st.checkbox("No quote yet", value=bool(draft.get("no_quote", True)))
            quote_val = draft.get("quoted_price_per_maund")
            quote = st.number_input(
                "Broker quote (Rs / maund)",
                min_value=0.0,
                value=float(quote_val) if quote_val is not None else 0.0,
                step=50.0,
                disabled=no_quote,
            )
        if draft.get("district") and draft["district"] not in DISTRICTS:
            st.caption(
                f"Parsed district “{draft['district']}” is not in the supported Punjab list — "
                "please choose one."
            )
        submitted = st.form_submit_button("✅ Confirm & Get Verdict", width="stretch")

    if not submitted:
        return
    if district == "— Select —":
        st.error("Please select a district.")
        return

    quoted: Optional[float] = None if no_quote or quote <= 0 else float(quote)
    disease_override = _disease_override_from_label(disease_label)
    image_bytes = st.session_state.get("crop_photo_bytes")
    try:
        request = ParsedFarmerRequest(
            crop=crop,
            quantity_maunds=float(qty),
            district=district,
            quoted_price_per_maund=quoted,
            crop_stage=stage,
            confidence=float(draft.get("confidence") or 0.8),
            language_detected=draft.get("language_detected"),
            raw_transcript=draft.get("raw_transcript"),
        )
    except ValidationError as exc:
        st.error("Please fix the form fields:")
        for err in exc.errors():
            st.write(f"- {err.get('loc')}: {err.get('msg')}")
        return

    with st.spinner("Checking wholesale ranges, weather, and crop health…"):
        try:
            result = analyze(request, image_bytes=image_bytes, disease_override=disease_override)
        except Exception as exc:
            st.error(f"Unable to complete analysis ({type(exc).__name__}). Please try again.")
            return
    st.session_state.analysis_result = result
    st.session_state.form_draft = {
        **draft,
        "crop": crop,
        "quantity_maunds": qty,
        "district": district,
        "quoted_price_per_maund": quoted,
        "crop_stage": stage,
        "no_quote": quoted is None,
    }


def _tts_with_fallback(summary: str) -> Optional[bytes]:
    """gTTS with 5 s timeout; on timeout retry with a shortened summary (first 2 sentences)."""
    try:
        return generate_urdu_audio(summary)
    except Exception:
        pass
    sentences = [s.strip() for s in summary.replace("۔", "۔|").split("|") if s.strip()]
    short = " ".join(sentences[:2]).strip()
    if not short or short == summary:
        return None
    try:
        return generate_urdu_audio(short)
    except Exception:
        return None


def _band_visual(v, quote: Optional[float]) -> str:
    low, avg, high = v.predicted_low_maund, v.predicted_avg_maund, v.predicted_high_maund
    if low is None or high is None or high <= 0:
        return ""
    span_lo = low * 0.75
    span_hi = high * 1.25
    width = max(span_hi - span_lo, 1.0)

    def pct(x: float) -> float:
        return max(0.0, min(100.0, (x - span_lo) / width * 100.0))

    range_left = pct(low)
    range_w = max(pct(high) - range_left, 2.0)
    marker = ""
    quote_label = ""
    if quote is not None:
        marker = f'<div class="marker" style="left:calc({pct(quote):.1f}% - 2px);"></div>'
        quote_label = f'<div class="quote-label">Your quote: Rs {quote:,.0f} / maund</div>'
    avg_txt = f"avg {avg:,.0f}" if avg is not None else ""
    return f"""
<div class="sd-band">
  <div class="track">
    <div class="range" style="left:{range_left:.1f}%;width:{range_w:.1f}%;"></div>
    {marker}
  </div>
  <div class="labels"><span>below range</span><span>wholesale band: {low:,.0f} – {high:,.0f} ({avg_txt})</span><span>above range</span></div>
  {quote_label}
</div>
"""


def _render_results() -> None:
    result = st.session_state.analysis_result
    if result is None:
        return

    v = result.verdict
    req = result.request
    style = STATUS_STYLE.get(v.verdict_status, STATUS_STYLE["Unable to assess"])
    theme = _VERDICT_THEME.get(v.verdict_status, _VERDICT_THEME["Unable to assess"])
    adv = result.advisory
    wx = result.weather
    best = result.top_cities[0] if result.top_cities else None

    _section_header(
        "4",
        "Your result",
        f"{req.crop} · {req.quantity_maunds:.0f} maund · {req.district} · {req.crop_stage}",
    )

    # ---- KPI tiles
    quote = req.quoted_price_per_maund
    gap_txt = f"{v.percentage_gap:+.0f}% vs avg" if v.percentage_gap is not None else "no quote"
    risk = adv.weather_risk if adv else "—"
    risk_theme = _RISK_THEME.get(risk, {"accent": "#B0BEC5"})
    threat = (
        adv.weather_threat_type
        if isinstance(adv, EnhancedHarvestAdvisory) and adv.weather_threat_type != "None"
        else ("forecast unavailable" if adv is None else "no named threat")
    )
    best_txt = f"{best.city_name}" if best else "—"
    best_sub = (
        f"net Rs {best.net_price_maund:,.0f}/maund"
        + (f" · {best.net_gain_vs_quote:+,.0f} vs quote" if best and quote is not None else "")
        if best
        else "no alternates"
    )
    st.markdown(
        f"""
<div class="sd-kpis">
  <div class="sd-kpi" style="--kpi:{theme['accent']};"><small>Quote verdict</small><b>{style['emoji']} {_esc(style['label'])}</b><span>{_esc(gap_txt)}</span></div>
  <div class="sd-kpi" style="--kpi:#E0C070;"><small>Wholesale avg</small><b>{('Rs ' + format(v.predicted_avg_maund, ',.0f')) if v.predicted_avg_maund else '—'}</b><span>{_esc(v.reference_market)} · per maund</span></div>
  <div class="sd-kpi" style="--kpi:{risk_theme['accent']};"><small>48 h weather risk</small><b>{_esc(risk)}</b><span>{_esc(threat)}</span></div>
  <div class="sd-kpi" style="--kpi:#5EDB8A;"><small>Best alternate mandi</small><b>{_esc(best_txt)}</b><span>{_esc(best_sub)}</span></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns([1.15, 1])

    # ---- Verdict panel
    with col_l:
        st.markdown("##### 💰 Fair-price verdict")
        st.markdown(
            f"""
<div class="sd-panel" style="background:{theme['bg']};border-color:{theme['border']};color:{theme['ink']};">
  <div class="sd-panel-title">{style['emoji']} {_esc(style['label'])}</div>
  <p>{_esc(verdict_sentence(v))}</p>
  {_band_visual(v, quote)}
  <div class="sd-meta">{_esc(band_caption(v))}<br/>Reference market: <strong>{_esc(v.reference_market)}</strong> · {_esc(WHOLESALE_CAPTION)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        if v.data_as_of is not None:
            age = (date.today() - v.data_as_of).days
            if age > STALE_DATA_DAYS:
                st.warning(
                    f"Price data is {age} days old (as of {v.data_as_of.isoformat()}). "
                    "Wholesale ranges may be outdated."
                )

    # ---- Weather & outlook
    with col_r:
        st.markdown("##### 🌦️ 48-hour weather & harvest outlook")
        if adv is None:
            st.info("Weather forecast unavailable — harvest outlook not shown.")
        else:
            rt = _RISK_THEME.get(adv.weather_risk, _RISK_THEME["Low"])
            wx_grid = ""
            if wx is not None:
                cache_tag = " · cached" if wx.from_cache else ""
                wx_grid = f"""
<div class="sd-wx">
  <div class="t"><small>Temp range</small><b>{wx.temp_min_c:.0f}–{wx.temp_max_c:.0f}°C</b></div>
  <div class="t"><small>Rain chance</small><b>{wx.max_precip_prob:.0f}%</b></div>
  <div class="t"><small>Rain 48 h</small><b>{wx.precip_mm_48h:.1f} mm</b></div>
  <div class="t"><small>Wind max</small><b>{wx.wind_max_kmh:.0f} km/h</b></div>
</div>
<div class="sd-meta">{_esc(wx.source)} · {_esc(wx.district)} · {_esc(wx.forecast_date)}{cache_tag}</div>
"""
            st.markdown(
                f"""
<div class="sd-panel" style="background:{rt['bg']};border-color:{rt['border']};color:{rt['ink']};">
  <span class="sd-chip" style="border-color:{rt['border']};color:{rt['ink']};">Risk: {_esc(adv.weather_risk)}</span>
  <span class="sd-chip" style="border-color:#E0C070;color:#E0C070;">Threat: {_esc(threat)}</span>
  <span class="sd-chip" style="border-color:#90A4AE;color:#CFD8DC;">Price trend: {_esc(adv.price_trend)}</span>
  {wx_grid}
</div>
                """,
                unsafe_allow_html=True,
            )

    # ---- Mitigation protocol + leaf health
    if adv is not None:
        col_a, col_b = st.columns([1.15, 1])
        with col_a:
            st.markdown("##### 🛡️ Proactive mitigation protocol")
            protocol = (
                adv.mitigation_protocol if isinstance(adv, EnhancedHarvestAdvisory) else ""
            ) or adv.action_advice
            steps = [s.strip() for s in protocol.replace(";", ".").split(".") if s.strip()]
            steps = [s[0].upper() + s[1:] for s in steps]
            steps_html = "".join(f"<li>{_esc(s)}.</li>" for s in steps[:5])
            st.markdown(
                f"""
<div class="sd-panel" style="background:#12221C;border-color:#C4A35A;color:#E8F0EB;">
  <ol class="sd-steps">{steps_html}</ol>
  <div class="sd-meta">{_esc(adv.disclaimer)}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Full advisory text"):
                st.write(adv.action_advice)

        with col_b:
            st.markdown("##### 🌿 Leaf health")
            vision = result.vision
            disease_tip = (
                adv.disease_action_tip if isinstance(adv, EnhancedHarvestAdvisory) else ""
            )
            if vision is not None:
                dt = vision.disease_triage
                healthy = dt.is_healthy
                bg, border, ink = (
                    ("#143A2B", "#4CAF6A", "#D7F2DC") if healthy else ("#3A2E14", "#E0C070", "#F7E8B8")
                )
                badge = "Healthy" if healthy else dt.detected_disease
                qnote = ""
                if not vision.image_quality_ok:
                    qnote = (
                        f'<p><em>⚠️ Photo quality — {_esc(vision.quality_issue_reason or "use manual overrides")}</em></p>'
                    )
                conf_txt = f" · {dt.confidence:.0%}" if dt.confidence else ""
                st.markdown(
                    f"""
<div class="sd-panel" style="background:{bg};border-color:{border};color:{ink};">
  <span class="sd-chip" style="border-color:{border};color:{ink};">{_esc(badge)}{conf_txt}</span>
  <span class="sd-chip" style="border-color:#E0C070;color:#E0C070;">Stage: {_esc(vision.phenology_stage.value)}</span>
  <span class="sd-chip" style="border-color:#90A4AE;color:#CFD8DC;">Severity: {_esc(dt.severity)}</span>
  <p style="margin-top:0.6rem;">{_esc(dt.symptoms_summary)}</p>
  {qnote}
  {f'<div class="sd-meta">{_esc(disease_tip)}</div>' if disease_tip else ''}
</div>
                    """,
                    unsafe_allow_html=True,
                )
            elif disease_tip:
                st.markdown(
                    f"""
<div class="sd-panel" style="background:#3A2E14;border-color:#E0C070;color:#F7E8B8;">
  <span class="sd-chip" style="border-color:#E0C070;color:#F7E8B8;">Manual override</span>
  <p style="margin-top:0.6rem;">{_esc(disease_tip)}</p>
</div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
<div class="sd-panel" style="background:#162820;border-color:rgba(196,163,90,0.35);color:#E8F0EB;">
  <span class="sd-chip" style="border-color:#90A4AE;color:#CFD8DC;">No photo this run</span>
  <p style="margin-top:0.6rem;">Add a leaf / canopy photo in step 3 for disease triage and
  photo-based phenology. Stage was taken from the form.</p>
</div>
                    """,
                    unsafe_allow_html=True,
                )

    # ---- City routing
    st.markdown("##### 🚚 Where selling may pay better")
    has_quote = quote is not None
    rows = format_city_rows(result.top_cities, has_quote=has_quote)
    if not rows:
        st.write("No alternate city estimates available right now.")
    else:
        if best is not None:
            gain_bit = (
                f" — <b>{best.net_gain_vs_quote:+,.0f} Rs/maund</b> vs your quote"
                if has_quote
                else ""
            )
            st.markdown(
                f'<div class="sd-callout">🏆 <b>{_esc(best.city_name)}</b> · ~{best.distance_km:.0f} km · '
                f"net Rs {best.net_price_maund:,.0f}/maund after transport &amp; commission{gain_bit}. "
                f"Break-even at Rs {best.break_even_price:,.0f}.</div>",
                unsafe_allow_html=True,
            )
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption(
            "Estimates only. Transport, commission and farm-gate rates are assumptions — "
            + (result.top_cities[0].assumptions if result.top_cities else "")
        )

    # ---- Urdu summary + audio
    st.markdown("##### 🔊 اردو خلاصہ · Urdu summary")
    summary = build_urdu_summary(result)
    st.markdown(
        f'<div class="sd-quote" dir="rtl">{_esc(summary)}</div>',
        unsafe_allow_html=True,
    )
    key = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    cache: dict = st.session_state.audio_cache
    if key not in cache:
        with st.spinner("Generating Urdu audio…"):
            cache[key] = _tts_with_fallback(summary)
    if cache.get(key):
        st.audio(cache[key], format="audio/mp3")
    else:
        c_msg, c_btn = st.columns([3, 1])
        with c_msg:
            st.caption("Audio unavailable (TTS timed out) — text summary is shown above.")
        with c_btn:
            if st.button("↻ Retry audio", key="retry_audio"):
                cache.pop(key, None)
                st.rerun()

    with st.expander("⚠️ Disclaimers & assumptions — please read"):
        st.warning(
            APP_DISCLAIMER
            + " Wholesale prices are reference baselines, not farm-gate guarantees."
        )
        for line in result.disclaimers:
            st.write(f"- {line}")


def _current_step() -> int:
    if st.session_state.get("analysis_result") is not None:
        return 4
    if st.session_state.get("parse_outcome") is not None:
        return 3
    return 1


def main() -> None:
    st.set_page_config(
        page_title="Sahi Daam AI — Voice-First Mandi & Crop-Health Advisor",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="🌾",
    )
    _inject_styles()
    _init_state()
    with st.spinner("Warming price engines…"):
        t0 = time.perf_counter()
        info = _warm_engines()
        st.session_state.cold_s = time.perf_counter() - t0
        st.session_state.warm_s = info.get("warm_s")

    _render_sidebar()
    _hero()
    _stepper(_current_step())

    try:
        _render_input()
        _render_parse_feedback()
        _render_confirmation_form()
        _render_results()
    except Exception as exc:
        st.error(f"Something went wrong. Please try again. ({type(exc).__name__})")

    mode = st.session_state.get("ai_mode_label") or (
        f"AI mode: live ready ({resolve_provider()})"
        if resolve_api_key()
        else "AI mode: basic offline parser (no API key)"
    )
    st.markdown(
        f'<p class="sd-footer-note">{_esc(mode)} · '
        f"AI calls this session: {int(st.session_state.get('ai_calls') or 0)}/{MAX_AI_CALLS_PER_SESSION}"
        "<br/>Built for Punjab farmers · Wholesale guidance only · "
        f"{_esc(APP_DISCLAIMER)}</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

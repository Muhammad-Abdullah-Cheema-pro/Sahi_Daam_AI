"""Offline tests for farmer-request voice/text parser."""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

import voice_parser as vp
from lexicon import normalize_number, price_to_per_maund, quantity_to_maunds
from llm_client import LLMError

CASES = Path(__file__).parent / "voice_cases.csv"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2800", 2800.0),
        ("chalees", 40.0),
        ("do hazar aath sau", 2800.0),
        ("dhai sau", 250.0),
        ("derh hazar", 1500.0),
        ("پچاس", 50.0),
        ("ایک سو بیس", 120.0),
        ("۴۰", 40.0),
        ("40 2800", None),
        ("abc", None),
    ],
)
def test_normalize_number(text: str, expected: float | None) -> None:
    assert normalize_number(text) == expected


def test_unit_conversions() -> None:
    assert quantity_to_maunds(4000, "kg") == 100.0
    assert quantity_to_maunds(2, "ton") == 50.0
    assert price_to_per_maund(80, "per_kg") == 3200.0
    assert price_to_per_maund(11750, "per_100kg") == 4700.0
    assert quantity_to_maunds(10, "bags") is None
    assert price_to_per_maund(100, "per_box") is None


def test_csv_fallback_accuracy() -> None:
    rows = list(csv.DictReader(CASES.open(encoding="utf-8")))
    mismatches: list[str] = []
    ok = 0
    for row in rows:
        out = vp.parse_request(row["spoken_text"], use_llm=False)
        exp_crop = row["expected_crop"]
        exp_qty = float(row["expected_quantity_maunds"])
        exp_dist = row["expected_district"]
        exp_quote = row["expected_quote_per_maund"].strip()
        req = out.request
        if out.status != "ok" or req is None:
            mismatches.append(f"{row['id']}: status={out.status} missing={out.missing_fields}")
            continue
        problems = []
        if req.crop != exp_crop:
            problems.append(f"crop {req.crop!r}!={exp_crop!r}")
        if abs(req.quantity_maunds - exp_qty) > 1e-6:
            problems.append(f"qty {req.quantity_maunds}!={exp_qty}")
        if req.district != exp_dist:
            problems.append(f"district {req.district!r}!={exp_dist!r}")
        if exp_quote == "":
            if req.quoted_price_per_maund is not None:
                problems.append(f"quote {req.quoted_price_per_maund}!=None")
        else:
            if req.quoted_price_per_maund is None or abs(
                req.quoted_price_per_maund - float(exp_quote)
            ) > 1e-6:
                problems.append(f"quote {req.quoted_price_per_maund}!={exp_quote}")
        if problems:
            mismatches.append(f"{row['id']}: " + "; ".join(problems))
        else:
            ok += 1
    print(f"fallback full-row accuracy {ok}/20")
    for m in mismatches:
        print("mismatch:", m)
    assert ok / 20.0 >= 0.90, mismatches


def test_needs_clarification_fallback() -> None:
    cases = [
        ("tamatar Okara mein hain", ["quantity_maunds"], False, False),
        ("40 maund tamatar", ["district"], False, True),
        ("40 maund chawal Okara", ["crop"], True, False),
        ("40 maund tamatar Badin", ["district"], False, True),
        ("", ["crop", "quantity_maunds", "district"], True, True),
        ("hello", ["crop", "quantity_maunds", "district"], True, True),
    ]
    for text, expect_missing, crops_note, punjab_note in cases:
        out = vp.parse_request(text or None, use_llm=False)
        assert out.status == "needs_clarification", text
        assert out.request is None, text
        assert out.missing_fields == expect_missing, (text, out.missing_fields)
        if crops_note:
            assert "Supported crops" in out.message
        if punjab_note:
            assert "Punjab" in out.message


def test_mocked_llm_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    def _kg(**_):
        return {
            "crop": "Tomato",
            "quantity": 4000,
            "quantity_unit": "kg",
            "district": "Multan",
            "quoted_price": 55,
            "price_unit": "per_kg",
            "crop_stage": None,
            "raw_transcript": "x",
            "language_detected": "en",
            "confidence": 0.9,
        }

    monkeypatch.setattr(vp, "extract_from_text", lambda t: _kg())
    out = vp.parse_request("ignored", use_llm=True)
    assert out.status == "ok" and out.request is not None
    assert out.request.quantity_maunds == 100.0
    assert out.request.quoted_price_per_maund == 2200.0

    monkeypatch.setattr(
        vp,
        "extract_from_text",
        lambda t: {
            "crop": "chawal",
            "quantity": 40,
            "quantity_unit": "maund",
            "district": "Okara",
            "quoted_price": 1000,
            "price_unit": "per_maund",
            "confidence": 0.9,
            "raw_transcript": t,
            "language_detected": None,
            "crop_stage": None,
        },
    )
    out = vp.parse_request("chawal", use_llm=True)
    assert out.status == "needs_clarification"
    assert "crop" in out.missing_fields

    monkeypatch.setattr(
        vp,
        "extract_from_text",
        lambda t: {
            "crop": "Wheat",
            "quantity": 50,
            "quantity_unit": "maund",
            "district": "Lahore",
            "quoted_price": None,
            "price_unit": None,
            "confidence": 0.9,
            "raw_transcript": t,
            "language_detected": None,
            "crop_stage": None,
        },
    )
    out = vp.parse_request("wheat no quote", use_llm=True)
    assert out.status == "ok"
    assert out.missing_fields == ["quoted_price_per_maund"]

    monkeypatch.setattr(
        vp,
        "extract_from_text",
        lambda t: {
            "crop": "Onion",
            "quantity": -5,
            "quantity_unit": "maund",
            "district": "Multan",
            "quoted_price": 1000,
            "price_unit": "per_maund",
            "confidence": 0.9,
            "raw_transcript": t,
            "language_detected": None,
            "crop_stage": None,
        },
    )
    out = vp.parse_request("neg", use_llm=True)
    assert out.status == "needs_clarification"
    assert "quantity_maunds" in out.missing_fields

    monkeypatch.setattr(
        vp,
        "extract_from_text",
        lambda t: {
            "crop": "Wheat",
            "quantity": 10,
            "quantity_unit": "maund",
            "district": "Lahore",
            "quoted_price": 3000,
            "price_unit": "per_maund",
            "confidence": None,
            "raw_transcript": t,
            "language_detected": None,
            "crop_stage": None,
        },
    )
    out = vp.parse_request("conf", use_llm=True)
    assert out.request and out.request.confidence == 0.8

    def _boom(_t: str):
        raise LLMError("down")

    monkeypatch.setattr(vp, "extract_from_text", _boom)
    out = vp.parse_request(
        "40 maund tamatar hain Okara mein, broker 2800 de raha hai",
        use_llm=True,
    )
    assert out.status == "ok"
    assert out.request and out.request.confidence <= 0.6
    assert "Basic mode" in out.message

    def _audio_fail(_b: bytes, _m: str):
        raise LLMError("bad audio")

    monkeypatch.setattr(vp, "extract_from_audio", _audio_fail)
    out = vp.parse_request(audio_bytes=b"abc", mime_type="audio/wav", use_llm=True)
    assert out.status == "failed"

    monkeypatch.setattr(
        vp,
        "extract_from_audio",
        lambda _b, _m: {
            "crop": "Potato",
            "quantity": 35,
            "quantity_unit": "maund",
            "district": "Kasur",
            "quoted_price": 2000,
            "price_unit": "per_maund",
            "confidence": 0.95,
            "raw_transcript": "audio",
            "language_detected": "ur",
            "crop_stage": None,
        },
    )
    out = vp.parse_request(audio_bytes=b"abc", mime_type="audio/wav", use_llm=True)
    assert out.status == "ok" and out.request is not None
    assert out.request.district == "Kasur"

    def _runtime(_t: str):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(vp, "extract_from_text", _runtime)
    # RuntimeError happens inside extract_from_text call — parse_request only
    # catches LLMError around LLM, then fallback. Force unexpected in build path:
    monkeypatch.setattr(
        vp,
        "rule_based_extract",
        lambda t: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    out = vp.parse_request("x", use_llm=False)
    assert out.status == "failed"


@pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="No GEMINI_API_KEY/GOOGLE_API_KEY",
)
def test_integration_gemini_live() -> None:
    out = vp.parse_request(
        "40 maund tamatar hain Okara mein, broker 2800 de raha hai",
        use_llm=True,
    )
    assert out.status in {"ok", "needs_clarification"}
    if out.status == "ok" and out.request is not None:
        assert out.request.crop == "Tomato"

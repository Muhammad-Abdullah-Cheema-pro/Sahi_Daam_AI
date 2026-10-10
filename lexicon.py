"""Offline deterministic lexicon for crops, districts, numbers, and units."""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Literal, Optional

QuantityUnit = Literal["maund", "kg", "ton", "quintal"]
PriceUnit = Literal["per_maund", "per_kg", "per_100kg"]

# Arabic → Urdu letter forms
_ARABIC_TO_URDU = str.maketrans({
    "\u064a": "\u06cc",  # Arabic yeh → Urdu yeh
    "\u0643": "\u06a9",  # Arabic kaf → Urdu kaf
    "\u0629": "\u06c3",  # teh marbuta → teh
})

_URDU_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
_PUNCT_RE = re.compile(r"[^\w\s.]+", re.UNICODE)
_THOUSANDS_COMMA_RE = re.compile(r"(?<=\d),(?=\d{3}\b)")


def normalize_text(text: str) -> str:
    """Lowercase, NFKC, map Arabic yeh/kaf, strip diacritics, digits→ASCII, commas, punct."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.translate(_ARABIC_TO_URDU)
    s = s.translate(_URDU_ARABIC_DIGITS)
    s = _DIACRITICS_RE.sub("", s)
    s = s.lower()
    s = _THOUSANDS_COMMA_RE.sub("", s)
    # Drop punctuation but keep dots inside numbers (e.g. 1.5)
    s = _PUNCT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Crops -----------------------------------------------------------------

CROPS: dict[str, list[str]] = {
    "Wheat": [
        "wheat", "gandum", "gandam", "gehu", "gehun", "گندم", "گیہوں", "گیہو",
    ],
    "Tomato": [
        "tomato", "tomatoes", "tamatar", "tamatars", "ٹماٹر", "ٹماٹرز",
    ],
    "Potato": [
        "potato", "potatoes", "aloo", "alu", "aalu", "aaloo", "آلو", "آلوؤں",
    ],
    "Onion": [
        "onion", "onions", "pyaz", "piaz", "piyaz", "pyaaz", "پیاز",
    ],
}

# --- Districts (Punjab) ----------------------------------------------------

DISTRICTS: dict[str, list[str]] = {
    "Lahore": ["lahore", "لاہور"],
    "Faisalabad": ["faisalabad", "faislabad", "lyallpur", "فیصل آباد", "فیصلاباد"],
    "Multan": ["multan", "ملتان"],
    "Sargodha": ["sargodha", "سرگودھا", "سرگودها"],
    "Gujranwala": ["gujranwala", "gujaranwala", "گوجرانوالہ", "گوجرانوالا"],
    "Okara": ["okara", "okaara", "اوکاڑہ", "اوکڑہ"],
    "Rawalpindi": ["rawalpindi", "pindi", "راولپنڈی"],
    "Kasur": ["kasur", "kasoor", "qasur", "pattoki", "patoki", "قصور", "پتوکی"],
    "Sahiwal": ["sahiwal", "ساہیوال"],
    "Bahawalpur": ["bahawalpur", "bahawal pur", "بہاولپور"],
    "Sialkot": ["sialkot", "سیالکوٹ"],
    "Jhang": ["jhang", "جھنگ"],
    "Sheikhupura": ["sheikhupura", "sheikupura", "شیخوپورہ", "شیخوپورا"],
    "Rahim Yar Khan": ["rahim yar khan", "rahimyarkhan", "ryk", "رحیم یار خان"],
    "Dera Ghazi Khan": ["dera ghazi khan", "dg khan", "dgkhan", "ڈیرہ غازی خان"],
    "Gujrat": ["gujrat", "گجرات"],
    "Khanewal": ["khanewal", "خانیوال"],
    "Vehari": ["vehari", "وہاڑی"],
    "Muzaffargarh": ["muzaffargarh", "مظفرگڑھ"],
    "Pakpattan": ["pakpattan", "pakpatan", "پاکپتن"],
    "Chiniot": ["chiniot", "چنیوٹ"],
    "Toba Tek Singh": ["toba tek singh", "toba", "ٹوبہ ٹیک سنگھ"],
    "Mandi Bahauddin": ["mandi bahauddin", "mandi baha ud din", "منڈی بہاؤالدین"],
    "Hafizabad": ["hafizabad", "حافظ آباد"],
    "Narowal": ["narowal", "نارووال"],
    "Mianwali": ["mianwali", "میانوالی"],
    "Bhakkar": ["bhakkar", "بھکر"],
    "Khushab": ["khushab", "خوشاب"],
    "Layyah": ["layyah", "لیہ"],
    "Lodhran": ["lodhran", "لودھراں"],
    "Rajanpur": ["rajanpur", "راجن پور"],
    "Attock": ["attock", "اٹک"],
    "Chakwal": ["chakwal", "چکوال"],
    "Jhelum": ["jhelum", "جہلم"],
    "Nankana Sahib": ["nankana sahib", "nankana", "ننکانہ صاحب"],
    "Bahawalnagar": ["bahawalnagar", "بہاولنگر"],
}


def _build_lookup(mapping: dict[str, list[str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for canonical, syns in mapping.items():
        out[normalize_text(canonical)] = canonical
        for s in syns:
            out[normalize_text(s)] = canonical
    return out


_CROP_LOOKUP = _build_lookup(CROPS)
_DISTRICT_LOOKUP = _build_lookup(DISTRICTS)


def _fuzzy_lookup(norm: str, lookup: dict[str, str]) -> Optional[str]:
    if not norm:
        return None
    if norm in lookup:
        return lookup[norm]
    if len(norm) < 5:
        return None
    keys = list(lookup.keys())
    matches = difflib.get_close_matches(norm, keys, n=1, cutoff=0.86)
    if matches:
        return lookup[matches[0]]
    return None


def canonical_crop(text: str) -> Optional[str]:
    return _fuzzy_lookup(normalize_text(text), _CROP_LOOKUP)


def canonical_district(text: str) -> Optional[str]:
    return _fuzzy_lookup(normalize_text(text), _DISTRICT_LOOKUP)


def _phrases_by_length(lookup: dict[str, str]) -> list[tuple[str, str]]:
    items = [(p, c) for p, c in lookup.items() if p]
    items.sort(key=lambda x: len(x[0]), reverse=True)
    return items


_CROP_PHRASES = _phrases_by_length(_CROP_LOOKUP)
_DISTRICT_PHRASES = _phrases_by_length(_DISTRICT_LOOKUP)


def _find_phrase(norm_text: str, phrases: list[tuple[str, str]]) -> Optional[str]:
    padded = f" {norm_text} "
    for phrase, canonical in phrases:
        needle = f" {phrase} "
        if needle in padded:
            return canonical
    return None


def find_crop(text: str) -> Optional[str]:
    return _find_phrase(normalize_text(text), _CROP_PHRASES)


def find_district(text: str) -> Optional[str]:
    return _find_phrase(normalize_text(text), _DISTRICT_PHRASES)


# --- Numbers ---------------------------------------------------------------

_SMALL: dict[str, float] = {
    # 1-20 Roman
    "zero": 0, "ek": 1, "aik": 1, "one": 1,
    "do": 2, "two": 2,
    "teen": 3, "tin": 3, "three": 3,
    "char": 4, "chaar": 4, "four": 4,
    "panch": 5, "paanch": 5, "five": 5,
    "chhe": 6, "che": 6, "chhah": 6, "cheh": 6, "six": 6,
    "saat": 7, "sat": 7, "seven": 7,
    "aath": 8, "ath": 8, "aat": 8, "eight": 8,
    "nau": 9, "no": 9, "nine": 9,
    "das": 10, "ten": 10,
    "gyarah": 11, "gyara": 11, "yarah": 11, "eleven": 11,
    "barah": 12, "bara": 12, "twelve": 12,
    "terah": 13, "tera": 13, "thirteen": 13,
    "chaudah": 14, "chauda": 14, "fourteen": 14,
    "pandrah": 15, "pandra": 15, "fifteen": 15,
    "solah": 16, "sola": 16, "sixteen": 16,
    "satrah": 17, "satra": 17, "seventeen": 17,
    "atharah": 18, "athara": 18, "eighteen": 18,
    "unnis": 19, "unees": 19, "unnis": 19, "nineteen": 19,
    "bees": 20, "bis": 20, "twenty": 20,
    # tens
    "tees": 30, "thirty": 30,
    "chalees": 40, "chalis": 40, "chaalis": 40, "forty": 40,
    "pachas": 50, "pachaas": 50, "fifty": 50,
    "saath": 60, "sixty": 60,
    "sattar": 70, "seventy": 70,
    "assi": 80, "eighty": 80,
    "nabbe": 90, "navve": 90, "ninety": 90,
    # xx5
    "pachhees": 25, "pachees": 25, "pachis": 25, "twentyfive": 25,
    "paintees": 35, "paintees": 35, "thirtyfive": 35,
    "paintalees": 45, "paintalis": 45, "fortyfive": 45,
    "pachpan": 55, "fiftyfive": 55,
    "painsath": 65, "pensath": 65, "sixtyfive": 65,
    "pachhattar": 75, "pachattar": 75, "seventyfive": 75,
    "pachasi": 85, "eightyfive": 85,
    "pachanve": 95, "pachanave": 95, "ninetyfive": 95,
    # fractions
    "derh": 1.5, "dedh": 1.5, "derhi": 1.5,
    "dhai": 2.5, "dhayi": 2.5, "adhai": 2.5,
    # Urdu script 1-20 / tens / xx5
    "ایک": 1, "دو": 2, "تین": 3, "چار": 4, "پانچ": 5,
    "چھ": 6, "چھہ": 6, "سات": 7, "آٹھ": 8, "اٹھ": 8, "نو": 9,
    "دس": 10, "گیارہ": 11, "بارہ": 12, "تیرہ": 13, "چودہ": 14,
    "پندرہ": 15, "سولہ": 16, "سترہ": 17, "اٹھارہ": 18, "انیس": 19, "بیس": 20,
    "تیس": 30, "چالیس": 40, "پچاس": 50, "ساٹھ": 60, "ستر": 70, "اسی": 80, "نوے": 90,
    "پچیس": 25, "پینتیس": 35, "پینتالیس": 45, "پچپن": 55,
    "پینسٹھ": 65, "پچہتر": 75, "پچاسی": 85, "پچانوے": 95,
    "ڈیڑھ": 1.5, "ڈیڈھ": 1.5, "ڈھائی": 2.5,
}

_MULT: dict[str, float] = {
    "sau": 100, "so": 100, "hundred": 100, "سو": 100,
    "hazar": 1000, "hazaar": 1000, "thousand": 1000, "ہزار": 1000,
    "lakh": 100000, "lac": 100000, "لاکھ": 100000,
}

# normalize keys once
_SMALL_N = {normalize_text(k): v for k, v in _SMALL.items()}
_MULT_N = {normalize_text(k): v for k, v in _MULT.items()}

TokenKind = Literal["digit", "small", "mult"]


def _token_kind_value(tok: str) -> Optional[tuple[TokenKind, float]]:
    if re.fullmatch(r"\d+(?:\.\d+)?", tok):
        return "digit", float(tok)
    if tok in _SMALL_N:
        return "small", _SMALL_N[tok]
    if tok in _MULT_N:
        return "mult", _MULT_N[tok]
    return None


def _can_join(prev: TokenKind, nxt: TokenKind) -> bool:
    return (prev, nxt) in {
        ("small", "mult"),
        ("digit", "mult"),
        ("mult", "small"),
        ("mult", "digit"),
    }


def _eval_span(parts: list[tuple[TokenKind, float]]) -> float:
    total = 0.0
    current = 0.0
    for kind, val in parts:
        if kind in {"digit", "small"}:
            current += val
        else:  # mult
            current = (current or 1.0) * val
            if val >= 1000:
                total += current
                current = 0.0
    return total + current


def find_number_spans(tokens: list[str]) -> list[tuple[int, int, float]]:
    """Return (start, end_exclusive, value) spans over normalized tokens."""
    spans: list[tuple[int, int, float]] = []
    i = 0
    n = len(tokens)
    while i < n:
        kv = _token_kind_value(tokens[i])
        if kv is None:
            i += 1
            continue
        start = i
        parts: list[tuple[TokenKind, float]] = [kv]
        prev_kind = kv[0]
        i += 1
        while i < n:
            nxt = _token_kind_value(tokens[i])
            if nxt is None or not _can_join(prev_kind, nxt[0]):
                break
            parts.append(nxt)
            prev_kind = nxt[0]
            i += 1
        spans.append((start, i, _eval_span(parts)))
    return spans


def normalize_number(text: str) -> Optional[float]:
    """Return a value only if the whole text is exactly one number span."""
    tokens = normalize_text(text).split()
    if not tokens:
        return None
    spans = find_number_spans(tokens)
    if len(spans) != 1:
        return None
    s, e, val = spans[0]
    if s != 0 or e != len(tokens):
        return None
    return val


# --- Units -----------------------------------------------------------------

MAUND_UNITS = {"maund", "maunds", "mund", "mand", "man", "mann", "mun", "من"}
KG_UNITS = {"kg", "kilo", "kilos", "kilogram", "kilograms", "کلو"}
TON_UNITS = {"ton", "tons", "tonne", "tonnes", "ٹن"}
QUINTAL_UNITS = {"quintal", "quintals", "qtl", "کوئنٹل"}

_UNIT_TO_CANON: dict[str, QuantityUnit] = {}
for u in MAUND_UNITS:
    _UNIT_TO_CANON[normalize_text(u)] = "maund"
for u in KG_UNITS:
    _UNIT_TO_CANON[normalize_text(u)] = "kg"
for u in TON_UNITS:
    _UNIT_TO_CANON[normalize_text(u)] = "ton"
for u in QUINTAL_UNITS:
    _UNIT_TO_CANON[normalize_text(u)] = "quintal"


def canonical_quantity_unit(token: str) -> Optional[QuantityUnit]:
    return _UNIT_TO_CANON.get(normalize_text(token))


def quantity_to_maunds(value: float, unit: Optional[str]) -> Optional[float]:
    if unit is None:
        return None
    u = normalize_text(unit)
    canon = _UNIT_TO_CANON.get(u, u if u in {"maund", "kg", "ton", "quintal"} else None)
    if canon == "maund":
        return float(value)
    if canon == "kg":
        return float(value) / 40.0
    if canon == "ton":
        return float(value) * 25.0
    if canon == "quintal":
        return float(value) * 2.5
    return None


def price_to_per_maund(value: float, unit: Optional[str]) -> Optional[float]:
    if unit is None:
        return None
    u = normalize_text(unit).replace(" ", "_")
    # accept both Literal forms and loose tokens
    if u in {"per_maund", "maund", "maunds", "man", "mann", "mun", "من"}:
        return float(value)
    if u in {"per_kg", "kg", "kilo", "kilogram", "کلو"}:
        return float(value) * 40.0
    if u in {"per_100kg", "quintal", "qtl", "کوئنٹل", "per_quintal"}:
        return float(value) * 0.4
    return None


PRICE_KEYWORDS = {
    normalize_text(x)
    for x in (
        "rs", "rupay", "rupees", "rupee", "روپے", "روپیہ", "ریٹ", "rate",
        "price", "bhao", "bhaao", "بھاؤ", "qeemat", "qimat", "قیمت",
    )
}
LINK_WORDS = {normalize_text(x) for x in ("ka", "ki", "ke", "hai", "of", "کا", "کی", "کے", "ہے")}

# Sahi Daam AI — 5-minute demo script

**Audience:** AICON judges · **Time:** ~5:00 · **Honesty:** every number below is **MEASURED** on repo data unless tagged **ESTIMATE** / **SYNTHETIC-AUDIO**.

**Before you start:** Streamlit running (`python -m streamlit run app.py`) or use screenshots from `reports/figures/` (placeholders OK). Have `.env` with a working `GEMINI_MODEL` for live voice; otherwise use **typed offline** path.

---

## 0:00–0:30 — Hook

> “A broker quoted you Rs 2800 per maund for tomato in Okara. Is that fair, should you harvest before rain, and is another mandi worth the diesel?”

Show title slide / home: **Sahi Daam AI** — voice-first mandi advisor (Punjab).

---

## 0:30–1:30 — Fair price (MEASURED sample)

**Action:** Type (or use offline sample):

```text
40 maund Tomato Okara quote 2800
```

Toggle **offline / basic parse** if Gemini returns `model_not_found` (documented in `reports/llm_text_metrics.md`).

**Say while results load:**

- Comparison is against **WHOLESALE** AMIS bands, not farm-gate.
- Okara tomato history is thin locally; app uses **nearest usable market — Lahore** for the band.

**Expected output (MEASURED, 2026-10-10, `scripts.demo_analyze --offline`):**

| Field | Value |
| --- | --- |
| Verdict | **Very low** |
| Reference market | **Lahore** |
| Band low / avg / high | **5400 / 5800 / 6000** Rs/maund |
| Basis | `recent_median_band`, data_as_of **2026-10-09**, sample_days **45** |
| Wording | Quote **below wholesale range** (not “cheating”) |

Point at routing row: Lahore net vs quote uses **ESTIMATE** transport assumptions (see `reports/spread.md` — not realised income).

---

## 1:30–2:15 — Unable to assess (MEASURED)

**Action:** Typed input:

```text
50 maund Wheat Lahore quote 4500
```

**Expected:** Verdict **Unable to assess** — “No market has usable WHOLESALE data for Wheat” (**MEASURED**: Wheat/Lahore has **0** days in `data/amis_prices.csv` per `reports/data_quality.md`).

**Say:** The product fails closed instead of inventing a band.

---

## 2:15–3:15 — Harvest advisory (rule-based, not ML)

**Action:** Re-run tomato case with crop stage **Ready to harvest** (default).

**Expected (MEASURED on same run):** Weather risk **High**, price trend label **Rising** at reference market; advice mentions tarpaulins, ventilation, dry window — **generic non-chemical** guidance from `advisory_engine.py` + Open-Meteo.

**Say:** Advisory is **RULE-BASED**, thresholds are **heuristic — verify with an agronomist**; trend is **descriptive** (no held-out forecast accuracy — `reports/trend_metrics.md` **n=0**).

---

## 3:15–4:00 — Voice path (optional)

**If HTTPS/localhost + working Gemini:**

- Record or upload short Urdu phrase from `tests/voice_cases.csv` row 9.
- Show structured fields populated.

**If not:**

- State live typed Gemini eval **0/20** with `model_not_found` (**MEASURED**).
- Show **offline lexicon 20/20** on the same CSV (**typed text, not speech**).
- Play **gTTS** Urdu summary button — clarify **SYNTHETIC-AUDIO** TTS of **summary text only**, not farmer ASR benchmark.

---

## 4:00–4:45 — Evidence slide (tagged metrics)

Quickly show `reports/` highlights:

- Data: **434** rows, **2026-07-13..2026-10-09**, all pairs still **&lt;90 days** (**MEASURED**).
- Latency: analyze p50 **127 ms**, p95 **164 ms**, n=20 (**MEASURED**, weather stubbed).
- Spread (**ESTIMATE**): Onion median gross gap **3.23%**, Tomato **4.07%**.
- Backtest **n_test=0** — we do not claim MAPE/coverage wins yet.

---

## 4:45–5:00 — Close

> “We combine honest wholesale bands, transparent routing assumptions, and cautious harvest hints — and we label what is measured versus estimated. DEPLOYED_URL in README after hosting.”

---

## Fallback plan

| Failure | Fallback |
| --- | --- |
| Gemini down / wrong model | Typed input + **offline parse**; show `reports/llm_text_metrics.md` |
| AMIS stale | Show `reports/data_quality.md` date range; explain cached CSV |
| Weather timeout | Cached SQLite forecast; mention 5 s timeout rule |
| Mic blocked (no HTTPS) | Typed demo only; note localhost/HTTPS requirement |
| Streamlit crash | Screenshots: verdict panel for tomato + wheat unable-to-assess; paste JSON from `scripts.demo_analyze` |

Pre-generate screenshots: run demo commands above and capture Streamlit UI before judging.

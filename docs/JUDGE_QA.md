# Judge Q&A — Sahi Daam AI

Answers are grounded in [README.md](../README.md) and `reports/` only. No invented accuracy or income claims.

---

### What problem does this solve?

Farmers often lack a wholesale reference price, a simple net comparison to other mandis after transport, and a non-chemical harvest timing hint when weather is risky — in one Urdu-friendly session.

### Is the quote compared to farm-gate or mandi prices?

**WHOLESALE AMIS mandi prices**, explicitly not farm-gate. Verdicts say **below wholesale range**, not broker fraud.

### How do you know Rs 2800 for tomato in Okara is “very low”?

**MEASURED** demo: typed `40 maund Tomato Okara quote 2800` → verdict **Very low** vs Lahore reference band **5400 / 5800 / 6000** Rs/maund (`recent_median_band`, as_of **2026-10-09**). Okara uses Lahore as nearest usable AMIS band.

### Why Lahore when the farmer said Okara?

Okara tomato history in cache is **12 days** (**MEASURED**, thin &lt;90). Routing/band logic picks a **reference market** with a usable wholesale band.

### What happens for wheat in Lahore?

**MEASURED:** **Unable to assess** — Wheat/Lahore has **0** days in `data/amis_prices.csv`; no usable band.

### What AI models do you use?

- **Gemini** (`google-genai`) for structured parse of text/audio when configured.
- **gTTS** for Urdu **summary** speech only.
- Fair-price band: **scikit-learn** quantiles when enough history; else **recent median band** (rules + stats, not an LLM).

Default model ID in code: **`gemini-3.5-flash`**. Set **`GEMINI_MODEL`** to a Flash ID that passes `python -m scripts.check_env` (often **`gemini-3.8-flash`** in current API listings — verify live, do not cite accuracy we have not measured).

### What is your speech recognition accuracy?

We **do not claim** speech accuracy. **MEASURED:** no human mandi recordings yet (`reports/voice_metrics.md`). Typed offline parser **20/20** on `voice_cases.csv` (**typed text, not speech**). Live Gemini typed path **0/20** when model missing. gTTS clips are **SYNTHETIC-AUDIO** for optional audio-parse tests.

### What is your price forecast accuracy?

**MEASURED:** rolling backtest **n_test=0** for all commodities (`reports/metrics.md`) because history is thin (&lt;90 days per pair). We do **not** report MAPE or coverage wins.

### What about price trend “Rising”?

Descriptive change in recent wholesale median (`analysis/trend.py`). Held-out trend eval **n=0** (`reports/trend_metrics.md`).

### Does harvest advice use machine learning?

**No.** **Rule-based** on Open-Meteo forecast + observed trend label in `advisory_engine.py`. Thresholds are **heuristic — verify with an agronomist**. Generic shading/tarpaulin/ventilation language only.

### How fast is the core analysis?

**MEASURED:** `analyze()` p50 **127.2 ms**, p95 **164.4 ms**, n=20 warm runs, weather stubbed (`reports/latency.md`).

### Do you prove farmers earn more?

**No.** Cross-city net gaps are **ESTIMATE** upper-bound style (`reports/spread.md`: e.g. Onion median gross gap **3.23%**, Tomato **4.07%** with assumed commission/transport). Not realised income studies.

### Where does data come from?

AMIS Punjab wholesale (cached CSV **434** rows, **2026-07-13..2026-10-09**), Open-Meteo weather (5 s timeout, SQLite cache). External calls fall back to cache per project rules.

### Microphone does not work on deploy?

Browser capture needs **HTTPS or localhost**.

### Limitations you admit openly?

Short AMIS history, many **Unable to assess** paths, Wheat gaps, retired Gemini model IDs, gTTS dialect, routing assumptions not truck quotes — see README **Not claim** and **Limitations**.

### How do we reproduce metrics?

`python -m scripts.run_all_checks` and individual scripts listed in README.

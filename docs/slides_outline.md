# Slide outline — Sahi Daam AI (7–8 slides)

Match `docs/Sahi_Daam_AI_Demo.pptx`. Tag metrics on slides as noted.

---

## Slide 1 — Title

- **Sahi Daam AI** — voice-first mandi advisor (Punjab, AICON'26)
- Tagline: wholesale reference · routing · harvest hints
- DEPLOYED_URL placeholder

---

## Slide 2 — Problem

- Single broker quote, no wholesale band
- Optional better mandi after transport (**ESTIMATE** math)
- Weather uncertainty at harvest
- No invented income statistics

---

## Slide 3 — Architecture flow

- Diagram: voice/text → parse (Gemini or offline rules) → band + verdict → routing → Open-Meteo advisory → Urdu summary → gTTS optional
- Label: harvest advisory **RULE-BASED, not ML**

---

## Slide 4 — Demo result (MEASURED)

- Input: `40 maund Tomato Okara quote 2800`
- Verdict **Very low**; ref **Lahore**; band **5400 / 5800 / 6000** Rs/maund
- Screenshot placeholder: `[Streamlit verdict panel]`

---

## Slide 5 — Fail closed (MEASURED)

- Wheat / Lahore → **Unable to assess** (0 days Wheat/Lahore in cache)
- Screenshot placeholder: `[Unable to assess UI]`

---

## Slide 6 — Data & evaluation (tagged)

- AMIS **434** rows, **2026-07-13..2026-10-09**; all pairs **&lt;90 days** — **MEASURED**
- Backtest **n_test=0** — **MEASURED**
- Spread Onion **3.23%** / Tomato **4.07%** median gross gap — **ESTIMATE**
- Latency p50 **127 ms** / p95 **164 ms** — **MEASURED**
- Figure placeholder: `[reports/figures/ or metrics table]`

---

## Slide 7 — AI scope & limits

- Gemini parse (model from `GEMINI_MODEL`; default `gemini-3.5-flash`)
- Live typed eval **0/20** if model missing — **MEASURED**; offline **20/20** typed — **MEASURED**
- gTTS = summary TTS only — **SYNTHETIC-AUDIO** for synth eval
- **Not claimed:** speech accuracy, farmer income proof, forecast MAPE

---

## Slide 8 — Team & ask

- Blank team table (fill names)
- Call to action: try DEPLOYED_URL; questions
- Built with AI assistants disclosure (one line)

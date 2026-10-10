# AICON Phase 6 — submission checklist

Use before hand-in / demo day. Check boxes when true.

## Repository

- [ ] `README.md` complete: problem, flow, DEPLOYED_URL filled after deploy, tagged evaluation summary, team table
- [ ] `docs/DEMO_SCRIPT.md`, `docs/JUDGE_QA.md`, `docs/slides_outline.md`, `docs/Sahi_Daam_AI_Demo.pptx` present
- [ ] `docs/PHASE6_LOG.md` updated through Phase 6 steps
- [ ] `.env` **not** committed; `.env.example` has no secrets
- [ ] `python -m pytest -q` passes
- [ ] `python -m scripts.preflight` passes (or documented SKIPs for missing API key)

## Data & reports (regenerate before submit)

- [ ] `python -m scripts.data_quality` → `reports/data_quality.md` reflects latest `data/amis_prices.csv`
- [ ] `python -m scripts.evaluate` → `reports/metrics.md` (expect **n_test=0** until ≥90-day pairs)
- [ ] `python -m scripts.estimate_spread` → `reports/spread.md`
- [ ] `python -m scripts.bench_latency` → `reports/latency.md`
- [ ] `python -m scripts.eval_trend` → `reports/trend_metrics.md`
- [ ] Optional with API key: `python -m scripts.check_env`, `eval_llm_text`, `eval_voice_synth`

## Deploy

- [ ] Streamlit Cloud (or host) deployed from clean branch
- [ ] Secrets: `GEMINI_API_KEY`, valid `GEMINI_MODEL` in host settings
- [ ] DEPLOYED_URL pasted in README
- [ ] HTTPS enabled if demoing microphone

## Demo readiness

- [ ] Rehearsed 5-minute script (`docs/DEMO_SCRIPT.md`)
- [ ] Fallback: offline typed tomato + wheat cases; screenshots if live API fails
- [ ] Slides match tagged metrics (no uncited income or ASR % claims)

## Honesty audit

- [ ] Every slide/README metric tagged **MEASURED / ESTIMATE / SIMULATED / SYNTHETIC-AUDIO**
- [ ] “Not claimed” list unchanged: no farmer income proof, no speech accuracy, no MAPE with **n_test=0**
- [ ] Harvest advisory described as **rule-based**, not ML

## Licences & attribution

- [ ] Third-party table in README reviewed
- [ ] “Built with AI assistants” disclosure present
- [ ] AMIS / Open-Meteo attribution mentioned in demo if asked

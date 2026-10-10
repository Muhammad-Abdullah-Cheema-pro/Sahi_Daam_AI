# LLM typed-text metrics

**Label: typed text, NOT speech accuracy.**

Generated: 2026-10-10T20:11:07
Cases: `tests/voice_cases.csv` (n=20)

## Offline fallback (rule_based_extract)

- Full-row accuracy: **20/20**
- `crop`: **20/20**
- `district`: **20/20**
- `quantity_maunds`: **20/20**
- `quote`: **20/20**

## Live Gemini text path (LIVE Gemini (20 rows, sleep=0.0s))

- Full-row accuracy: **0/20**
- `crop`: **0/20**
- `district`: **0/20**
- `quantity_maunds`: **0/20**
- `quote`: **0/20**
- Errors:
  - id=1: model_not_found
  - id=2: model_not_found
  - id=3: model_not_found
  - id=4: model_not_found
  - id=5: model_not_found
  - id=6: model_not_found
  - id=7: model_not_found
  - id=8: model_not_found
  - id=9: unknown
  - id=10: model_not_found
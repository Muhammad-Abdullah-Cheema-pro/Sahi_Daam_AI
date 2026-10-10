# AMIS data quality (MEASURED)

Generated: 2026-10-10T20:37:22
Source file: `data/amis_prices.csv`
Date range: **2026-07-13** … **2026-10-09**
Total rows: **434**
Duplicate (date,city,commodity) rows: **0**
Suspect rows (`is_suspect`): **0**
Unit sanity failures (|maund − 100kg×0.4| > 0.05): **0**

Thin-pair threshold for demo/model: **<90 days present**.

| Commodity | City | Days present | Longest gap (days) | Suspect | Thin? |
| --- | --- | ---: | ---: | ---: | --- |
| Wheat | Lahore | 0 | 0 | 0 | YES |
| Wheat | Faisalabad | 35 | 54 | 0 | YES |
| Wheat | Gujranwala | 0 | 0 | 0 | YES |
| Wheat | Okara | 0 | 0 | 0 | YES |
| Wheat | Sargodha | 4 | 5 | 0 | YES |
| Wheat | Rawalpindi | 14 | 1 | 0 | YES |
| Wheat | Multan | 0 | 0 | 0 | YES |
| Tomato | Lahore | 74 | 16 | 0 | YES |
| Tomato | Faisalabad | 32 | 54 | 0 | YES |
| Tomato | Gujranwala | 14 | 1 | 0 | YES |
| Tomato | Okara | 12 | 2 | 0 | YES |
| Tomato | Sargodha | 9 | 2 | 0 | YES |
| Tomato | Rawalpindi | 14 | 1 | 0 | YES |
| Tomato | Multan | 14 | 1 | 0 | YES |
| Onion | Lahore | 74 | 16 | 0 | YES |
| Onion | Faisalabad | 33 | 54 | 0 | YES |
| Onion | Gujranwala | 14 | 1 | 0 | YES |
| Onion | Okara | 12 | 2 | 0 | YES |
| Onion | Sargodha | 9 | 2 | 0 | YES |
| Onion | Rawalpindi | 14 | 1 | 0 | YES |
| Onion | Multan | 14 | 1 | 0 | YES |
| Potato Fresh | Lahore | 0 | 0 | 0 | YES |
| Potato Fresh | Faisalabad | 1 | 0 | 0 | YES |
| Potato Fresh | Gujranwala | 0 | 0 | 0 | YES |
| Potato Fresh | Okara | 0 | 0 | 0 | YES |
| Potato Fresh | Sargodha | 0 | 0 | 0 | YES |
| Potato Fresh | Rawalpindi | 0 | 0 | 0 | YES |
| Potato Fresh | Multan | 0 | 0 | 0 | YES |
| Potato Store | Lahore | 0 | 0 | 0 | YES |
| Potato Store | Faisalabad | 32 | 54 | 0 | YES |
| Potato Store | Gujranwala | 0 | 0 | 0 | YES |
| Potato Store | Okara | 0 | 0 | 0 | YES |
| Potato Store | Sargodha | 9 | 2 | 0 | YES |
| Potato Store | Rawalpindi | 0 | 0 | 0 | YES |
| Potato Store | Multan | 0 | 0 | 0 | YES |

## Thin pairs (35)

- Wheat/Lahore (0d)
- Wheat/Faisalabad (35d)
- Wheat/Gujranwala (0d)
- Wheat/Okara (0d)
- Wheat/Sargodha (4d)
- Wheat/Rawalpindi (14d)
- Wheat/Multan (0d)
- Tomato/Lahore (74d)
- Tomato/Faisalabad (32d)
- Tomato/Gujranwala (14d)
- Tomato/Okara (12d)
- Tomato/Sargodha (9d)
- Tomato/Rawalpindi (14d)
- Tomato/Multan (14d)
- Onion/Lahore (74d)
- Onion/Faisalabad (33d)
- Onion/Gujranwala (14d)
- Onion/Okara (12d)
- Onion/Sargodha (9d)
- Onion/Rawalpindi (14d)
- Onion/Multan (14d)
- Potato Fresh/Lahore (0d)
- Potato Fresh/Faisalabad (1d)
- Potato Fresh/Gujranwala (0d)
- Potato Fresh/Okara (0d)
- Potato Fresh/Sargodha (0d)
- Potato Fresh/Rawalpindi (0d)
- Potato Fresh/Multan (0d)
- Potato Store/Lahore (0d)
- Potato Store/Faisalabad (32d)
- Potato Store/Gujranwala (0d)
- Potato Store/Okara (0d)
- Potato Store/Sargodha (9d)
- Potato Store/Rawalpindi (0d)
- Potato Store/Multan (0d)

Action: run `python -m scripts.collect_amis` for missing ranges in resumable ~60-day chunks. Never fabricate or interpolate rows.

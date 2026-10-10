# Price trend evaluation (MEASURED)

Method: at each eligible as_of, compare `get_price_trend` label with the sign of
the NEXT-7-observation median change (held-out). Threshold ±3.0%.
Baselines: always-Flat; shuffled labels (same marginal distribution).

| Commodity | n | Trend agree | Always-Flat | Shuffled |
| --- | ---: | ---: | ---: | ---: |
| ALL | 134 | 49.3% | 6.0% | 38.1% |
| Wheat | 7 | 0.0% | 28.6% | 42.9% |
| Tomato | 60 | 36.7% | 8.3% | 36.7% |
| Onion | 61 | 72.1% | 1.6% | 37.7% |
| Potato Fresh | 0 | n/a | n/a | n/a |
| Potato Store | 6 | 0.0% | 0.0% | 50.0% |

**Verdict (MEASURED, n=134)**: trend agree=49.3% vs always-Flat=6.0% vs shuffled=38.1%.

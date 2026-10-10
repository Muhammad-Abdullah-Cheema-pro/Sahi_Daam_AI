# Cross-market spread

**ESTIMATE, upper bound. Wholesale prices, assumed costs, not realised farmer income.**

Formulas reuse `analysis/routing.py` helpers: `net_j = FQP_j×(1-4%) − distance_km×1.5`; `net_gain = max_j(net_j) − origin_FQP`. `is_suspect` rows ignored. Need ≥3 markets/day.


Generated: 2026-10-10T20:24:55

Total origin-days: **190**

## Per commodity (ESTIMATE)

| Commodity | n origin-days | median gross gap % | share net gain > 0 | median net gain among >0 (Rs/maund) |
| --- | ---: | ---: | ---: | ---: |
| Onion | 89 | 3.23 | 16.9% | 131.7 |
| Tomato | 89 | 4.07 | 15.7% | 436.5 |
| Wheat | 12 | 0.00 | 0.0% | nan |
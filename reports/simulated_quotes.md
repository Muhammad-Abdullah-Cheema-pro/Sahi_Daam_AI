# Simulated quote verdict rates (SIMULATED)

Quotes are offsets from **actual next FQP** on held-out one-step pairs; verdict via `assess_quote` + `get_band` at prediction date.

## Flag rate by offset

| offset | n | any-flag rate | verdict mix |
| --- | ---: | ---: | --- |
| -5% | 6 | 0.667 | Fair=0.333, Unable to assess=0.667 |
| -10% | 6 | 0.667 | Fair=0.333, Unable to assess=0.667 |
| -20% | 6 | 1.0 | Low=0.333, Unable to assess=0.667 |
| -30% | 6 | 1.0 | Low=0.167, Unable to assess=0.667, Very low=0.167 |
| +5% | 6 | 0.667 | Fair=0.333, Unable to assess=0.667 |

## False-flag on +5% (SIMULATED)

- At **+5%** of actual next FQP, non-Fair (false-flag) rate ≈ **66.7%** (Fair rate=33.3%, n=6).
- Expected: quotes above wholesale should usually be **Fair**; Low/Very low here count as false flags.
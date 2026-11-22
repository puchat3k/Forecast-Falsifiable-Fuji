# EXPLORATORY: when does the adjusted forecast help?

> Post hoc slices of the frozen run (`per_case.csv`). Not pre-registered, so these slices suggest where to look next; they do not change the frozen verdict. Synthetic data only.

## 1. Is Fuji's rate current? (|rate − true base|; synthetic truth)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| current (≤ 0.10) | 130 | -0.0081 | [-0.0292, +0.0141] inconclusive | 46 |
| stale (> 0.10) | 95 | +0.0047 | [-0.0113, +0.0236] inconclusive | 43 |

## 2. How big a shift does the rule ask for? (|rate − analyst's own mean on the same records|)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| small (< 0.05) | 51 | -0.0015 | [-0.0071, +0.0042] inconclusive | 25 |
| medium (0.05–0.15) | 95 | -0.0120 | [-0.0301, +0.0066] inconclusive | 35 |
| large (≥ 0.15) | 79 | +0.0076 | [-0.0269, +0.0418] inconclusive | 29 |
| large AND current | 65 | -0.0003 | [-0.0351, +0.0346] inconclusive | 24 |
| large AND stale | 14 | +0.0443 | [-0.0567, +0.1520] inconclusive | 5 |

## 3. How much history? (n resolved)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| 10–19 | 22 | +0.0484 | [-0.0165, +0.1215] inconclusive | 9 |
| 20–49 | 52 | -0.0115 | [-0.0384, +0.0165] inconclusive | 21 |
| 50+ | 151 | -0.0072 | [-0.0231, +0.0089] inconclusive | 59 |


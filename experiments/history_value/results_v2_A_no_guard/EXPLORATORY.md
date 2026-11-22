# EXPLORATORY: when does the adjusted forecast help?

> Post hoc slices of the frozen run (`per_case.csv`). Not pre-registered, so these slices suggest where to look next; they do not change the frozen verdict. Synthetic data only.

## 1. Is Fuji's rate current? (|rate − true base|; synthetic truth)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| current (≤ 0.10) | 142 | -0.0093 | [-0.0291, +0.0097] inconclusive | 47 |
| stale (> 0.10) | 108 | +0.0027 | [-0.0116, +0.0193] inconclusive | 50 |

## 2. How big a shift does the rule ask for? (|rate − analyst's own mean on the same records|)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| small (< 0.05) | 58 | -0.0007 | [-0.0058, +0.0045] inconclusive | 30 |
| medium (0.05–0.15) | 113 | -0.0140 | [-0.0297, +0.0022] inconclusive | 38 |
| large (≥ 0.15) | 79 | +0.0076 | [-0.0269, +0.0418] inconclusive | 29 |
| large AND current | 65 | -0.0003 | [-0.0351, +0.0346] inconclusive | 24 |
| large AND stale | 14 | +0.0443 | [-0.0567, +0.1520] inconclusive | 5 |

## 3. How much history? (n resolved)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| 10–19 | 22 | +0.0484 | [-0.0165, +0.1215] inconclusive | 9 |
| 20–49 | 64 | -0.0134 | [-0.0343, +0.0089] inconclusive | 22 |
| 50+ | 164 | -0.0075 | [-0.0224, +0.0079] inconclusive | 66 |


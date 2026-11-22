# EXPLORATORY: when does the adjusted forecast help?

> Post hoc slices of the frozen run (`per_case.csv`). Not pre-registered, so these slices suggest where to look next; they do not change the frozen verdict. Synthetic data only.

## 1. Is Fuji's rate current? (|rate − true base|; synthetic truth)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| current (≤ 0.10) | 116 | -0.0199 | [-0.0387, -0.0002] HELPS | 35 |
| stale (> 0.10) | 117 | +0.0132 | [+0.0009, +0.0263] HURTS | 51 |

## 2. How big a shift does the rule ask for? (|rate − analyst's own mean on the same records|)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| small (< 0.05) | 60 | -0.0055 | [-0.0106, -0.0003] HELPS | 20 |
| medium (0.05–0.15) | 122 | -0.0009 | [-0.0152, +0.0134] inconclusive | 54 |
| large (≥ 0.15) | 51 | -0.0063 | [-0.0459, +0.0349] inconclusive | 12 |
| large AND current | 44 | -0.0329 | [-0.0707, +0.0069] inconclusive | 7 |
| large AND stale | 7 | +0.1613 | [+0.0340, +0.2553] HURTS | 5 |

## 3. How much history? (n resolved)

| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |
|---|---|---|---|---|
| 10–19 | 17 | -0.0503 | [-0.0972, +0.0057] inconclusive | 2 |
| 20–49 | 68 | -0.0101 | [-0.0310, +0.0115] inconclusive | 21 |
| 50+ | 148 | +0.0053 | [-0.0084, +0.0193] inconclusive | 63 |


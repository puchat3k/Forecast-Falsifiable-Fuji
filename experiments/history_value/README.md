# History-value replay: when do Fuji's historical reference rates improve offer-approval forecasts?

This is a time-ordered, pre-registered replay. It is **SYNTHETIC** and validates the method only. It is **not evidence that customer cases improve**. It runs in SHADOW mode and is forecast-only: it never sets an approval status, chooses a move or triggers an action.

## Run
```bash
python3 -m experiments.history_value.run      # ~11 s; verifies the frozen hashes, then writes results/
```

`freeze.py` was run once and committed in `47739ce`, before any scoring. Re-running it would only reproduce the same files, because it is seeded. `run.py` refuses to run if any frozen input, `history.py` or `combine.py` has changed.

## What was frozen before scoring (`frozen/`)
- **Cases:** 360 synthetic `offer_approval` cases (seed 20261122), in four cohorts:
  - **stable:** deal_desk, 14 days, true rate 0.70;
  - **drift:** procurement, 14 days, 0.80 changing to **0.35 on 2026-10-01**;
  - **heavily unresolved:** cfo, 14 days, 0.55, where rejections are often never written back;
  - **sparse:** legal, 7 days, 15 cases.
- **Unassisted forecast:** frozen per case. It reads the case evidence correctly but starts from a mis-set prior.
- **Cutoff rule:** each case is forecast at its own decision time (`anchor_at`). Only `reference_rate()` history visible at that moment is used, and the case's own record is excluded.
- **Combination rule (`combine.py`):** `logit p_adj = logit p_u + λ·(logit r − logit m)`.
  - `r` is Fuji's visible rate.
  - `m` is the analyst's own mean forecast on the same contributing records.
  - `λ = n/(n+10)`.
  - **Fallback:** when Fuji withholds, `p_u` is returned unchanged.
- **Scoring and decision rule (`protocol.json`):**
  - Brier score, computed by Fuji core `resolve()` and cross-checked;
  - case-bootstrap 95% CI;
  - harm counted per case.

## Results (`results/RESULTS.md`, `results.json`, `per_case.csv`)
**Paired Brier**, on the 233 cases where all three variants exist (lower is better):

| Variant | Brier |
|---|---|
| Unassisted | 0.2614 |
| Rate alone | 0.2545 |
| Adjusted | 0.2581 |

Adjusted minus unassisted: −0.0033 [−0.0147, +0.0087], **inconclusive**.

**Coverage:** the adjusted forecast actually ran on 233 of 360 cases (65%). Fuji withheld the rate on the rest: SPARSE 62, CENSORED 65.

**By cohort:**
- **Stable:** coverage 0.89. Adjusted −0.0073 [−0.0195, +0.0043], inconclusive, but in the expected direction. History made the forecast worse on 49 of 131 cases.
- **Drift, before the change:** rate alone **helps** (−0.070 [−0.129, −0.017]). Adjusted −0.037, inconclusive.
- **Drift, after the change:** adjusted **hurts** (+0.028 [+0.006, +0.052]); history made the forecast worse on 30 of 58 cases. Fuji's rate keeps pooling pre-change history (0.85 while the truth is 0.35), and nothing in the reader detects the change.
- **Heavily unresolved:** coverage 0. Every rate was withheld, so the forecast fell back unchanged.
  - This was the right call. At the first censored cutoff, the visible records read 10/10 approved while the true rate was 0.55, because rejections go missing.
- **Sparse:** coverage 0.27 (4 cases). Inconclusive.

**Fallback:** the forecast is unchanged on 100% of withheld cases. The exact analyst text for each withhold reason is in `RESULTS.md`.

**Existing #310 frozen forecasts** (3 approval forecasts, reused): all fall back.
- 2 are `WITHHELD_INCOMPATIBLE`: their horizons (51 and 82 days) are not in the family rules.
- 1 is `WITHHELD_SPARSE`: there is no labelled history.

## Verdict under the frozen decision rule
The overall paired interval is not below 0, and one period (drift, after the change) HURTS. So the frozen rule says **do not expose the signal to analysts yet**.

**What would need to change first:**
1. Add a recency window or change-point check, so a cohort whose recent rate departs from its pooled rate is withheld or reported as unstable.
2. Re-run on a freshly frozen seed with that guard frozen in advance.

**What already works:** the visibility, the censoring guard and the fallback behave as designed.

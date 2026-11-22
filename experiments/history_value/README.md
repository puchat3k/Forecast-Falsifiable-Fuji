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

## When does it help? (EXPLORATORY, post hoc: `explore.py` → `results/EXPLORATORY.md`)
These slices come from the already-scored run. They were not pre-registered and do not change the verdict.
- **The rate is current** (|rate − true base| ≤ 0.10, 116 cases): history **helps**, −0.0199 [−0.0387, −0.0002].
- **The rate is stale** (> 0.10, 117 cases): history **hurts**, +0.0132 [+0.0009, +0.0263].
- **Worst case:** a large requested shift on a stale rate hurts badly (+0.161, 7 cases).
- **More history is not better:** with 50+ records the result is +0.0053 (inconclusive). Long cohorts pool stale records.

So the useful regime is a cohort whose rate is current, and the reader cannot yet tell current from stale. That is the guard to build next.

**Independent cross-check:** frays-platform #310's own Fuji scoring path (`experiments/next-move-benchmark/history-value/score-with-310-harness.mjs`, through `lib/fuji_bridge.py`) reproduces the paired Brier scores exactly: 0.2614, 0.2545 and 0.2581 (n=233).

## v2: pre-registered regime test on a fresh seed (`frozen_v2/`, freeze commit `080e00e` before scoring)
**What v2 tests:**
- **Guard:** the reader gained an opt-in **stability guard** (`guards=['stability']`, rules in `RULES["stability"]`). It returns `WITHHELD_UNSTABLE` when the most recent 15 resolved records differ from the older ones by at least 0.20 with |z| ≥ 2. It uses only records visible at the cutoff.
- **Pre-registered hypothesis:** the adjusted forecast helps in the regime where Fuji, with the guard on, returns AVAILABLE.
- **Data:** a fresh seed, 20261123, that nobody had scored. The guard was designed after seeing v1.
- **v1 unchanged:** a v1 rerun on the new code is identical, because the guard is opt-in. The code drift is recorded in `results/results.json`.

```bash
python3 -m experiments.history_value.run --frozen experiments/history_value/frozen_v2 --results experiments/history_value/results_v2_A_no_guard
python3 -m experiments.history_value.run --frozen experiments/history_value/frozen_v2 --results experiments/history_value/results_v2_B_stability_guard --guards stability
```

**Results:**

| Arm (seed 20261123) | Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] |
|---|---|---|---|---|---|
| A, no guard | 250/370 | 0.2314 | 0.2497 | 0.2273 | −0.0041 [−0.0173, 0.0090], inconclusive |
| B, stability guard (the pre-registered regime) | 225/370 | 0.2382 | 0.2547 | 0.2354 | **−0.0027 [−0.0170, 0.0110], inconclusive** |

- **Arm B by cohort:** no cohort or period HURTS, and none HELPS. The fallback is unchanged on 100% of withheld cases (UNSTABLE 25, SPARSE 54, CENSORED 66).
- **The guard is imperfect:**
  - it caught 13 of the 68 cases after the change;
  - it also fired on 12 cases before the change, when the rate had not moved (false alarms).
- **v1 did not fully replicate:** Arm A shows no harm after the drift on this seed (−0.0040, inconclusive).
  - Its only pre-registered HELPS is the drift cohort before the change (−0.0083 [−0.0155, −0.0017]).
  - Rate alone is worse than unassisted on this seed (0.2497 vs 0.2314).
- **The exploratory "current rate" finding:** same direction on the fresh seed (current −0.009, stale +0.003), but not significant.

## When does history help? Answer across both seeds
- **No pre-registered, analyst-visible regime** was found in which the adjusted forecast reliably beats the unassisted one.
- **Overall effects are small:** −0.003 to −0.004 Brier, with every overall interval spanning zero.
- **History hurt** in one condition, on one seed: a stale rate after an approval-rate change.
- **History may help** when the rate is current (significant on seed 1, same direction on seed 2). The stability guard does not yet isolate that condition well enough.

## v3: pre-registered "when" test (`frozen_v3/`, freeze commit `7c2deaf` before scoring; fresh seed 20261124)
**Design:**
- **What varies on purpose:** how wrong the unassisted forecaster's base rate is. Prior error is 0, 0.10, 0.20 or 0.30 below a true 0.70, each in its own stable cohort. There is also one drifting cohort with prior error 0.20.
- **Reader:** the stability guard is on.
- **Hypotheses:**
  - **H1 (dose-response):** history helps at prior error 0.20 and 0.30, and does not hurt at 0.
  - **H2 (regime an analyst can see):** history helps where the visible gap |Fuji rate − the analyst's own mean forecast on the same visible records| is at least 0.10. Cases with a gap below 0.10 do not hurt.
- **Frozen:** the analysis script (`analyze_v3.py`) and the decision rule.

```bash
python3 -m experiments.history_value.run --frozen experiments/history_value/frozen_v3 --results experiments/history_value/results_v3 --guards stability
python3 -m experiments.history_value.analyze_v3
```

**Overall:**

| Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] |
|---|---|---|---|---|
| 560/657 (85%) | 0.2468 | 0.2311 | 0.2297 | **−0.0171 [−0.0250, −0.0089], HELPS** |

**H1, by prior error** (adjusted − unassisted):

| Prior error | Result | Verdict |
|---|---|---|
| 0.00 | +0.0020 [−0.0040, +0.0076] | no harm |
| 0.10 | **−0.0170 [−0.0288, −0.0047]** | HELPS |
| 0.20 | −0.0144 [−0.0304, +0.0022] | inconclusive (**the prediction missed here**) |
| 0.30 | **−0.0544 [−0.0812, −0.0268]** | HELPS |
| drifting, 0.20 | +0.0002 | no harm; the guard withheld 32 |

**H2, by visible gap:**

| Gap | Result | Verdict |
|---|---|---|
| ≥ 0.10 (n=345) | **−0.0254 [−0.0383, −0.0126]** | **HELPS** |
| < 0.10 (n=215) | −0.0037 [−0.0084, +0.0010] | no harm |

- **Fallback:** unchanged on 100% of withheld cases (SPARSE 64, UNSTABLE 33).
- **Pre-registered decision:** **EXPOSE in a shadow pilot, shown only when the guard passes and the visible gap ≥ 0.10.**

**Consistency check** (the same frozen gap rule applied to the earlier data; done after the v3 result, so it is not independent):
- **Gap ≥ 0.10:** inconclusive on v1 (+0.0005) and on v2 (−0.0006). In those generators the analyst's base-rate error was smaller (0.15 or less), and much of the gap came from drift.
- **So the gain depends on the analyst having a large, stable base-rate error.** A real pilot has to measure whether analysts actually do.

## v3 replication (`frozen_v3r/`, freeze commit `a7dccf5` before scoring; fresh seed 20261125)
**Design:** the same design, hypotheses, analysis and decision rule as v3. Pre-registered: the v3 result counts as replicated only if H2 is again HELPS.

```bash
python3 -m experiments.history_value.run --frozen experiments/history_value/frozen_v3r --results experiments/history_value/results_v3r --guards stability
python3 -m experiments.history_value.analyze_v3 experiments/history_value/results_v3r
```

**Overall:**

| Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] |
|---|---|---|---|---|
| 554/708 | 0.2288 | 0.2323 | 0.2091 | **−0.0197 [−0.0298, −0.0092], HELPS** |

**H2, by visible gap: replicated.**

| Gap | Result | Verdict |
|---|---|---|
| ≥ 0.10 (n=368) | **−0.0291 [−0.0440, −0.0140]** | **HELPS** |
| < 0.10 (n=186) | −0.0011 | no harm |

**H1, by prior error:**

| Prior error | Result | Verdict |
|---|---|---|
| 0.00 | +0.0019 | no harm |
| 0.10 | −0.0005 | inconclusive |
| 0.20 | **−0.0269** | HELPS |
| 0.30 | **−0.0346** | HELPS |
| drifting | −0.0510 | inconclusive; 81 withheld as UNSTABLE across the run |

- **Fallback:** unchanged on 100% of withheld cases.
- **H1 vs the original v3:** the predicted pattern (helps at 0.20 and 0.30, no harm at 0) now holds exactly. Across the two seeds, the 0.10 level helped once and was flat once.

## When does history help? Answer across all rounds
- **Helps:** when the analyst's own past forecasts on the same visible records are systematically off from Fuji's rate (gap ≥ 0.10) **and** the cohort is stable (the guard passes). In v3, the larger the base-rate error, the bigger the gain.
- **Does nothing:** when the analyst is already calibrated (prior error 0).
- **Can hurt:** when the rate is stale after a change and no guard is applied (v1).
- **Unproven:** whether real analysts show the large, stable error this regime needs.

## Verdicts under the frozen decision rules
- **v1 and v2:** unconditional exposure is **not** supported.
- **v3, and its pre-registered replication:** **conditional** exposure is supported: shadow only, evidence only, stability guard on, and shown only when the visible gap is at least 0.10.

**Recommended shadow pilot design:**
- The analyst locks an unassisted forecast in Fuji **before** seeing the rate.
- Then the gated rate is shown, and an adjusted forecast is locked.
- Both are scored on resolution, so the pilot measures itself.
- **Stop condition:** if, on 30+ resolved gated cases, the 95% interval of adjusted − unassisted is entirely above 0.

**Still unproven:** benefit on customer cases. These are synthetic results.

**What works:** visibility, the censoring, sparse and stability guards, and the unchanged fallback.

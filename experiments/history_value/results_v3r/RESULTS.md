# History-value replay: do Fuji's historical reference rates improve offer-approval forecasts?

> **SYNTHETIC method validation.** The seeded generator, the unassisted forecasts, the cutoff rule, the combine rule and this scoring plan were frozen in `frozen/` (commit before scoring; hashes re-verified at run time). These numbers say whether the method behaves as intended. **They are not evidence that customer cases improve.** SHADOW, forecast-only: nothing here changes an approval status or chooses a move.

## Paired Brier (cases where all three variants exist) and coverage (all cases)

| Group | Cases | Paired | Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] | Rate alone − unassisted [95% CI] | History made it worse | Full set (with fallback) Δ | Withheld (Fuji reasons) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 708 | 554 | 0.7820 | 0.2288 | 0.2323 | 0.2091 | -0.0197 [-0.0298, -0.0092] HELPS | 0.0035 [-0.0179, 0.0243] inconclusive | 201 of 554 | -0.0154 | WITHHELD_SPARSE 73, WITHHELD_UNSTABLE 81 |
| drift_prior_err_0.20 | 148 | 66 | 0.4460 | 0.2807 | 0.2407 | 0.2297 | -0.0510 [-0.1113, 0.0137] inconclusive | -0.0400 [-0.1326, 0.0574] inconclusive | 21 of 66 | -0.0227 | WITHHELD_SPARSE 16, WITHHELD_UNSTABLE 66 |
| prior_err_0.00 | 132 | 107 | 0.8110 | 0.2289 | 0.2369 | 0.2308 | 0.0019 [-0.0101, 0.0141] inconclusive | 0.0080 [-0.0272, 0.0435] inconclusive | 38 of 107 | 0.0016 | WITHHELD_SPARSE 14, WITHHELD_UNSTABLE 11 |
| prior_err_0.10 | 146 | 129 | 0.8840 | 0.2060 | 0.2348 | 0.2055 | -0.0005 [-0.0060, 0.0046] inconclusive | 0.0288 [-0.0040, 0.0607] inconclusive | 54 of 129 | -0.0005 | WITHHELD_SPARSE 14, WITHHELD_UNSTABLE 3 |
| prior_err_0.20 | 147 | 133 | 0.9050 | 0.2078 | 0.2172 | 0.1809 | -0.0269 [-0.0445, -0.0096] HELPS | 0.0095 [-0.0346, 0.0526] inconclusive | 42 of 133 | -0.0244 | WITHHELD_SPARSE 14 |
| prior_err_0.30 | 135 | 119 | 0.8810 | 0.2483 | 0.2378 | 0.2136 | -0.0346 [-0.0556, -0.0130] HELPS | -0.0105 [-0.0594, 0.0354] inconclusive | 46 of 119 | -0.0305 | WITHHELD_SPARSE 15, WITHHELD_UNSTABLE 1 |

Fuji core scoring cross-check (paired set): unassisted 0.2288 (n=554), rate_alone 0.2323 (n=554), adjusted 0.2091 (n=554).
Fallback leaves the unassisted forecast unchanged whenever Fuji withholds: **True**.

## Fallback when Fuji withholds (exact analyst-facing text)

**WITHHELD_SPARSE** — case `prior_err_0.30-000`: adjusted forecast = unassisted 0.2138 (unchanged). Reason: WITHHELD_SPARSE: 0 resolved < min_resolved 10

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=credit_committee, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-01-06T05:26:59.696349Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_SPARSE (0 resolved < min_resolved 10)
Observed rate: withheld
Cohort: eligible 0 | resolved 0 (0 approved, 0 not) | unresolved at cutoff 0 (not counted either way) | window still open 0 (not counted)
Not matched: other_field_values 573, not_locked_by_cutoff 135
Provenance: ledger sha256 d1bd8f667e95d085 | query sha256 b62e42cc372044a2 | 0 contributing records
```

**WITHHELD_UNSTABLE** — case `drift_prior_err_0.20-034`: adjusted forecast = unassisted 0.7651 (unchanged). Reason: WITHHELD_UNSTABLE: recent 15 rate 0.73 vs older 1.00 (z=-2.15)

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=legal, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-05-13T21:01:08.685384Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_UNSTABLE (recent 15 rate 0.73 vs older 1.00 (z=-2.15))
Observed rate: withheld
Cohort: eligible 30 | resolved 30 (26 approved, 4 not) | unresolved at cutoff 0 (not counted either way) | window still open 4 (not counted)
Not matched: other_field_values 560, not_locked_by_cutoff 114
Provenance: ledger sha256 d1bd8f667e95d085 | query sha256 0526c221214d37a2 | 30 contributing records: 0a8fdbcb, 0cdc4a47, 29d7b1ab, 357e362a, 36e4bfaf, 370df3ae, 37cd379e, 397777fa, 3f05e78f, 4ea52654, 56a91980, 63a56651, 693c695e, 79cb30f0, 88891bf5, 9671ef71, 9edf1cbe, a6a9a1e2, a7d324d4, af7b0643, b5107e83, bfa2cc72, c9b21f18, ca994026, d15fca3b, d192d0de, e3358069, f261a21d, f57c4168, fda4e847
```

## Where history made the forecast worse

By group: drift_prior_err_0.20 21, prior_err_0.00 38, prior_err_0.10 54, prior_err_0.20 42, prior_err_0.30 46.

| Case | Anchor | Approved | True base | Unassisted | Fuji rate (n) | Adjusted | Brier unassisted → adjusted |
|---|---|---|---|---|---|---|---|
| drift_prior_err_0.20-017 | 2026-03-12 | False | 0.7 | 0.519 | 1.0 (10) | 0.8752 | 0.2694 → 0.766 |
| drift_prior_err_0.20-020 | 2026-03-16 | False | 0.7 | 0.6097 | 1.0 (11) | 0.9174 | 0.3717 → 0.8416 |
| drift_prior_err_0.20-029 | 2026-04-26 | False | 0.7 | 0.4112 | 0.8929 (28) | 0.7639 | 0.1691 → 0.5835 |
| drift_prior_err_0.20-024 | 2026-03-31 | False | 0.7 | 0.3665 | 0.9091 (22) | 0.7097 | 0.1343 → 0.5037 |
| drift_prior_err_0.20-066 | 2026-09-25 | False | 0.7 | 0.5592 | 0.8095 (63) | 0.8259 | 0.3127 → 0.6821 |
| drift_prior_err_0.20-043 | 2026-06-16 | False | 0.7 | 0.4453 | 0.8205 (39) | 0.7533 | 0.1983 → 0.5675 |
| drift_prior_err_0.20-074 | 2026-10-27 | False | 0.35 | 0.545 | 0.8028 (71) | 0.8133 | 0.297 → 0.6615 |
| drift_prior_err_0.20-045 | 2026-06-26 | False | 0.7 | 0.4078 | 0.8293 (41) | 0.7228 | 0.1663 → 0.5224 |
| drift_prior_err_0.20-075 | 2026-11-02 | False | 0.35 | 0.4528 | 0.7917 (72) | 0.7388 | 0.205 → 0.5458 |
| drift_prior_err_0.20-042 | 2026-06-14 | False | 0.7 | 0.6943 | 0.8205 (39) | 0.8963 | 0.4821 → 0.8034 |

## Existing #310 frozen forecasts (reused; not pooled with synthetic cases)

| Case | Member | Horizon days | Unassisted p | Fuji status (reasons) | Adjusted | Brier unassisted |
|---|---|---|---|---|---|---|
| h3-supplier-outstanding-approval:r2:plain | plain | 51 | 0.55 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.55 (fallback) | 0.2025 |
| h3-supplier-outstanding-approval:r2:core_fuji_ap_nd | core_fuji_ap_nd | 82 | 0.6 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.6 (fallback) | 0.16 |
| c1-saas-renewal-term:r2:core_fuji_ap_nd | core_fuji_ap_nd | 30 | 0.45 | WITHHELD_SPARSE (0 resolved < min_resolved 10) | 0.45 (fallback) | 0.3025 |

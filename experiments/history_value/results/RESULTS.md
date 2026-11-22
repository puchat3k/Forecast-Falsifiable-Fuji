# History-value replay: do Fuji's historical reference rates improve offer-approval forecasts?

> **SYNTHETIC method validation.** The seeded generator, the unassisted forecasts, the cutoff rule, the combine rule and this scoring plan were frozen in `frozen/` (commit before scoring; hashes re-verified at run time). These numbers say whether the method behaves as intended. **They are not evidence that customer cases improve.** SHADOW, forecast-only: nothing here changes an approval status or chooses a move.

## Paired Brier (cases where all three variants exist) and coverage (all cases)

| Group | Cases | Paired | Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] | Rate alone − unassisted [95% CI] | History made it worse | Full set (with fallback) Δ | Withheld (Fuji reasons) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 360 | 233 | 0.6470 | 0.2614 | 0.2545 | 0.2581 | -0.0033 [-0.0147, 0.0087] inconclusive | -0.0069 [-0.0353, 0.0219] inconclusive | 86 of 233 | -0.0021 | WITHHELD_SPARSE 62, WITHHELD_CENSORED 65 |
| drift:after | 58 | 58 | 1.0000 | 0.3041 | 0.3669 | 0.3324 | 0.0283 [0.0057, 0.0518] HURTS | 0.0628 [0.0000, 0.1205] inconclusive | 30 of 58 | 0.0283 | – |
| drift:before | 54 | 40 | 0.7410 | 0.2048 | 0.1344 | 0.1679 | -0.0369 [-0.0753, 0.0028] inconclusive | -0.0704 [-0.1286, -0.0171] HELPS | 6 of 40 | -0.0273 | WITHHELD_SPARSE 14 |
| sparse | 15 | 4 | 0.2670 | 0.1448 | 0.2246 | 0.1516 | 0.0068 [-0.1138, 0.2050] inconclusive | 0.0798 [-0.1386, 0.4510] inconclusive | 1 of 4 | 0.0018 | WITHHELD_SPARSE 11 |
| stable | 147 | 131 | 0.8910 | 0.2633 | 0.2423 | 0.2560 | -0.0073 [-0.0195, 0.0043] inconclusive | -0.0210 [-0.0602, 0.0139] inconclusive | 49 of 131 | -0.0065 | WITHHELD_SPARSE 16 |
| unresolved | 86 | 0 | 0.0000 | – | – | – | – | – | 0 of 0 | 0.0000 | WITHHELD_SPARSE 21, WITHHELD_CENSORED 65 |

Fuji core scoring cross-check (paired set): unassisted 0.2614 (n=233), rate_alone 0.2545 (n=233), adjusted 0.2581 (n=233).
Fallback leaves the unassisted forecast unchanged whenever Fuji withholds: **True**.

## Fallback when Fuji withholds (exact analyst-facing text)

**WITHHELD_SPARSE** — case `unresolved-000`: adjusted forecast = unassisted 0.4588 (unchanged). Reason: WITHHELD_SPARSE: 0 resolved < min_resolved 10

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=cfo, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-01-06T06:00:29.493952Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_SPARSE (0 resolved < min_resolved 10)
Observed rate: withheld
Cohort: eligible 0 | resolved 0 (0 approved, 0 not) | unresolved at cutoff 0 (not counted either way) | window still open 0 (not counted)
Not matched: other_field_values 274, not_locked_by_cutoff 86
Provenance: ledger sha256 61a0e20476b1b490 | query sha256 424c21fba65c6e5d | 0 contributing records
```

**WITHHELD_CENSORED** — case `unresolved-021`: adjusted forecast = unassisted 0.4062 (unchanged). Reason: WITHHELD_CENSORED: unresolved share 8/18 > 0.25

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=cfo, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-05-15T23:50:32.273849Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_CENSORED (unresolved share 8/18 > 0.25)
Observed rate: withheld
Cohort: eligible 18 | resolved 10 (10 approved, 0 not) | unresolved at cutoff 8 (not counted either way) | window still open 3 (not counted)
  unresolved: 1444b54eb8bb window closed 2026-03-09T09:07:04.219336Z: no resolution recorded
  unresolved: 54c9f0e0e04d window closed 2026-02-19T05:42:00.977171Z: no resolution recorded
  unresolved: 6437d9edd6d7 window closed 2026-04-26T14:39:01.725909Z: no resolution recorded
  unresolved: 726af759d904 window closed 2026-03-11T00:03:09.450927Z: no resolution recorded
  unresolved: 926296230b28 window closed 2026-05-12T21:10:50.041240Z: resolution recorded after the cutoff
  unresolved: b5c8b8d3e36a window closed 2026-05-14T16:34:48.966374Z: no resolution recorded
  unresolved: e4556eb5cd59 window closed 2026-01-30T05:47:14.029204Z: no resolution recorded
  unresolved: f9bc77adc163 window closed 2026-04-21T16:19:08.341790Z: no resolution recorded
Not matched: other_field_values 274, not_locked_by_cutoff 65
Provenance: ledger sha256 61a0e20476b1b490 | query sha256 4833cab53e821bde | 10 contributing records: 395d0e8e, 5fe2d97e, 8a21f51c, 8e08cdfb, 94a55a6c, a44b11a4, bf8ce2af, c445aef6, c9d89400, fe99213b
```

## Where history made the forecast worse

By group: drift:after 30, drift:before 6, sparse 1, stable 49.

| Case | Anchor | Approved | True base | Unassisted | Fuji rate (n) | Adjusted | Brier unassisted → adjusted |
|---|---|---|---|---|---|---|---|
| sparse-011 | 2027-04-10 | False | 0.85 | 0.4362 | 0.9091 (11) | 0.7029 | 0.1903 → 0.4941 |
| drift-058 | 2026-10-09 | False | 0.35 | 0.5669 | 0.8491 (53) | 0.768 | 0.3214 → 0.5898 |
| drift-037 | 2026-08-13 | False | 0.8 | 0.6589 | 0.8529 (34) | 0.8367 | 0.4341 → 0.7001 |
| drift-057 | 2026-10-08 | False | 0.35 | 0.6455 | 0.8491 (53) | 0.8216 | 0.4167 → 0.675 |
| drift-056 | 2026-10-06 | False | 0.35 | 0.6626 | 0.8491 (53) | 0.8324 | 0.439 → 0.6929 |
| drift-053 | 2026-09-26 | False | 0.8 | 0.5883 | 0.8431 (51) | 0.7716 | 0.3461 → 0.5954 |
| drift-059 | 2026-10-15 | False | 0.35 | 0.5925 | 0.8333 (54) | 0.7702 | 0.3511 → 0.5932 |
| drift-060 | 2026-10-16 | False | 0.35 | 0.5963 | 0.8333 (54) | 0.7729 | 0.3556 → 0.5974 |
| drift-021 | 2026-05-22 | False | 0.8 | 0.7757 | 0.8571 (21) | 0.9131 | 0.6017 → 0.8338 |
| drift-027 | 2026-06-25 | False | 0.8 | 0.7954 | 0.84 (25) | 0.9144 | 0.6327 → 0.8361 |

## Existing #310 frozen forecasts (reused; not pooled with synthetic cases)

| Case | Member | Horizon days | Unassisted p | Fuji status (reasons) | Adjusted | Brier unassisted |
|---|---|---|---|---|---|---|
| h3-supplier-outstanding-approval:r2:plain | plain | 51 | 0.55 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.55 (fallback) | 0.2025 |
| h3-supplier-outstanding-approval:r2:core_fuji_ap_nd | core_fuji_ap_nd | 82 | 0.6 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.6 (fallback) | 0.16 |
| c1-saas-renewal-term:r2:core_fuji_ap_nd | core_fuji_ap_nd | 30 | 0.45 | WITHHELD_SPARSE (0 resolved < min_resolved 10) | 0.45 (fallback) | 0.3025 |

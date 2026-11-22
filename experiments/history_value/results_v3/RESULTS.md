# History-value replay: do Fuji's historical reference rates improve offer-approval forecasts?

> **SYNTHETIC method validation.** The seeded generator, the unassisted forecasts, the cutoff rule, the combine rule and this scoring plan were frozen in `frozen/` (commit before scoring; hashes re-verified at run time). These numbers say whether the method behaves as intended. **They are not evidence that customer cases improve.** SHADOW, forecast-only: nothing here changes an approval status or chooses a move.

## Paired Brier (cases where all three variants exist) and coverage (all cases)

| Group | Cases | Paired | Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] | Rate alone − unassisted [95% CI] | History made it worse | Full set (with fallback) Δ | Withheld (Fuji reasons) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 657 | 560 | 0.8520 | 0.2468 | 0.2311 | 0.2297 | -0.0171 [-0.0250, -0.0089] HELPS | -0.0157 [-0.0346, 0.0044] inconclusive | 225 of 560 | -0.0146 | WITHHELD_SPARSE 64, WITHHELD_UNSTABLE 33 |
| drift_prior_err_0.20 | 133 | 89 | 0.6690 | 0.2527 | 0.2526 | 0.2529 | 0.0002 [-0.0214, 0.0232] inconclusive | -0.0001 [-0.0497, 0.0491] inconclusive | 39 of 89 | 0.0001 | WITHHELD_SPARSE 12, WITHHELD_UNSTABLE 32 |
| prior_err_0.00 | 136 | 124 | 0.9120 | 0.2356 | 0.2380 | 0.2375 | 0.0020 [-0.0040, 0.0076] inconclusive | 0.0024 [-0.0309, 0.0347] inconclusive | 76 of 124 | 0.0018 | WITHHELD_SPARSE 12 |
| prior_err_0.10 | 138 | 124 | 0.8990 | 0.2264 | 0.2078 | 0.2094 | -0.0170 [-0.0288, -0.0047] HELPS | -0.0186 [-0.0570, 0.0188] inconclusive | 34 of 124 | -0.0152 | WITHHELD_SPARSE 13, WITHHELD_UNSTABLE 1 |
| prior_err_0.20 | 125 | 110 | 0.8800 | 0.2347 | 0.2319 | 0.2203 | -0.0144 [-0.0304, 0.0022] inconclusive | -0.0028 [-0.0474, 0.0386] inconclusive | 38 of 110 | -0.0127 | WITHHELD_SPARSE 15 |
| prior_err_0.30 | 125 | 113 | 0.9040 | 0.2888 | 0.2316 | 0.2344 | -0.0544 [-0.0812, -0.0268] HELPS | -0.0571 [-0.1102, -0.0042] HELPS | 38 of 113 | -0.0492 | WITHHELD_SPARSE 12 |

Fuji core scoring cross-check (paired set): unassisted 0.2468 (n=560), rate_alone 0.2311 (n=560), adjusted 0.2297 (n=560).
Fallback leaves the unassisted forecast unchanged whenever Fuji withholds: **True**.

## Fallback when Fuji withholds (exact analyst-facing text)

**WITHHELD_SPARSE** — case `prior_err_0.20-000`: adjusted forecast = unassisted 0.7982 (unchanged). Reason: WITHHELD_SPARSE: 0 resolved < min_resolved 10

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=cfo, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-01-05T15:28:47.973833Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_SPARSE (0 resolved < min_resolved 10)
Observed rate: withheld
Cohort: eligible 0 | resolved 0 (0 approved, 0 not) | unresolved at cutoff 0 (not counted either way) | window still open 0 (not counted)
Not matched: other_field_values 532, not_locked_by_cutoff 125
Provenance: ledger sha256 b283b74371b7f897 | query sha256 8b9a1a1f796263e9 | 0 contributing records
```

**WITHHELD_UNSTABLE** — case `drift_prior_err_0.20-090`: adjusted forecast = unassisted 0.1202 (unchanged). Reason: WITHHELD_UNSTABLE: recent 15 rate 0.27 vs older 0.68 (z=-2.96)

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=legal, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-12-23T18:52:44.460209Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_UNSTABLE (recent 15 rate 0.27 vs older 0.68 (z=-2.96))
Observed rate: withheld
Cohort: eligible 90 | resolved 89 (54 approved, 35 not) | unresolved at cutoff 1 (not counted either way) | window still open 0 (not counted)
  unresolved: b4847e4ca8e9 window closed 2026-12-22T16:18:30.646363Z: resolution recorded after the cutoff
Not matched: other_field_values 524, not_locked_by_cutoff 43
Provenance: ledger sha256 b283b74371b7f897 | query sha256 d0ba86bc1f9ddc0c | 89 contributing records: 0018fcc4, 02b677be, 087a354f, 0a8fdbcb, 0cdc4a47, 0f717c1a, 11de55b4, 19d252c8, 1a1ad5a8, 1ace980f, 1b90b171, 25684632, 29d7b1ab, 35356241, 357e362a, 36e4bfaf, 370df3ae, 37cd379e, 388111e3, 397777fa, 3d3da2b4, 3d8f7cd1, 3f05e78f, 3fc26dcf, 40b3a632, 420432a6, 447013a9, 4693ab82, 46aa0869, 4ea52654, 56a91980, 5b4ad3fb, 5c7c54b5, 60397b00, 6262ddb9, 63a56651, 6812e39d, 693c695e, 733c2eb6, 73c2ae7a, 7421cfd1, 75b35ccd, 75e64d62, 768ae940, 787ae405, 79cb30f0, 7b6ba4f8, 7c3d2051, 8423a101, 88891bf5, 8ea50aea, 916b16bd, 93edd675, 9671ef71, 9edf1cbe, 9fd991b2, a1ae36a8, a5be2c43, a6a9a1e2, a7d324d4, af7b0643, b5107e83, b8caae10, baf35656, bbd7c583, bc40b90c, be0c39cc, bf8f3782, bfa2cc72, c9b21f18, ca994026, ce6de53d, d15fca3b, d192d0de, d2d15d8c, d5962ff7, deaeefea, e3358069, e6b2faa8, e836d0b6, e8aa1aec, e9fb8765, f22c3e59, f261a21d, f2f3016b, f3753e2a, f42d53fd, f57c4168, fda4e847
```

## Where history made the forecast worse

By group: drift_prior_err_0.20 39, prior_err_0.00 76, prior_err_0.10 34, prior_err_0.20 38, prior_err_0.30 38.

| Case | Anchor | Approved | True base | Unassisted | Fuji rate (n) | Adjusted | Brier unassisted → adjusted |
|---|---|---|---|---|---|---|---|
| prior_err_0.30-112 | 2027-05-14 | False | 0.7 | 0.514 | 0.6422 (109) | 0.7282 | 0.2642 → 0.5303 |
| prior_err_0.30-120 | 2027-06-17 | False | 0.7 | 0.4851 | 0.6555 (119) | 0.7063 | 0.2353 → 0.4989 |
| prior_err_0.30-111 | 2027-05-10 | False | 0.7 | 0.5747 | 0.6389 (108) | 0.7706 | 0.3303 → 0.5938 |
| prior_err_0.30-103 | 2027-04-08 | False | 0.7 | 0.5295 | 0.6373 (102) | 0.7316 | 0.2804 → 0.5352 |
| prior_err_0.30-071 | 2026-11-11 | False | 0.7 | 0.6015 | 0.6364 (66) | 0.7781 | 0.3618 → 0.6054 |
| prior_err_0.30-072 | 2026-11-13 | False | 0.7 | 0.669 | 0.6364 (66) | 0.8245 | 0.4476 → 0.6798 |
| prior_err_0.30-097 | 2027-02-24 | False | 0.7 | 0.7348 | 0.6392 (97) | 0.8729 | 0.5399 → 0.762 |
| prior_err_0.30-076 | 2026-11-18 | False | 0.7 | 0.4174 | 0.6364 (66) | 0.6247 | 0.1742 → 0.3903 |
| drift_prior_err_0.20-036 | 2026-05-27 | False | 0.7 | 0.6227 | 0.7188 (32) | 0.7761 | 0.3878 → 0.6023 |
| prior_err_0.30-048 | 2026-08-29 | False | 0.7 | 0.5798 | 0.6429 (42) | 0.7379 | 0.3362 → 0.5445 |

## Existing #310 frozen forecasts (reused; not pooled with synthetic cases)

| Case | Member | Horizon days | Unassisted p | Fuji status (reasons) | Adjusted | Brier unassisted |
|---|---|---|---|---|---|---|
| h3-supplier-outstanding-approval:r2:plain | plain | 51 | 0.55 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.55 (fallback) | 0.2025 |
| h3-supplier-outstanding-approval:r2:core_fuji_ap_nd | core_fuji_ap_nd | 82 | 0.6 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.6 (fallback) | 0.16 |
| c1-saas-renewal-term:r2:core_fuji_ap_nd | core_fuji_ap_nd | 30 | 0.45 | WITHHELD_SPARSE (0 resolved < min_resolved 10) | 0.45 (fallback) | 0.3025 |

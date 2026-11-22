# History-value replay: do Fuji's historical reference rates improve offer-approval forecasts?

> **SYNTHETIC method validation.** The seeded generator, the unassisted forecasts, the cutoff rule, the combine rule and this scoring plan were frozen in `frozen/` (commit before scoring; hashes re-verified at run time). These numbers say whether the method behaves as intended. **They are not evidence that customer cases improve.** SHADOW, forecast-only: nothing here changes an approval status or chooses a move.

## Paired Brier (cases where all three variants exist) and coverage (all cases)

| Group | Cases | Paired | Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] | Rate alone − unassisted [95% CI] | History made it worse | Full set (with fallback) Δ | Withheld (Fuji reasons) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 370 | 225 | 0.6080 | 0.2382 | 0.2547 | 0.2354 | -0.0027 [-0.0170, 0.0110] inconclusive | 0.0166 [-0.0167, 0.0492] inconclusive | 89 of 225 | -0.0017 | WITHHELD_SPARSE 54, WITHHELD_CENSORED 66, WITHHELD_UNSTABLE 25 |
| drift:after | 68 | 55 | 0.8090 | 0.2866 | 0.3130 | 0.2843 | -0.0022 [-0.0144, 0.0101] inconclusive | 0.0264 [-0.0198, 0.0732] inconclusive | 25 of 55 | -0.0018 | WITHHELD_UNSTABLE 13 |
| drift:before | 51 | 26 | 0.5100 | 0.2149 | 0.1949 | 0.2129 | -0.0021 [-0.0081, 0.0038] inconclusive | -0.0201 [-0.1018, 0.0528] inconclusive | 13 of 26 | -0.0010 | WITHHELD_SPARSE 13, WITHHELD_UNSTABLE 12 |
| sparse | 15 | 5 | 0.3330 | 0.3110 | 0.3266 | 0.3328 | 0.0218 [-0.1289, 0.1725] inconclusive | 0.0155 [-0.2794, 0.3105] inconclusive | 2 of 5 | 0.0073 | WITHHELD_SPARSE 10 |
| stable | 153 | 139 | 0.9080 | 0.2207 | 0.2403 | 0.2168 | -0.0039 [-0.0262, 0.0179] inconclusive | 0.0195 [-0.0261, 0.0639] inconclusive | 49 of 139 | -0.0036 | WITHHELD_SPARSE 14 |
| unresolved | 83 | 0 | 0.0000 | – | – | – | – | – | 0 of 0 | 0.0000 | WITHHELD_SPARSE 17, WITHHELD_CENSORED 66 |

Fuji core scoring cross-check (paired set): unassisted 0.2382 (n=225), rate_alone 0.2547 (n=225), adjusted 0.2354 (n=225).
Fallback leaves the unassisted forecast unchanged whenever Fuji withholds: **True**.

## Fallback when Fuji withholds (exact analyst-facing text)

**WITHHELD_SPARSE** — case `unresolved-000`: adjusted forecast = unassisted 0.2685 (unchanged). Reason: WITHHELD_SPARSE: 0 resolved < min_resolved 10

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=cfo, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-01-07T04:21:25.192136Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_SPARSE (0 resolved < min_resolved 10)
Observed rate: withheld
Cohort: eligible 0 | resolved 0 (0 approved, 0 not) | unresolved at cutoff 0 (not counted either way) | window still open 0 (not counted)
Not matched: other_field_values 287, not_locked_by_cutoff 83
Provenance: ledger sha256 fb86e48b63091de9 | query sha256 779359891ff6850a | 0 contributing records
```

**WITHHELD_CENSORED** — case `unresolved-017`: adjusted forecast = unassisted 0.5674 (unchanged). Reason: WITHHELD_CENSORED: unresolved share 6/16 > 0.25

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=cfo, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-05-29T14:36:13.893299Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_CENSORED (unresolved share 6/16 > 0.25)
Observed rate: withheld
Cohort: eligible 16 | resolved 10 (9 approved, 1 not) | unresolved at cutoff 6 (not counted either way) | window still open 1 (not counted)
  unresolved: 5fe2d97e935d window closed 2026-04-29T07:09:15.338132Z: no resolution recorded
  unresolved: 6437d9edd6d7 window closed 2026-04-25T23:00:40.882712Z: no resolution recorded
  unresolved: 726af759d904 window closed 2026-03-28T13:05:17.389619Z: no resolution recorded
  unresolved: 926296230b28 window closed 2026-05-06T12:51:31.825158Z: no resolution recorded
  unresolved: a44b11a4aec9 window closed 2026-02-27T11:46:18.737808Z: no resolution recorded
  unresolved: c445aef65869 window closed 2026-04-17T22:17:16.592341Z: no resolution recorded
Not matched: other_field_values 287, not_locked_by_cutoff 66
Provenance: ledger sha256 fb86e48b63091de9 | query sha256 0a5799d4d8a5a218 | 10 contributing records: 1444b54e, 54c9f0e0, 8a21f51c, 8e08cdfb, 94a55a6c, b5c8b8d3, bf8ce2af, e4556eb5, f9bc77ad, fe99213b
```

**WITHHELD_UNSTABLE** — case `drift-039`: adjusted forecast = unassisted 0.9318 (unchanged). Reason: WITHHELD_UNSTABLE: recent 15 rate 0.93 vs older 0.58 (z=2.36)

```text
HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)
Question: Was the offer approved by the named approver within horizon_days of being submitted for approval?
Event: family=offer_approval, version=1, approver_role=procurement, offer_side=vendor, horizon_days=14
Decision cutoff: 2026-07-06T17:01:22.868931Z | classification: synthetic | rules: fuji.history.v1
Status: WITHHELD_UNSTABLE (recent 15 rate 0.93 vs older 0.58 (z=2.36))
Observed rate: withheld
Cohort: eligible 39 | resolved 39 (28 approved, 11 not) | unresolved at cutoff 0 (not counted either way) | window still open 0 (not counted)
Not matched: other_field_values 251, not_locked_by_cutoff 80
Provenance: ledger sha256 fb86e48b63091de9 | query sha256 144cc10b1babe7d9 | 39 contributing records: 0ec4513b, 1183acff, 12f7a737, 167b3e55, 1bf5ab95, 245ce944, 2a0152e4, 2c253df3, 2e6e365b, 3f788690, 4b1634d3, 4be1069d, 502d8b35, 5aafeb4d, 82885fb8, 8f25277e, 91496cfc, 98c506f0, 99afcd6c, 9b19c6e3, a3238139, a84a730a, adadaf13, aecafa90, b298b671, b2b7e35b, b2f81bac, b327b24c, b68385da, bd0a052c, c3ccf5b7, c772f516, cf09bc61, d64cee52, d7cc324e, d8a22f29, f199b85d, f8932254, fa21fc8a
```

## Where history made the forecast worse

By group: drift:after 25, drift:before 13, sparse 2, stable 49.

| Case | Anchor | Approved | True base | Unassisted | Fuji rate (n) | Adjusted | Brier unassisted → adjusted |
|---|---|---|---|---|---|---|---|
| stable-019 | 2026-03-12 | False | 0.7 | 0.4229 | 0.9286 (14) | 0.7552 | 0.1788 → 0.5703 |
| stable-018 | 2026-03-06 | False | 0.7 | 0.4482 | 0.9091 (11) | 0.7393 | 0.2009 → 0.5466 |
| stable-014 | 2026-02-28 | False | 0.7 | 0.4881 | 0.9 (10) | 0.7524 | 0.2382 → 0.5661 |
| stable-021 | 2026-03-22 | False | 0.7 | 0.5935 | 0.8421 (19) | 0.7915 | 0.3522 → 0.6265 |
| sparse-010 | 2026-10-19 | False | 0.85 | 0.6701 | 0.9 (10) | 0.8341 | 0.449 → 0.6957 |
| stable-065 | 2026-07-19 | False | 0.7 | 0.53 | 0.7541 (61) | 0.7172 | 0.2809 → 0.5144 |
| stable-069 | 2026-07-24 | False | 0.7 | 0.5192 | 0.7541 (61) | 0.7083 | 0.2696 → 0.5017 |
| stable-067 | 2026-07-20 | False | 0.7 | 0.6557 | 0.7541 (61) | 0.8107 | 0.4299 → 0.6572 |
| stable-035 | 2026-04-29 | False | 0.7 | 0.6442 | 0.7742 (31) | 0.7933 | 0.415 → 0.6293 |
| sparse-013 | 2027-03-10 | False | 0.85 | 0.5216 | 0.8462 (13) | 0.6948 | 0.2721 → 0.4827 |

## Existing #310 frozen forecasts (reused; not pooled with synthetic cases)

| Case | Member | Horizon days | Unassisted p | Fuji status (reasons) | Adjusted | Brier unassisted |
|---|---|---|---|---|---|---|
| h3-supplier-outstanding-approval:r2:plain | plain | 51 | 0.55 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.55 (fallback) | 0.2025 |
| h3-supplier-outstanding-approval:r2:core_fuji_ap_nd | core_fuji_ap_nd | 82 | 0.6 | WITHHELD_INCOMPATIBLE (horizon_days_not_allowed) | 0.6 (fallback) | 0.16 |
| c1-saas-renewal-term:r2:core_fuji_ap_nd | core_fuji_ap_nd | 30 | 0.45 | WITHHELD_SPARSE (0 resolved < min_resolved 10) | 0.45 (fallback) | 0.3025 |

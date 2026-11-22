# v3 pre-registered analysis (synthetic; SHADOW, forecast-only)

## H1: dose-response (adjusted − unassisted Brier, by the unassisted forecaster's prior error)

- drift_prior_err_0.20: -0.0510 [-0.1113, +0.0137] inconclusive (n=66, worse 21)
- prior_err_0.00: +0.0019 [-0.0101, +0.0141] inconclusive (n=107, worse 38)
- prior_err_0.10: -0.0005 [-0.0060, +0.0046] inconclusive (n=129, worse 54)
- prior_err_0.20: -0.0269 [-0.0445, -0.0096] HELPS (n=133, worse 42)
- prior_err_0.30: -0.0346 [-0.0556, -0.0130] HELPS (n=119, worse 46)

## H2: analyst-visible regime (gap = |Fuji rate − analyst's own mean on the same records|, threshold 0.1)

- gap >= 0.1: -0.0291 [-0.0440, -0.0140] HELPS (n=368, worse 126)
- gap < 0.1: -0.0011 [-0.0062, +0.0038] inconclusive (n=186, worse 75)

Coverage: adjusted ran on 554/708; regime (gap ≥ 0.1) on 368/708. Withheld: {'WITHHELD_SPARSE': 73, 'WITHHELD_UNSTABLE': 81}. Fallback unchanged: True.

**Pre-registered decision: EXPOSE in shadow pilot, shown only when the guard passes and the visible gap >= 0.10**

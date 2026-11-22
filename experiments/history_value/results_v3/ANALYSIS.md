# v3 pre-registered analysis (synthetic; SHADOW, forecast-only)

## H1: dose-response (adjusted − unassisted Brier, by the unassisted forecaster's prior error)

- drift_prior_err_0.20: +0.0002 [-0.0214, +0.0232] inconclusive (n=89, worse 39)
- prior_err_0.00: +0.0020 [-0.0040, +0.0076] inconclusive (n=124, worse 76)
- prior_err_0.10: -0.0170 [-0.0288, -0.0047] HELPS (n=124, worse 34)
- prior_err_0.20: -0.0144 [-0.0304, +0.0022] inconclusive (n=110, worse 38)
- prior_err_0.30: -0.0544 [-0.0812, -0.0268] HELPS (n=113, worse 38)

## H2: analyst-visible regime (gap = |Fuji rate − analyst's own mean on the same records|, threshold 0.1)

- gap >= 0.1: -0.0254 [-0.0383, -0.0126] HELPS (n=345, worse 121)
- gap < 0.1: -0.0037 [-0.0084, +0.0010] inconclusive (n=215, worse 104)

Coverage: adjusted ran on 560/657; regime (gap ≥ 0.1) on 345/657. Withheld: {'WITHHELD_SPARSE': 64, 'WITHHELD_UNSTABLE': 33}. Fallback unchanged: True.

**Pre-registered decision: EXPOSE in shadow pilot, shown only when the guard passes and the visible gap >= 0.10**

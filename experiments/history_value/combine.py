"""Frozen combination rule (see frozen/protocol.json). Forecast-only: returns a probability, nothing else."""
from __future__ import annotations

import math

CLIP = (0.02, 0.98)
SHRINK_K = 10


def _logit(p):
    p = min(max(p, CLIP[0]), CLIP[1])
    return math.log(p / (1 - p))


def adjust(p_unassisted, history_result, contributing_p_unassisted):
    """Return (p_adjusted, applied, reason).

    history_result: output of forecast_fuji.history.reference_rate().
    contributing_p_unassisted: the frozen unassisted forecasts of the records in history_result["cohort"].
    If Fuji withholds the rate, the unassisted forecast is returned unchanged (fallback) with Fuji's reason.
    """
    if history_result["status"] != "AVAILABLE":
        return p_unassisted, False, history_result["status"] + (": " + "; ".join(history_result["reasons"]) if history_result["reasons"] else "")
    n = history_result["rate"]["denominator"]
    r = history_result["rate"]["observed"]
    m = sum(contributing_p_unassisted) / len(contributing_p_unassisted)
    lam = n / (n + SHRINK_K)
    x = math.log(p_unassisted / (1 - p_unassisted)) + lam * (_logit(r) - _logit(m))
    return 1 / (1 + math.exp(-x)), True, f"adjusted with n={n}, r={r:.3f}, m={m:.3f}, lambda={lam:.3f}"

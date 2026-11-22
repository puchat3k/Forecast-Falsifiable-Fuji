"""Step 1 (run once, committed before any scoring): freeze the replay cases, the unassisted forecasts, the cutoff
rule, the combination rule and the scoring plan.

    python3 -m experiments.history_value.freeze      # writes experiments/history_value/frozen/*

SYNTHETIC. The generator validates the METHOD (does a time-ordered, visibility-correct reference rate help a
forecaster that has case evidence but a mis-set prior?). It is not evidence that customer cases improve.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
FROZEN = HERE / "frozen"
SEED = 20261122
UTC = timezone.utc
START, END = datetime(2026, 1, 5, 9, tzinfo=UTC), datetime(2027, 6, 30, 9, tzinfo=UTC)

# Cohorts (offer_approval family, offer_side=vendor). base(t) is the true approval probability for a typical case.
COHORTS = {
    "stable": {"approver_role": "deal_desk", "horizon_days": 14, "mean_gap_days": 4,
               "base": [["2026-01-01", 0.70]], "analyst_prior": 0.55,
               "late": {"approved": 0.05, "not_approved": 0.05}, "never": {"approved": 0.0, "not_approved": 0.0}},
    "drift": {"approver_role": "procurement", "horizon_days": 14, "mean_gap_days": 5,
              "base": [["2026-01-01", 0.80], ["2026-10-01", 0.35]], "analyst_prior": 0.65,
              "late": {"approved": 0.05, "not_approved": 0.05}, "never": {"approved": 0.0, "not_approved": 0.0}},
    "unresolved": {"approver_role": "cfo", "horizon_days": 14, "mean_gap_days": 6,
                   "base": [["2026-01-01", 0.55]], "analyst_prior": 0.50,
                   # Rejections are often never written back; approvals usually are (non-random missingness).
                   "late": {"approved": 0.10, "not_approved": 0.30}, "never": {"approved": 0.10, "not_approved": 0.60}},
    "sparse": {"approver_role": "legal", "horizon_days": 7, "mean_gap_days": 45,
               "base": [["2026-01-01", 0.85]], "analyst_prior": 0.60,
               "late": {"approved": 0.05, "not_approved": 0.05}, "never": {"approved": 0.0, "not_approved": 0.0}},
}
CASE_SD = 0.8         # spread of case-level log-odds around the cohort base
ANALYST_NOISE_SD = 0.6
ANALYST_SLOPE = 1.0   # the analyst reads case evidence correctly but starts from a mis-set prior

PROTOCOL = {
    "schema": "fuji.history-value.protocol.v1",
    "status": "FROZEN before scoring",
    "mode": "SHADOW, forecast-only: no approval status, no move, no action",
    "data": "SYNTHETIC (seeded generator in freeze.py); validates the method only",
    "seed": SEED,
    "cohorts": COHORTS,
    "generator": {"case_sd": CASE_SD, "analyst_noise_sd": ANALYST_NOISE_SD, "analyst_slope": ANALYST_SLOPE,
                  "outcome": "Bernoulli(sigmoid(logit(base(anchor)) + case_effect))",
                  "unassisted_forecast": "sigmoid(logit(analyst_prior) + slope*(case_effect + noise)), frozen per case"},
    "cutoff_rule": "Each case is forecast at its own decision time: cutoff = anchor_at (when the offer was submitted "
                   "for approval). History = forecast_fuji.history.reference_rate(cutoff=anchor_at, own case excluded); "
                   "the reader admits only records locked, window-closed, observed AND recorded by the cutoff.",
    "variants": {
        "unassisted": "the frozen unassisted forecast p_u",
        "rate_alone": "Fuji's observed rate k/n when status is AVAILABLE; no forecast otherwise",
        "adjusted": "when AVAILABLE: logit(p_adj) = logit(p_u) + lam*(logit(r) - logit(m)), lam = n/(n+10), "
                    "r = k/n, m = mean p_u over the SAME contributing records (the analyst's own visible bias), "
                    "r and m clipped to [0.02, 0.98]; when WITHHELD: fallback p_adj = p_u (unchanged)",
    },
    "scoring": {
        "metric": "Brier (p - outcome)^2; lower is better; computed by Fuji core resolve() and cross-checked",
        "paired_set": "cases where all three variants exist (rate AVAILABLE)",
        "coverage": "share of ALL cases where the rate is AVAILABLE (= adjusted forecast actually adjusts), "
                    "with Fuji's withhold reasons counted",
        "uncertainty": "case-resampling bootstrap, 4000 draws, seed 7, 95% percentile interval of mean paired difference",
        "harm": "cases where adjusted Brier > unassisted Brier, counted and listed; drift cohort split at 2026-10-01",
        "full_set": "adjusted-with-fallback vs unassisted over ALL cases (fallback cases contribute 0 difference)",
    },
    "existing_system_slice": "Reuse of frozen predictions from frays-platform #310 round 2 "
        "(tests/fixtures/next_move_round2_fuji.sqlite): every proposition whose statement mentions approval is put "
        "through the same reader and combine rule with its own case cutoff; scored with its #310 resolution. "
        "Reported separately; never pooled with the synthetic cases.",
    "decision_rule": [
        "History HELPS a cohort/period if the 95% interval of (adjusted - unassisted) is entirely below 0; HURTS if "
        "entirely above 0; otherwise inconclusive.",
        "Recommend exposing the signal to analysts in a shadow pilot (evidence only) if the paired difference overall "
        "is below 0 with its interval below 0 AND every withheld case falls back unchanged. If any cohort/period HURTS, "
        "the recommendation must name the condition (e.g. drift) and the guard needed before the pilot.",
        "Synthetic results never count as evidence of customer-case improvement.",
    ],
}


def logit(p):
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def base_at(cohort, t):
    b = None
    for since, p in cohort["base"]:
        if t >= datetime.fromisoformat(since).replace(tzinfo=UTC):
            b = p
    return b


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def generate():
    rng = random.Random(SEED)
    cases = []
    for name, c in COHORTS.items():
        t = START + timedelta(days=rng.uniform(0, c["mean_gap_days"]))
        i = 0
        while t < END:
            effect = rng.gauss(0, CASE_SD)
            p_true = sigmoid(logit(base_at(c, t)) + effect)
            approved = rng.random() < p_true
            p_u = sigmoid(logit(c["analyst_prior"]) + ANALYST_SLOPE * (effect + rng.gauss(0, ANALYST_NOISE_SD)))
            closes = t + timedelta(days=c["horizon_days"])
            observed = (t + timedelta(days=rng.uniform(0.5, c["horizon_days"] - 0.5)) if approved
                        else (closes if rng.random() < 0.5 else t + timedelta(days=rng.uniform(0.5, c["horizon_days"] - 0.5))))
            key = "approved" if approved else "not_approved"
            u = rng.random()
            if u < c["never"][key]:
                recorded = None
            elif u < c["never"][key] + c["late"][key]:
                recorded = observed + timedelta(days=rng.uniform(20, 60))
            else:
                recorded = observed + timedelta(hours=rng.uniform(1, 48))
            cases.append({"case_key": f"{name}-{i:03d}", "cohort": name, "approver_role": c["approver_role"],
                          "offer_side": "vendor", "horizon_days": c["horizon_days"],
                          "anchor_at": iso(t), "p_unassisted": round(p_u, 4),
                          "observed_at": iso(observed), "recorded_at": iso(recorded), "approved": approved,
                          "true_base": base_at(c, t)})
            i += 1
            t += timedelta(days=rng.expovariate(1 / c["mean_gap_days"]))
    cases.sort(key=lambda x: (x["anchor_at"], x["case_key"]))
    return cases


def main():
    FROZEN.mkdir(parents=True, exist_ok=True)
    cases = generate()
    files = {"protocol.json": PROTOCOL, "cases.json": cases}
    for name, data in files.items():
        (FROZEN / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    digest = {name: hashlib.sha256((FROZEN / name).read_bytes()).hexdigest() for name in files}
    for name in ("history.py", "combine.py"):
        p = HERE.parent.parent / "forecast_fuji" / name if name == "history.py" else HERE / name
        digest[str(p.relative_to(HERE.parent.parent))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (FROZEN / "FREEZE.json").write_text(json.dumps(digest, indent=1, sort_keys=True) + "\n")
    by = {}
    for c in cases:
        by[c["cohort"]] = by.get(c["cohort"], 0) + 1
    print(json.dumps({"cases": len(cases), "by_cohort": by, "freeze": digest}, indent=1))


if __name__ == "__main__":
    main()

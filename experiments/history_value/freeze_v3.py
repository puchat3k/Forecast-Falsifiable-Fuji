"""v3 FREEZE (committed before any v3 scoring): WHEN does the history signal help? A pre-registered dose-response.

    python3 -m experiments.history_value.freeze_v3   # writes experiments/history_value/frozen_v3/*

Same generator, reader (stability guard ON), combine rule and scoring as v1/v2; fresh seed 20261124.
What varies on purpose: how wrong the unassisted forecaster's base rate is (prior error 0, 0.10, 0.20, 0.30 below a
true 0.70), each in its own stable cohort, plus one drifting cohort with prior error 0.20.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import freeze as v1
from forecast_fuji.history import RULES

HERE = Path(__file__).parent
FROZEN = HERE / "frozen_v3"
SEED = 20261124
_quiet = {"late": {"approved": 0.05, "not_approved": 0.05}, "never": {"approved": 0.0, "not_approved": 0.0}}
COHORTS = {
    "prior_err_0.00": {"approver_role": "deal_desk", "horizon_days": 14, "mean_gap_days": 4, "base": [["2026-01-01", 0.70]], "analyst_prior": 0.70, **_quiet},
    "prior_err_0.10": {"approver_role": "procurement", "horizon_days": 14, "mean_gap_days": 4, "base": [["2026-01-01", 0.70]], "analyst_prior": 0.60, **_quiet},
    "prior_err_0.20": {"approver_role": "cfo", "horizon_days": 14, "mean_gap_days": 4, "base": [["2026-01-01", 0.70]], "analyst_prior": 0.50, **_quiet},
    "prior_err_0.30": {"approver_role": "credit_committee", "horizon_days": 14, "mean_gap_days": 4, "base": [["2026-01-01", 0.70]], "analyst_prior": 0.40, **_quiet},
    "drift_prior_err_0.20": {"approver_role": "legal", "horizon_days": 14, "mean_gap_days": 4, "base": [["2026-01-01", 0.70], ["2026-10-01", 0.35]], "analyst_prior": 0.50, **_quiet},
}
PROTOCOL = {**v1.PROTOCOL, "schema": "fuji.history-value.protocol.v3", "status": "FROZEN before v3 scoring", "seed": SEED,
    "cohorts": COHORTS, "reader_guards": ["stability"], "stability_rule": RULES["stability"],
    "hypotheses": {
        "H1": "Dose-response: adjusted - unassisted Brier is HELPS for prior error 0.20 and 0.30, and does not HURT at 0.00.",
        "H2": "Analyst-visible regime: among cases where the adjusted forecast ran, those with visible gap "
              "|r - m| >= 0.10 (Fuji rate vs the analyst's own mean forecast on the same visible records) are HELPS; "
              "those with gap < 0.10 do not HURT.",
    },
    "analysis": "analyze_v3.py (frozen): bootstrap 4000, seed 7, 95% interval; HELPS if entirely < 0, HURTS if entirely > 0",
    "decision_rule": ["EXPOSE in a shadow pilot (evidence only; shown only when the stability guard passes and the visible "
                      "gap >= 0.10) if H2's gap>=0.10 regime HELPS AND no H1 level or H2 slice HURTS AND the fallback is "
                      "unchanged on every withheld case. Otherwise DO NOT EXPOSE.",
                      "Synthetic results never count as evidence of customer-case improvement."]}


def main():
    import sys
    global FROZEN
    seed, protocol = SEED, PROTOCOL
    if "--replicate" in sys.argv:  # exact v3 design on a fresh seed; same hypotheses, analysis and decision rule
        seed = 20261125
        FROZEN = HERE / "frozen_v3r"
        protocol = {**PROTOCOL, "seed": seed, "status": "FROZEN before v3-replication scoring",
                    "replication_of": "v3 (seed 20261124, freeze 7c2deaf); pre-registered: H2 must again be HELPS "
                                      "for the replication to count as replicated"}
    FROZEN.mkdir(parents=True, exist_ok=True)
    cases = v1.generate(seed, COHORTS)
    for name, data in {"protocol.json": protocol, "cases.json": cases}.items():
        (FROZEN / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    root = HERE.parent.parent
    digest = {n: hashlib.sha256((FROZEN / n).read_bytes()).hexdigest() for n in ("protocol.json", "cases.json")}
    for rel in ("forecast_fuji/history.py", "experiments/history_value/combine.py", "experiments/history_value/analyze_v3.py"):
        digest[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    (FROZEN / "FREEZE.json").write_text(json.dumps(digest, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "freeze": digest}, indent=1))


if __name__ == "__main__":
    main()

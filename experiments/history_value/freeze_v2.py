"""v2 FREEZE (committed before any v2 scoring): a fresh seed, the same generator, two pre-registered arms.

    python3 -m experiments.history_value.freeze_v2      # writes experiments/history_value/frozen_v2/*

Arm A: the v1 reader (no guard): a replication of v1 on new data.
Arm B: the same reader with the opt-in stability guard (forecast_fuji.history RULES["stability"]), which withholds
       a pooled rate when the most recent 15 resolved records differ from the older ones (gap >= 0.20 and |z| >= 2).
       The guard uses only records visible at the cutoff, so an analyst could see it; it does not use synthetic truth.
The guard was designed after seeing v1 (seed 20261122). v2 tests it on seed 20261123, which nobody has scored.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import freeze as v1
from forecast_fuji.history import RULES

HERE = Path(__file__).parent
FROZEN = HERE / "frozen_v2"
SEED = 20261123

PROTOCOL = {**v1.PROTOCOL,
    "schema": "fuji.history-value.protocol.v2",
    "status": "FROZEN before v2 scoring",
    "seed": SEED,
    "arms": {"A_no_guard": "reference_rate(guards=[])", "B_stability_guard": "reference_rate(guards=['stability'])",
             "stability_rule": RULES["stability"]},
    "regime_hypothesis": "The adjusted forecast improves on the unassisted forecast in the regime where Fuji returns "
                         "AVAILABLE with the stability guard on (enough resolved history, not censored, recent records "
                         "consistent with older ones). Every input to this regime is visible to an analyst at the cutoff.",
    "decision_rule": [
        "Arm B HELPS in its regime if the 95% interval of mean (adjusted - unassisted) over its paired cases is "
        "entirely below 0; HURTS if entirely above 0; otherwise inconclusive. The same verdicts are reported per "
        "cohort/period (drift split at 2026-10-01).",
        "Recommend exposing the signal to analysts in a shadow pilot (evidence only, with the stability guard on) if "
        "Arm B HELPS overall AND no cohort/period HURTS AND every withheld case (including WITHHELD_UNSTABLE) "
        "falls back unchanged. Otherwise do not recommend it.",
        "Arm A is reported for comparison and replication; it does not decide the recommendation.",
        "Synthetic results never count as evidence of customer-case improvement.",
    ],
}


def main():
    FROZEN.mkdir(parents=True, exist_ok=True)
    cases = v1.generate(SEED)
    for name, data in {"protocol.json": PROTOCOL, "cases.json": cases}.items():
        (FROZEN / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    root = HERE.parent.parent
    digest = {n: hashlib.sha256((FROZEN / n).read_bytes()).hexdigest() for n in ("protocol.json", "cases.json")}
    for rel in ("forecast_fuji/history.py", "experiments/history_value/combine.py"):
        digest[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    (FROZEN / "FREEZE.json").write_text(json.dumps(digest, indent=1, sort_keys=True) + "\n")
    by = {}
    for c in cases:
        by[c["cohort"]] = by.get(c["cohort"], 0) + 1
    print(json.dumps({"cases": len(cases), "by_cohort": by, "freeze": digest}, indent=1))


if __name__ == "__main__":
    main()

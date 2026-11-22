"""v3 pre-registered analysis (frozen with frozen_v3/ before scoring). Reads results_v3/per_case.csv.

    python3 -m experiments.history_value.analyze_v3    # writes results_v3/ANALYSIS.md and analysis.json
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .run import bootstrap, verdict

HERE = Path(__file__).parent
RESULTS = HERE / "results_v3"
GAP = 0.10  # pre-registered threshold on the visible gap |Fuji rate - analyst's own mean on the same records|


def stats(rows):
    d = [float(r["brier_adjusted"]) - float(r["brier_unassisted"]) for r in rows]
    if not d:
        return {"cases": 0, "mean": None, "ci95": None, "verdict": "no cases", "worse": 0}
    ci = bootstrap(d)
    return {"cases": len(d), "mean": round(sum(d) / len(d), 4), "ci95": ci, "verdict": verdict(ci), "worse": sum(x > 0 for x in d)}


def main():
    rows = list(csv.DictReader((RESULTS / "per_case.csv").open()))
    applied = [r for r in rows if r["applied"] == "True"]
    for r in applied:
        m = re.search(r"r=([\d.]+), m=([\d.]+)", r["why"])
        r["gap"] = abs(float(m.group(1)) - float(m.group(2)))
    out = {
        "H1_dose_response_by_prior_error": {c: stats([r for r in applied if r["cohort"] == c])
                                            for c in sorted({r["cohort"] for r in rows})},
        "H2_visible_gap_regime": {f"gap >= {GAP}": stats([r for r in applied if r["gap"] >= GAP]),
                                  f"gap < {GAP}": stats([r for r in applied if r["gap"] < GAP])},
        "coverage": {"all": len(rows), "adjusted_ran": len(applied),
                     "gap_regime_ran": sum(1 for r in applied if r["gap"] >= GAP)},
        "withheld": {}, "fallback_unchanged": all(r["adjusted"] == r["unassisted"] for r in rows if r["applied"] != "True"),
    }
    for r in rows:
        if r["applied"] != "True":
            out["withheld"][r["status"]] = out["withheld"].get(r["status"], 0) + 1
    g = out["H2_visible_gap_regime"]
    h1 = out["H1_dose_response_by_prior_error"]
    hurts = [k for k, v in {**h1, **g}.items() if v["verdict"] == "HURTS"]
    out["decision"] = ("EXPOSE in shadow pilot, shown only when the guard passes and the visible gap >= 0.10"
                       if g[f"gap >= {GAP}"]["verdict"] == "HELPS" and not hurts and out["fallback_unchanged"]
                       else "DO NOT EXPOSE") + (f" (HURTS in: {', '.join(hurts)})" if hurts else "")
    (RESULTS / "analysis.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    f = lambda s: "–" if s["mean"] is None else f"{s['mean']:+.4f} [{s['ci95'][0]:+.4f}, {s['ci95'][1]:+.4f}] {s['verdict']} (n={s['cases']}, worse {s['worse']})"
    L = ["# v3 pre-registered analysis (synthetic; SHADOW, forecast-only)", "",
         "## H1: dose-response (adjusted − unassisted Brier, by the unassisted forecaster's prior error)", ""]
    L += [f"- {k}: {f(v)}" for k, v in h1.items()]
    L += ["", f"## H2: analyst-visible regime (gap = |Fuji rate − analyst's own mean on the same records|, threshold {GAP})", ""]
    L += [f"- {k}: {f(v)}" for k, v in g.items()]
    L += ["", f"Coverage: adjusted ran on {out['coverage']['adjusted_ran']}/{out['coverage']['all']}; regime (gap ≥ {GAP}) on "
          f"{out['coverage']['gap_regime_ran']}/{out['coverage']['all']}. Withheld: {out['withheld']}. Fallback unchanged: {out['fallback_unchanged']}.",
          "", f"**Pre-registered decision: {out['decision']}**"]
    (RESULTS / "ANALYSIS.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

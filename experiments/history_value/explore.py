"""EXPLORATORY (post hoc; not pre-registered; does not change the frozen verdict).

Asks WHEN the adjusted forecast helps, using only the already-scored per-case results:
  1. Is Fuji's rate current?  |r - true base| <= 0.10 ("current") vs > 0.10 ("stale"); synthetic truth only,
     used to explain the mechanism, not something an analyst could see.
  2. How large is the shift the rule asks for?  |r - m| (rate vs the analyst's own mean on the same records).
  3. How much history?  n resolved records.

    python3 -m experiments.history_value.explore   # writes results/EXPLORATORY.md
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .run import bootstrap, verdict

RESULTS = Path(__file__).parent / "results"


def main():
    rows = [r for r in csv.DictReader((RESULTS / "per_case.csv").open()) if r["applied"] == "True"]
    for r in rows:
        m = re.search(r"r=([\d.]+), m=([\d.]+)", r["why"])
        r["r"], r["m"] = float(m.group(1)), float(m.group(2))
        r["d"] = float(r["brier_adjusted"]) - float(r["brier_unassisted"])
        r["staleness"] = abs(r["r"] - float(r["true_base"]))
        r["shift"] = abs(r["r"] - r["m"])
        r["n"] = int(r["n_resolved"])

    def line(label, sub):
        if not sub:
            return f"| {label} | 0 | – | – | – |"
        ds = [x["d"] for x in sub]
        ci = bootstrap(ds)
        worse = sum(1 for x in ds if x > 0)
        return f"| {label} | {len(sub)} | {sum(ds) / len(ds):+.4f} | [{ci[0]:+.4f}, {ci[1]:+.4f}] {verdict(ci)} | {worse} |"

    head = ["| Slice | Cases | Adjusted − unassisted (mean Brier) | 95% CI | History worse |", "|---|---|---|---|---|"]
    L = ["# EXPLORATORY: when does the adjusted forecast help?", "",
         "> Post hoc slices of the frozen run (`per_case.csv`). Not pre-registered, so these slices suggest where to "
         "look next; they do not change the frozen verdict. Synthetic data only.", "",
         "## 1. Is Fuji's rate current? (|rate − true base|; synthetic truth)", "", *head,
         line("current (≤ 0.10)", [x for x in rows if x["staleness"] <= 0.10]),
         line("stale (> 0.10)", [x for x in rows if x["staleness"] > 0.10]), "",
         "## 2. How big a shift does the rule ask for? (|rate − analyst's own mean on the same records|)", "", *head,
         line("small (< 0.05)", [x for x in rows if x["shift"] < 0.05]),
         line("medium (0.05–0.15)", [x for x in rows if 0.05 <= x["shift"] < 0.15]),
         line("large (≥ 0.15)", [x for x in rows if x["shift"] >= 0.15]),
         line("large AND current", [x for x in rows if x["shift"] >= 0.15 and x["staleness"] <= 0.10]),
         line("large AND stale", [x for x in rows if x["shift"] >= 0.15 and x["staleness"] > 0.10]), "",
         "## 3. How much history? (n resolved)", "", *head,
         line("10–19", [x for x in rows if x["n"] < 20]),
         line("20–49", [x for x in rows if 20 <= x["n"] < 50]),
         line("50+", [x for x in rows if x["n"] >= 50]), ""]
    (RESULTS / "EXPLORATORY.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

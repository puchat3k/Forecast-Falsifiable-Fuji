"""Step 2: time-ordered replay and scoring, against the frozen inputs (refuses to run if they changed).

    python3 -m experiments.history_value.run     # writes experiments/history_value/results/*

For every frozen case, in time order, at its own decision cutoff:
  history  = forecast_fuji.history.reference_rate(cutoff = anchor_at), own case excluded
  variants = unassisted (frozen), rate_alone (only when AVAILABLE), adjusted (frozen rule; fallback when withheld)
Scored with Fuji core resolve() (Brier); SHADOW, forecast-only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from examples.history_replay import ReplayClock
from forecast_fuji import core, workflow
from forecast_fuji.core import Fuji
from forecast_fuji.history import reference_rate, render
from forecast_fuji.workflow import WorkflowFuji, _hash

from . import combine

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
FROZEN, RESULTS = HERE / "frozen", HERE / "results"
FIXTURE = ROOT / "tests" / "fixtures" / "next_move_round2_fuji.sqlite"
WF, PRINCIPAL, PURPOSE = "history-value-replay", "replay", "history_value"
DRIFT_AT = "2026-10-01T00:00:00Z"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_freeze():
    want = json.loads((FROZEN / "FREEZE.json").read_text())
    for name, digest in want.items():
        path = FROZEN / name if (FROZEN / name).exists() else ROOT / name
        if sha(path) != digest:
            raise SystemExit(f"FROZEN INPUT CHANGED: {name}")
    return want


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def pid(case_key):
    return _hash(["proposition", _hash([WF, PRINCIPAL, case_key]), "approval"])


def build_ledger(path, cases):
    engine = WorkflowFuji(path, authorize=lambda *a: True)
    events = []
    for c in cases:
        a = ts(c["anchor_at"])
        events.append((a + timedelta(hours=1), 0, "lock", c))
        if c["recorded_at"]:
            events.append((ts(c["recorded_at"]), 1, "resolve", c))
    with patch.object(workflow, "datetime", ReplayClock), patch.object(core, "datetime", ReplayClock):
        for when, _, kind, c in sorted(events, key=lambda e: (e[0], e[1], e[3]["case_key"])):
            ReplayClock.current = when
            a = ts(c["anchor_at"])
            if kind == "lock":
                engine.lock({
                    "workflow": WF, "principal_id": PRINCIPAL, "purpose": PURPOSE, "case_key": c["case_key"],
                    "mode": "SHADOW",
                    "evidence": {"classification": "synthetic", "source_refs": [f"synthetic:{c['case_key']}"],
                                 "snapshot_sha256": "0" * 64, "cutoff_at": c["anchor_at"]},
                    "proposition": {"key": "approval", "statement": f"{c['approver_role']} approves within {c['horizon_days']} days",
                                    "horizon": iso(a + timedelta(days=c["horizon_days"])),
                                    "resolution_rule": "TRUE iff approval observed by the window end",
                                    "resolution_source": "synthetic-crm:",
                                    "earliest_observable_at": iso(a + timedelta(hours=2)),
                                    "event": {"family": "offer_approval", "version": 1, "approver_role": c["approver_role"],
                                              "offer_side": c["offer_side"], "horizon_days": c["horizon_days"],
                                              "anchor_at": c["anchor_at"]}},
                    "forecasts": [{"member": "unassisted", "probability": c["p_unassisted"], "generated_at": iso(when)}],
                    "baseline": {"name": "declared", "probability": 0.5, "derivation": "synthetic replay"}})
            else:
                engine.resolve({"workflow": WF, "principal_id": PRINCIPAL, "purpose": PURPOSE, "case_key": c["case_key"],
                                "outcome": c["approved"], "source_ref": f"synthetic-crm:{c['case_key']}",
                                "source_sha256": "1" * 64, "observed_at": c["observed_at"], "verified_by": "replay"})


def query(c):
    return {"event": {"family": "offer_approval", "version": 1, "approver_role": c["approver_role"],
                      "offer_side": c["offer_side"], "horizon_days": c["horizon_days"]},
            "cutoff_at": c["anchor_at"], "classification": "synthetic", "exclude_case_keys": [c["case_key"]]}


def fuji_brier(rows, members):
    """Score with Fuji core (resolve -> scores table); return mean Brier per member over rows."""
    f = Fuji(":memory:")
    exp = f.create_experiment("history-value scoring", mode="SHADOW")
    for r in rows:
        case = f.create_case(exp, r["case_key"], r["anchor_at"])
        p = f.add_proposition(case, "approval", "approval", r["anchor_at"], "frozen outcome")
        for m in members:
            f.add_forecast(p, m, r[m])
        f.lock_case(case, min_members=1)
        f.resolve(p, r["approved"])
    out = {}
    for m in members:
        v = f.conn.execute("SELECT AVG(brier), COUNT(*) FROM scores WHERE method_type='FORECAST' AND method_name=?", (m,)).fetchone()
        out[m] = (v[0], v[1])
    f.close()
    return out


def bootstrap(diffs, draws=4000, seed=7):
    if not diffs:
        return None
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return [round(means[int(0.025 * draws)], 4), round(means[int(0.975 * draws) - 1], 4)]


def verdict(ci):
    if ci is None:
        return "no paired cases"
    return "HELPS" if ci[1] < 0 else "HURTS" if ci[0] > 0 else "inconclusive"


def brier(p, y):
    return (p - (1.0 if y else 0.0)) ** 2


def existing_slice():
    """Reuse the frozen #310 round-2 forecasts that concern approval; same reader + combine rule."""
    conn = sqlite3.connect(f"file:{FIXTURE}?mode=ro", uri=True)
    rows = conn.execute(
        """SELECT c.case_key, c.evidence_cutoff_at, p.statement, p.target_horizon, f.member, f.probability, r.outcome
           FROM propositions p JOIN cases c USING(case_id) JOIN forecasts f USING(proposition_id)
           LEFT JOIN resolutions r USING(proposition_id) WHERE lower(p.statement) LIKE '%approv%'""").fetchall()
    conn.close()
    out = []
    for case_key, cutoff, statement, horizon, member, p, outcome in rows:
        role = "credit_committee" if "credit committee" in statement.lower() else "deal_desk"
        days = (ts(horizon) - ts(cutoff)).days
        q = {"event": {"family": "offer_approval", "version": 1, "approver_role": role, "offer_side": "vendor",
                       "horizon_days": days}, "cutoff_at": cutoff, "classification": "synthetic"}
        h = reference_rate(FIXTURE, q, principal_id=PRINCIPAL, purpose=PURPOSE, authorize=lambda *a: True)
        p_adj, applied, why = combine.adjust(p, h, [])
        out.append({"case_key": case_key, "member": member, "statement": statement[:90], "horizon_days": days,
                    "p_unassisted": p, "status": h["status"], "reasons": h["reasons"], "p_adjusted": p_adj,
                    "applied": applied, "fallback": why,
                    "brier_unassisted": None if outcome is None else round(brier(p, outcome), 4)})
    return out


def main():
    freeze = verify_freeze()
    protocol = json.loads((FROZEN / "protocol.json").read_text())
    cases = json.loads((FROZEN / "cases.json").read_text())
    p_by_pid = {pid(c["case_key"]): c["p_unassisted"] for c in cases}
    RESULTS.mkdir(exist_ok=True)
    tmp = tempfile.TemporaryDirectory()
    db = Path(tmp.name) / "ledger.sqlite"
    build_ledger(db, cases)

    rows, fallback_example = [], {}
    for c in cases:  # time order is the frozen order
        h = reference_rate(db, query(c), principal_id=PRINCIPAL, purpose=PURPOSE, authorize=lambda *a: True)
        contrib = [p_by_pid[x["proposition_id"]] for x in h["cohort"]]
        p_adj, applied, why = combine.adjust(c["p_unassisted"], h, contrib)
        row = {"case_key": c["case_key"], "cohort": c["cohort"], "anchor_at": c["anchor_at"], "approved": c["approved"],
               "true_base": c["true_base"], "status": h["status"], "reasons": "; ".join(h["reasons"]),
               "n_resolved": (h["counts"] or {}).get("resolved"), "n_unresolved": (h["counts"] or {}).get("unresolved"),
               "unassisted": c["p_unassisted"], "rate_alone": h["rate"]["observed"] if h["rate"] else None,
               "adjusted": round(p_adj, 4), "applied": applied, "why": why}
        for v in ("unassisted", "rate_alone", "adjusted"):
            row[f"brier_{v}"] = None if row[v] is None else round(brier(row[v], c["approved"]), 4)
        if c["cohort"] == "drift":
            row["cohort_period"] = "drift:before" if c["anchor_at"] < DRIFT_AT else "drift:after"
        else:
            row["cohort_period"] = c["cohort"]
        rows.append(row)
        if not applied and h["status"] not in fallback_example:
            fallback_example[h["status"]] = {"case": c["case_key"], "text": render(h), "unassisted": c["p_unassisted"],
                                             "adjusted": p_adj, "note": why}

    paired = [r for r in rows if r["rate_alone"] is not None]
    fuji = fuji_brier(paired, ["unassisted", "rate_alone", "adjusted"])
    for m in ("unassisted", "rate_alone", "adjusted"):  # cross-check own arithmetic against Fuji's scores
        own = sum(r[f"brier_{m}"] for r in paired) / len(paired)
        assert abs(own - fuji[m][0]) < 1e-3, (m, own, fuji[m])

    def summarize(sub):
        p = [r for r in sub if r["rate_alone"] is not None]
        d_adj = [r["brier_adjusted"] - r["brier_unassisted"] for r in p]
        d_rate = [r["brier_rate_alone"] - r["brier_unassisted"] for r in p]
        mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
        ci_adj, ci_rate = bootstrap(d_adj), bootstrap(d_rate)
        return {"cases": len(sub), "paired": len(p), "coverage": round(len(p) / len(sub), 3) if sub else None,
                "withheld": dict(Counter(r["status"] for r in sub if r["rate_alone"] is None)),
                "brier_paired": {"unassisted": mean([r["brier_unassisted"] for r in p]),
                                 "rate_alone": mean([r["brier_rate_alone"] for r in p]),
                                 "adjusted": mean([r["brier_adjusted"] for r in p])},
                "adjusted_minus_unassisted": {"mean": mean(d_adj), "ci95": ci_adj, "verdict": verdict(ci_adj)},
                "rate_minus_unassisted": {"mean": mean(d_rate), "ci95": ci_rate, "verdict": verdict(ci_rate)},
                "full_set_adjusted_with_fallback_minus_unassisted": mean([r["brier_adjusted"] - r["brier_unassisted"] for r in sub]),
                "history_worse_cases": sum(1 for x in d_adj if x > 0)}

    groups = defaultdict(list)
    for r in rows:
        groups[r["cohort_period"]].append(r)
    summary = {"ALL": summarize(rows), **{k: summarize(v) for k, v in sorted(groups.items())}}
    fallback_ok = all(r["adjusted"] == r["unassisted"] for r in rows if not r["applied"])
    harm = sorted((r for r in rows if r["applied"] and r["brier_adjusted"] > r["brier_unassisted"]),
                  key=lambda r: r["brier_unassisted"] - r["brier_adjusted"])
    existing = existing_slice()
    out = {"protocol_status": protocol["status"], "freeze": freeze, "data": protocol["data"], "summary": summary,
           "fuji_scores_paired": {k: {"mean_brier": round(v[0], 4), "n": v[1]} for k, v in fuji.items()},
           "fallback_unchanged_when_withheld": fallback_ok, "fallback_examples": fallback_example,
           "harm_top10": harm[:10], "harm_by_group": dict(Counter(r["cohort_period"] for r in harm)),
           "existing_310_slice": existing, "shadow": {"mode": "SHADOW", "forecast_only": True, "actions_enabled": False}}
    (RESULTS / "results.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    with (RESULTS / "per_case.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) + ["cohort_period"] if "cohort_period" not in rows[0] else list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (RESULTS / "RESULTS.md").write_text(report(out))
    tmp.cleanup()
    print((RESULTS / "RESULTS.md").read_text())


def report(o):
    s = o["summary"]
    f = lambda x: "–" if x is None else f"{x:.4f}" if isinstance(x, float) else str(x)
    ci = lambda d: f"{f(d['mean'])} [{f(d['ci95'][0])}, {f(d['ci95'][1])}] {d['verdict']}" if d["ci95"] else "–"
    L = ["# History-value replay: do Fuji's historical reference rates improve offer-approval forecasts?", "",
         "> **SYNTHETIC method validation.** The seeded generator, the unassisted forecasts, the cutoff rule, the combine "
         "rule and this scoring plan were frozen in `frozen/` (commit before scoring; hashes re-verified at run time). "
         "These numbers say whether the method behaves as intended. **They are not evidence that customer cases improve.** "
         "SHADOW, forecast-only: nothing here changes an approval status or chooses a move.", "",
         "## Paired Brier (cases where all three variants exist) and coverage (all cases)", "",
         "| Group | Cases | Paired | Coverage | Unassisted | Rate alone | Adjusted | Adjusted − unassisted [95% CI] | Rate alone − unassisted [95% CI] | History made it worse | Full set (with fallback) Δ | Withheld (Fuji reasons) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g, x in s.items():
        b = x["brier_paired"]
        L.append(f"| {g} | {x['cases']} | {x['paired']} | {f(x['coverage'])} | {f(b['unassisted'])} | {f(b['rate_alone'])} | {f(b['adjusted'])} | "
                 f"{ci(x['adjusted_minus_unassisted'])} | {ci(x['rate_minus_unassisted'])} | {x['history_worse_cases']} of {x['paired']} | "
                 f"{f(x['full_set_adjusted_with_fallback_minus_unassisted'])} | {', '.join(f'{k} {v}' for k, v in x['withheld'].items()) or '–'} |")
    fs = o["fuji_scores_paired"]
    L += ["", f"Fuji core scoring cross-check (paired set): " + ", ".join(f"{k} {v['mean_brier']} (n={v['n']})" for k, v in fs.items()) + ".",
          f"Fallback leaves the unassisted forecast unchanged whenever Fuji withholds: **{o['fallback_unchanged_when_withheld']}**.", "",
          "## Fallback when Fuji withholds (exact analyst-facing text)", ""]
    for status, ex in o["fallback_examples"].items():
        L += [f"**{status}** — case `{ex['case']}`: adjusted forecast = unassisted {ex['unassisted']:.4f} (unchanged). Reason: {ex['note']}", "",
              "```text", ex["text"], "```", ""]
    L += ["## Where history made the forecast worse", "",
          "By group: " + ", ".join(f"{k} {v}" for k, v in sorted(o["harm_by_group"].items())) + ".", "",
          "| Case | Anchor | Approved | True base | Unassisted | Fuji rate (n) | Adjusted | Brier unassisted → adjusted |", "|---|---|---|---|---|---|---|---|"]
    for r in o["harm_top10"]:
        L.append(f"| {r['case_key']} | {r['anchor_at'][:10]} | {r['approved']} | {r['true_base']} | {r['unassisted']} | {r['rate_alone']} ({r['n_resolved']}) | {r['adjusted']} | {r['brier_unassisted']} → {r['brier_adjusted']} |")
    L += ["", "## Existing #310 frozen forecasts (reused; not pooled with synthetic cases)", "",
          "| Case | Member | Horizon days | Unassisted p | Fuji status (reasons) | Adjusted | Brier unassisted |", "|---|---|---|---|---|---|---|"]
    for e in o["existing_310_slice"]:
        L.append(f"| {e['case_key']} | {e['member']} | {e['horizon_days']} | {e['p_unassisted']} | {e['status']} ({'; '.join(e['reasons'])}) | {e['p_adjusted']} (fallback) | {e['brier_unassisted']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

"""Synthetic replay for the read-only forecast-history reader (offer_approval family).

Builds a SYNTHETIC ledger through the real WorkflowFuji lock/resolve path under a replay clock, then asks the
reader for reference rates at two decision cutoffs. No network, no model calls, no production data.

    python3 -m examples.history_replay [--out <dir>] [--legacy-db <existing Fuji sqlite>]

Scenarios:
  A  usable cohort        deal_desk / vendor / 14 days, cutoff 2027-03-15  -> AVAILABLE
  B  same query, later    cutoff 2027-04-01: the late resolution and the open window now count
  C  sparse cohort        cfo / vendor / 14 days                            -> WITHHELD_SPARSE
  D  incompatible query   approver_role=board (not in the family's rules)   -> WITHHELD_INCOMPATIBLE
  E  existing records     an existing Fuji ledger without event labels      -> nothing matches (optional)
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime as NativeDatetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from forecast_fuji import core, workflow
from forecast_fuji.history import reference_rate, render
from forecast_fuji.workflow import WorkflowFuji

UTC = timezone.utc
Q1 = "2027-03-15T00:00:00Z"
Q2 = "2027-04-01T00:00:00Z"


class ReplayClock(NativeDatetime):
    current = NativeDatetime(2027, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.current if tz is not None else cls.current.replace(tzinfo=None)


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _allow(principal, purpose, refs):
    return principal == "replay-analyst" and purpose == "history_replay"


# (case, approver_role, horizon_days, anchor, observed_at, recorded_at, approved, classification)
def records():
    d = lambda s: NativeDatetime.fromisoformat(s).replace(tzinfo=UTC)
    out = []
    pattern = [True, True, False, True, True, True, False, True, True, False, True, True]  # 9 of 12 approved
    for i, ok in enumerate(pattern):
        a = d("2027-01-04T09:00:00") + timedelta(days=3 * i)
        out.append((f"dd14-{i:02d}", "deal_desk", 14, a, a + timedelta(days=6), a + timedelta(days=6, hours=2), ok, "synthetic"))
    # The late resolution: window closes 2027-03-06, approval observed 2027-03-05, but entered only on 2027-03-20.
    a = d("2027-02-20T09:00:00")
    out.append(("dd14-late", "deal_desk", 14, a, d("2027-03-05T15:00:00"), d("2027-03-20T10:00:00"), True, "synthetic"))
    # Window still open at Q1 (closes 2027-03-24); resolved before Q2.
    a = d("2027-03-10T09:00:00")
    out.append(("dd14-open", "deal_desk", 14, a, d("2027-03-18T12:00:00"), d("2027-03-18T13:00:00"), False, "synthetic"))
    # Locked only after Q1 (anchor 2027-03-20): invisible at Q1, window still open at Q2.
    a = d("2027-03-20T09:00:00")
    out.append(("dd14-after", "deal_desk", 14, a, None, None, None, "synthetic"))
    # Other horizon (30 days): never pooled with 14 days.
    for i, ok in enumerate([True, True, False, True, True]):
        a = d("2027-01-05T09:00:00") + timedelta(days=5 * i)
        out.append((f"dd30-{i}", "deal_desk", 30, a, a + timedelta(days=20), a + timedelta(days=20, hours=1), ok, "synthetic"))
    # Sparse cohort: CFO approvals.
    for i, ok in enumerate([True, False, True, True]):
        a = d("2027-01-11T09:00:00") + timedelta(days=7 * i)
        out.append((f"cfo14-{i}", "cfo", 14, a, a + timedelta(days=9), a + timedelta(days=9, hours=1), ok, "synthetic"))
    # A private-classified record with the same definition: never mixed into a synthetic cohort.
    a = d("2027-01-20T09:00:00")
    out.append(("dd14-private", "deal_desk", 14, a, a + timedelta(days=4), a + timedelta(days=4, hours=1), False, "private"))
    return out


def build_ledger(path):
    engine = WorkflowFuji(path, authorize=lambda p, u, r: True)
    with patch.object(workflow, "datetime", ReplayClock), patch.object(core, "datetime", ReplayClock):
        events = []
        for case, role, h, anchor, observed, recorded, ok, cls in records():
            events.append((anchor + timedelta(hours=1), "lock", (case, role, h, anchor, cls)))
            if observed is not None:
                events.append((recorded, "resolve", (case, observed, ok)))
        for when, kind, args in sorted(events, key=lambda e: e[0]):
            ReplayClock.current = when
            if kind == "lock":
                case, role, h, anchor, cls = args
                engine.lock({
                    "workflow": "negotiation-replay", "principal_id": "replay", "purpose": "history_replay",
                    "case_key": case, "mode": "SHADOW",
                    "evidence": {"classification": cls, "source_refs": [f"synthetic:{case}"],
                                 "snapshot_sha256": "0" * 64, "cutoff_at": _iso(anchor)},
                    "proposition": {"key": "approval", "statement": f"The {role} approves the offer within {h} days",
                                    "horizon": _iso(anchor + timedelta(days=h)),
                                    "resolution_rule": "TRUE iff the approval is recorded by the window end",
                                    "resolution_source": "synthetic-crm:",
                                    "earliest_observable_at": _iso(anchor + timedelta(hours=2)),
                                    "event": {"family": "offer_approval", "version": 1, "approver_role": role,
                                              "offer_side": "vendor", "horizon_days": h, "anchor_at": _iso(anchor)}},
                    "forecasts": [{"member": "analyst", "probability": 0.6, "generated_at": _iso(when)}],
                    "baseline": {"name": "declared", "probability": 0.5, "derivation": "synthetic replay"},
                })
            else:
                case, observed, ok = args
                engine.resolve({"workflow": "negotiation-replay", "principal_id": "replay", "purpose": "history_replay",
                                "case_key": case, "outcome": ok, "source_ref": f"synthetic-crm:{case}",
                                "source_sha256": "1" * 64, "observed_at": _iso(observed), "verified_by": "replay"})


def query(role, cutoff, *, cls="synthetic"):
    return {"event": {"family": "offer_approval", "version": 1, "approver_role": role, "offer_side": "vendor",
                      "horizon_days": 14},
            "cutoff_at": cutoff, "classification": cls, "exclude_case_keys": ["new-offer-under-review"]}


def run(out_dir=None, legacy_db=None):
    tmp = tempfile.TemporaryDirectory()
    db = Path(tmp.name) / "replay.sqlite"
    build_ledger(db)
    ask = lambda q, path=db: reference_rate(path, q, principal_id="replay-analyst", purpose="history_replay", authorize=_allow)
    scenarios = {
        "A_usable_cohort_at_2027-03-15": ask(query("deal_desk", Q1)),
        "B_same_query_at_2027-04-01": ask(query("deal_desk", Q2)),
        "C_sparse_cohort_cfo": ask(query("cfo", Q2)),
        "D_incompatible_query_board": ask(query("board", Q2)),
    }
    if legacy_db:
        scenarios["E_existing_unlabelled_records"] = ask(query("credit_committee", "2027-12-31T00:00:00Z"), Path(legacy_db))
    texts = {k: render(v) for k, v in scenarios.items()}
    # Shadow / evidence-only guarantees, shown alongside the analyst text.
    flags = {k: {f: v[f] for f in ("use", "mode", "actions_enabled", "may_change_approval_status", "may_select_move")}
             for k, v in scenarios.items()}
    texts["F_evidence_only_flags"] = "\n".join(f"{k}: {json.dumps(f, sort_keys=True)}" for k, f in flags.items())
    try:  # an unauthorized principal must not read history at all
        reference_rate(db, query("deal_desk", Q1), principal_id="other-analyst", purpose="history_replay",
                       authorize=_allow)
        texts["G_unauthorized_read"] = "UNEXPECTED: read allowed"
    except PermissionError as e:
        texts["G_unauthorized_read"] = f"other-analyst -> PermissionError: {e} (no counts, no rate returned)"
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "replay.json").write_text(json.dumps(scenarios, indent=1, sort_keys=True) + "\n")
        (out / "ANALYST-OUTPUT.txt").write_text("\n\n".join(f"### {k}\n{t}" for k, t in texts.items()) + "\n")
    tmp.cleanup()
    return scenarios, texts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--legacy-db")
    a = ap.parse_args()
    _, texts = run(a.out, a.legacy_db)
    for k, t in texts.items():
        print(f"### {k}\n{t}\n")

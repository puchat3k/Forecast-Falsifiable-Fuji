import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples import history_replay as replay
from forecast_fuji import history
from forecast_fuji.core import Fuji
from forecast_fuji.history import reference_rate, render, _open_read_only

FIXTURE = Path(__file__).parent / "fixtures" / "next_move_round2_fuji.sqlite"


def pid(case):
    # WorkflowFuji proposition ids are deterministic hashes of the scope key.
    from forecast_fuji.workflow import _hash
    key = _hash(["negotiation-replay", "replay", case])
    return _hash(["proposition", key, "approval"])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HistoryReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "replay.sqlite"
        replay.build_ledger(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ask(self, q, db=None):
        return reference_rate(db or self.db, q, principal_id="replay-analyst", purpose="history_replay",
                              authorize=replay._allow)

    def test_usable_cohort(self):
        r = self.ask(replay.query("deal_desk", replay.Q1))
        self.assertEqual(r["status"], "AVAILABLE")
        self.assertEqual(r["counts"], {"eligible": 13, "resolved": 12, "unresolved": 1, "approved": 9,
                                       "not_approved": 3, "window_open": 1})
        self.assertEqual(r["rate"]["numerator"], 9)
        self.assertEqual(r["rate"]["denominator"], 12)
        self.assertEqual(r["rate"]["observed"], 0.75)
        self.assertEqual(len(r["cohort"]), 12)
        for x in r["cohort"]:  # provenance per contributing record
            self.assertLessEqual(x["observed_at"], replay.Q1)
            self.assertLessEqual(x["recorded_at"], replay.Q1)
            self.assertEqual(x["resolution_source_sha256"], "1" * 64)

    def test_late_resolution_excluded_early_counted_later(self):
        late = pid("dd14-late")
        early = self.ask(replay.query("deal_desk", replay.Q1))
        self.assertNotIn(late, [x["proposition_id"] for x in early["cohort"]])
        self.assertEqual([(u["proposition_id"], u["why_unresolved"]) for u in early["unresolved_records"]],
                         [(late, "resolution recorded after the cutoff")])
        later = self.ask(replay.query("deal_desk", replay.Q2))
        self.assertIn(late, [x["proposition_id"] for x in later["cohort"]])
        self.assertEqual(later["counts"]["unresolved"], 0)
        self.assertEqual((later["rate"]["numerator"], later["rate"]["denominator"]), (10, 14))

    def test_record_locked_after_cutoff_is_invisible(self):
        r = self.ask(replay.query("deal_desk", replay.Q1))
        self.assertEqual(r["excluded"]["not_locked_by_cutoff"], 1)
        self.assertNotIn(pid("dd14-after"), json.dumps(r))

    def test_sparse_cohort_withheld(self):
        r = self.ask(replay.query("cfo", replay.Q2))
        self.assertEqual(r["status"], "WITHHELD_SPARSE")
        self.assertIsNone(r["rate"])
        self.assertEqual(r["counts"]["resolved"], 4)

    def test_incompatible_query_withheld(self):
        r = self.ask(replay.query("board", replay.Q2))
        self.assertEqual(r["status"], "WITHHELD_INCOMPATIBLE")
        self.assertIsNone(r["rate"])
        q = replay.query("deal_desk", replay.Q2)
        q["event"]["horizon_days"] = 10
        self.assertEqual(self.ask(q)["reasons"], ["horizon_days_not_allowed"])

    def test_horizons_are_never_pooled(self):
        r = self.ask(replay.query("deal_desk", replay.Q2))
        self.assertEqual(r["other_horizons"], {"30": {"eligible": 5, "resolved": 5, "unresolved": 0}})
        q = replay.query("deal_desk", replay.Q2)
        q["event"]["horizon_days"] = 30
        r30 = self.ask(q)
        self.assertEqual(r30["status"], "WITHHELD_SPARSE")
        self.assertEqual(r30["counts"]["resolved"], 5)

    def test_classifications_are_never_mixed(self):
        r = self.ask(replay.query("deal_desk", replay.Q2))
        self.assertEqual(r["excluded"]["other_classification"], 1)
        self.assertEqual(self.ask(replay.query("deal_desk", replay.Q2, cls="private"))["counts"]["resolved"], 1)

    def test_censoring_withholds(self):
        with patch.dict(history.RULES, {"max_unresolved_share": 0.05}):
            r = self.ask(replay.query("deal_desk", replay.Q1))
        self.assertEqual(r["status"], "WITHHELD_CENSORED")
        self.assertIsNone(r["rate"])

    def test_read_only_and_evidence_only(self):
        before = sha(self.db)
        r = self.ask(replay.query("deal_desk", replay.Q1))
        self.assertEqual(sha(self.db), before)
        conn = _open_read_only(self.db)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM workflow_receipts")
        conn.close()
        self.assertEqual((r["use"], r["actions_enabled"], r["may_change_approval_status"], r["may_select_move"]),
                         ("EVIDENCE_ONLY", False, False, False))
        keys = set(r) | set(r["counts"])
        self.assertFalse({"move", "recommended_move", "approval_status", "action"} & keys)
        text = render(r).lower()
        self.assertIn("evidence only", text)
        for word in ("recommend", "you should", "accept", "counter", "walk away"):
            self.assertNotIn(word, text)

    def test_authorization_required(self):
        with self.assertRaises(PermissionError):
            reference_rate(self.db, replay.query("deal_desk", replay.Q1), principal_id="someone", purpose="x",
                           authorize=replay._allow)

    def test_rules_are_returned_for_inspection(self):
        r = self.ask(replay.query("deal_desk", replay.Q1))
        self.assertEqual(r["rules"]["version"], "fuji.history.v1")
        self.assertEqual(r["family_rules"]["match_exact"], ["approver_role", "offer_side"])
        self.assertIn("horizons are never pooled", " ".join(r["rules"]["match"]))


class HistoryRecordTests(unittest.TestCase):
    def test_existing_unlabelled_records_never_match(self):
        r = reference_rate(FIXTURE, replay.query("credit_committee", "2027-12-31T00:00:00Z"),
                           principal_id="replay-analyst", purpose="history_replay", authorize=replay._allow)
        self.assertEqual(r["status"], "WITHHELD_SPARSE")
        self.assertEqual(r["excluded"]["unlabelled_or_invalid_label"], 54)

    def test_outcome_without_observed_time_is_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "core.sqlite"
            f = Fuji(path)
            exp = f.create_experiment("x")
            for i in range(12):
                case = f.create_case(exp, f"k{i}", "2026-01-01T00:00:00Z", metadata={"classification": "synthetic"})
                p = f.add_proposition(case, "approval", "s", "2026-01-15T00:00:00Z", "r", metadata={"event": {
                    "family": "offer_approval", "version": 1, "approver_role": "deal_desk", "offer_side": "vendor",
                    "horizon_days": 14, "anchor_at": "2026-01-01T00:00:00Z"}})
                f.add_forecast(p, "m", 0.5)
                f.lock_case(case, min_members=1)
                f.resolve(p, True)  # core resolve: no observed_at in notes
            f.close()
            r = reference_rate(path, replay.query("deal_desk", "2030-01-01T00:00:00Z"), principal_id="replay-analyst",
                               purpose="history_replay", authorize=replay._allow)
        self.assertEqual(r["excluded"]["outcome_time_unverifiable"], 12)
        self.assertEqual(r["status"], "WITHHELD_SPARSE")

    def test_lock_validates_event_labels(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError) as e:
                replay_engine_lock(Path(d) / "f.sqlite", {"family": "offer_approval", "version": 1,
                                   "approver_role": "board", "offer_side": "vendor", "horizon_days": 14,
                                   "anchor_at": "2027-01-04T09:00:00Z"})
            self.assertIn("approver_role_not_allowed", str(e.exception))
            with self.assertRaises(ValueError) as e:
                replay_engine_lock(Path(d) / "g.sqlite", {"family": "offer_approval", "version": 1,
                                   "approver_role": "cfo", "offer_side": "vendor", "horizon_days": 14,
                                   "anchor_at": "2027-01-05T09:00:00Z"})
            self.assertIn("event_anchor_after_cutoff", str(e.exception))


def replay_engine_lock(path, event):
    from datetime import datetime, timezone
    from forecast_fuji import core, workflow
    from forecast_fuji.workflow import WorkflowFuji
    replay.ReplayClock.current = datetime(2027, 1, 4, 10, tzinfo=timezone.utc)
    with patch.object(workflow, "datetime", replay.ReplayClock), patch.object(core, "datetime", replay.ReplayClock):
        WorkflowFuji(path, authorize=lambda *a: True).lock({
            "workflow": "w", "principal_id": "p", "purpose": "u", "case_key": "c", "mode": "SHADOW",
            "evidence": {"classification": "synthetic", "source_refs": ["s"], "snapshot_sha256": "0" * 64,
                         "cutoff_at": "2027-01-04T09:00:00Z"},
            "proposition": {"key": "approval", "statement": "s", "horizon": "2027-01-18T09:00:00Z",
                            "resolution_rule": "r", "resolution_source": "x:",
                            "earliest_observable_at": "2027-01-04T11:00:00Z", "event": event},
            "forecasts": [{"member": "m", "probability": 0.5, "generated_at": "2027-01-04T10:00:00Z"}],
            "baseline": {"name": "b", "probability": 0.5, "derivation": "d"}})


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime as NativeDatetime, timezone
from pathlib import Path
from unittest.mock import patch

from forecast_fuji.workflow import WorkflowFuji

class TestClock(NativeDatetime):
    current = NativeDatetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current if tz is not None else cls.current.replace(tzinfo=None)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fuji.sqlite"
        self.allowed = True
        self.calls = []
        def authorize(principal, purpose, refs):
            self.calls.append((principal, purpose, tuple(refs)))
            return self.allowed and principal == "owner-1" and purpose == "investor_discovery" and all(r in {"evidence:123", "gmail:456"} for r in refs)
        self.engine = WorkflowFuji(self.path, authorize=authorize)
        self.packet = {
            "workflow": "Company Zero",
            "principal_id": "owner-1",
            "purpose": "investor_discovery",
            "case_key": "soonami-diligence-2027-02",
            "mode": "SHADOW",
            "evidence": {
                "classification": "private",
                "source_refs": ["evidence:123"],
                "snapshot_sha256": "a" * 64,
                "cutoff_at": "2026-11-17T09:00:00Z"
            },
            "proposition": {
                "key": "INVESTOR_REQUEST",
                "statement": "Named investor requests specific diligence by 2027-02-15",
                "horizon": "2027-02-15",
                "resolution_rule": "TRUE iff consented correspondence explicitly requests diligence",
                "resolution_source": "gmail:456",
                "earliest_observable_at": "2026-11-18T00:00:00Z"
            },
            "forecasts": [{
                "member": "owner",
                "probability": 0.25,
                "generated_at": "2026-11-17T09:30:00Z",
                "model": "human_initial"
            }],
            "baseline": {
                "name": "NAIVE_50",
                "probability": 0.5,
                "derivation": "Neutral baseline, not empirical reference rate"
            },
            "conditioning_action": "Join Venturethon and present a non-binding deck"
        }

    def tearDown(self):
        self.temp.cleanup()

    def lock(self, packet=None):
        with patch("forecast_fuji.workflow.datetime", TestClock):
            return self.engine.lock(packet or self.packet)

    def resolution(self, **changes):
        x = {"workflow": self.packet["workflow"],
             "principal_id": "owner-1",
             "purpose": "investor_discovery",
             "case_key": self.packet["case_key"],
             "outcome": True,
             "source_ref": "gmail:456",
             "source_sha256": "b" * 64,
             "observed_at": "2026-11-19T09:00:00Z",
             "verified_by": "owner-1"}
        x.update(changes)
        return x

    def test_single_member_locks_and_scores_private_outcome(self):
        locked = self.lock()
        self.assertEqual(locked["status"], "LOCKED")
        self.assertEqual(locked["forecast_count"], 1)
        self.assertEqual(locked["kind"], "individual")
        self.assertFalse(locked["actions_enabled"])
        self.assertEqual(self.lock(), locked)
        with patch("forecast_fuji.workflow.datetime", TestClock):
            with self.assertRaises(ValueError):
                self.engine.resolve(self.resolution())
        TestClock.current = NativeDatetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        try:
            with patch("forecast_fuji.workflow.datetime", TestClock):
                scored = self.engine.resolve(self.resolution())
                self.assertAlmostEqual(scored["scores"]["forecast:owner"], 0.5625)
                self.assertAlmostEqual(scored["scores"]["baseline:NAIVE_50"], 0.25)
                self.assertEqual(self.engine.resolve(self.resolution()), scored)
        finally:
            TestClock.current = NativeDatetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)
        with sqlite3.connect(self.path) as db:
            for stmt in [
                "UPDATE cases SET evidence_cutoff_at='2099-01-01' ",
                "UPDATE propositions SET statement='edited'",
                "UPDATE scores SET brier=0",
                "DELETE FROM workflow_receipts",
            ]:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(stmt)

    def test_authorizer_fails_closed_and_original_ledger_is_unchanged(self):
        self.allowed = False
        with self.assertRaises(PermissionError):
            self.lock()
        self.allowed = True
        self.lock()
        self.allowed = False
        with self.assertRaises(PermissionError):
            self.engine.inspect(workflow="Company Zero", principal_id="owner-1",
                purpose="investor_discovery", case_key=self.packet["case_key"],
                source_refs=["evidence:123"])
        with self.assertRaises(PermissionError):
            self.engine.resolve(self.resolution())

    def test_replay_conflict_and_atomic_failure(self):
        self.lock()
        changed = json.loads(json.dumps(self.packet))
        changed["forecasts"][0]["probability"] = 0.9
        with self.assertRaises(ValueError):
            self.lock(changed)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM cases").fetchone()[0], 1)

    def test_late_forged_invalid_and_no_workflow_collision(self):
        late = json.loads(json.dumps(self.packet))
        late["proposition"]["earliest_observable_at"] = "2026-11-17T09:59:00Z"
        with self.assertRaises(ValueError):
            self.lock(late)
        invalid = json.loads(json.dumps(self.packet))
        invalid["forecasts"][0]["probability"] = float("nan")
        with self.assertRaises(ValueError):
            self.lock(invalid)
        other = json.loads(json.dumps(self.packet))
        other["workflow"] = "Career"
        first = self.lock()
        second = self.lock(other)
        self.assertNotEqual(first["case_id"], second["case_id"])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM cases").fetchone()[0], 2)

    def test_unapproved_source_or_wrong_private_resolution_is_denied(self):
        self.lock()
        self.allowed = False
        with self.assertRaises(PermissionError):
            self.engine.inspect(workflow="Company Zero", principal_id="owner-1",
                purpose="investor_discovery", case_key=self.packet["case_key"],
                source_refs=["evidence:123"])
        self.allowed = True
        with self.assertRaises(PermissionError):
            self.engine.inspect(workflow="Company Zero", principal_id="owner-1",
                purpose="investor_discovery", case_key=self.packet["case_key"],
                source_refs=["gmail:456"])
        TestClock.current = NativeDatetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        try:
            with patch("forecast_fuji.workflow.datetime", TestClock):
                with self.assertRaises(ValueError):
                    self.engine.resolve(self.resolution(source_ref="evidence:123"))
        finally:
            TestClock.current = NativeDatetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()

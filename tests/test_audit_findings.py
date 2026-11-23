"""Reproductions for the November 2026 core audit (tested at commit 0fb05de).

Findings 1 and 4 are fixed in this change; their tests check the fix.
Findings 2, 3 and 5 are documented only: their tests pin today's behaviour
and say the proposed rule, so a later change shows up here on purpose.
"""
import sqlite3
import unittest

from forecast_fuji import Fuji


class AuditBase(unittest.TestCase):
    def setUp(self):
        self.fuji = Fuji(":memory:")
        self.exp = self.fuji.create_experiment("audit")
        self.case = self.fuji.create_case(self.exp, "c1", "2026-11-01T00:00:00+00:00")
        self.prop = self.fuji.add_proposition(
            self.case, "SHIP_30D", "The project ships within 30 days.", "30D",
            "Resolve TRUE iff the release is public by day 30.")

    def tearDown(self):
        self.fuji.close()

    def lock_and_resolve(self, outcome=False):
        self.fuji.add_forecast(self.prop, "a", 0.9)
        self.fuji.add_baseline(self.prop, "NAIVE_50", 0.5)
        self.fuji.lock_case(self.case)
        self.fuji.resolve(self.prop, outcome)


class Finding1RecordIntegrity(AuditBase):
    """Finding 1: a locked or resolved record could be rewritten with plain SQL."""

    def test_proposition_cannot_be_rewritten_after_lock(self):
        self.lock_and_resolve()
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "UPDATE propositions SET statement='The project does NOT ship.' WHERE proposition_id=?",
                (self.prop,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "UPDATE propositions SET resolution_rule='anything' WHERE proposition_id=?", (self.prop,))

    def test_proposition_cannot_be_added_or_deleted_after_lock(self):
        self.fuji.add_forecast(self.prop, "a", 0.6)
        self.fuji.lock_case(self.case)
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute("DELETE FROM propositions WHERE proposition_id=?", (self.prop,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "INSERT INTO propositions(proposition_id,case_id,proposition_key,statement,target_horizon,"
                "resolution_rule,created_at) VALUES('x',?,'LATE','late','1D','r','2026')", (self.case,))

    def test_scores_cannot_be_edited_or_deleted(self):
        self.lock_and_resolve()
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute("UPDATE scores SET brier=0.0 WHERE proposition_id=?", (self.prop,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute("DELETE FROM scores WHERE proposition_id=?", (self.prop,))

    def test_scores_must_match_the_resolution(self):
        self.lock_and_resolve(outcome=False)
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "INSERT INTO scores(score_id,proposition_id,method_type,method_name,probability,outcome,brier,"
                "created_at) VALUES('fake',?,'FORECAST','late',1.0,1,0.0,'2026')", (self.prop,))

    def test_case_cannot_be_reopened_or_its_cutoff_moved(self):
        self.lock_and_resolve()
        for sql in (
            "UPDATE cases SET forecast_status='PENDING' WHERE case_id=?",
            "UPDATE cases SET resolution_status='PENDING' WHERE case_id=?",
            "UPDATE cases SET evidence_cutoff_at='2027-01-01T00:00:00+00:00' WHERE case_id=?",
            "DELETE FROM cases WHERE case_id=?",
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.fuji.conn.execute(sql, (self.case,))

    def test_no_late_forecast_or_baseline_even_with_plain_sql(self):
        self.lock_and_resolve()
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "INSERT INTO forecasts(forecast_id,proposition_id,member,probability,locked_at) "
                "VALUES('late',?,'late',0.0,'2026')", (self.prop,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "INSERT INTO baselines(baseline_id,proposition_id,baseline_type,probability,locked_at) "
                "VALUES('late',?,'LATE',0.0,'2026')", (self.prop,))

    def test_no_resolution_before_lock_even_with_plain_sql(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute(
                "INSERT INTO resolutions(resolution_id,proposition_id,outcome,resolved_at) "
                "VALUES('early',?,1,'2026')", (self.prop,))

    def test_insert_or_replace_cannot_overwrite_the_record(self):
        # REPLACE deletes the old row without firing DELETE triggers, so every
        # table refuses an insert that collides with an existing row.
        # Found in the Claude comparison run (its item C1).
        self.lock_and_resolve(outcome=False)
        rid = self.fuji.conn.execute("SELECT resolution_id FROM resolutions").fetchone()[0]
        sid = self.fuji.conn.execute(
            "SELECT score_id FROM scores WHERE method_type='FORECAST'").fetchone()[0]
        fid = self.fuji.conn.execute("SELECT forecast_id FROM forecasts").fetchone()[0]
        cases = (
            ("REPLACE INTO resolutions(resolution_id,proposition_id,outcome,resolved_at) "
             "VALUES(?,?,1,'2026')", (rid, self.prop)),
            ("REPLACE INTO scores(score_id,proposition_id,method_type,method_name,probability,outcome,"
             "brier,created_at) VALUES(?,?,'FORECAST','a',0.9,0,0.0,'2026')", (sid, self.prop)),
            ("REPLACE INTO forecasts(forecast_id,proposition_id,member,probability,locked_at) "
             "VALUES(?,?,'a',0.0,'2026')", (fid, self.prop)),
            ("REPLACE INTO cases(case_id,experiment_id,case_key,evidence_cutoff_at,created_at) "
             "VALUES(?,?,'c1','2026','2026')", (self.case, self.exp)),
        )
        for sql, args in cases:
            with self.subTest(sql=sql.split("(")[0]), self.assertRaises(sqlite3.IntegrityError):
                self.fuji.conn.execute(sql, args)
        outcome = self.fuji.conn.execute("SELECT outcome FROM resolutions").fetchone()[0]
        self.assertEqual(outcome, 0)

    def test_pending_case_can_still_be_edited_before_lock(self):
        # The new rules apply only once a case is locked.
        self.fuji.conn.execute(
            "UPDATE propositions SET statement='Clarified before lock.' WHERE proposition_id=?", (self.prop,))
        self.fuji.conn.execute(
            "UPDATE cases SET evidence_cutoff_at='2026-11-02T00:00:00+00:00' WHERE case_id=?", (self.case,))


class Finding2Independence(AuditBase):
    """Finding 2 (documented): the same model under three names counts as three members.

    Proposed rule: an ensemble needs distinct, independent estimates; members
    that share a model_name (or prompt) count once toward min_members.
    """

    def test_current_behaviour_counts_names_not_models(self):
        for name in ("a", "b", "c"):
            self.fuji.add_forecast(self.prop, name, 0.9, model_name="same-model")
        agg = self.fuji.lock_case(self.case, min_members=3)
        self.assertEqual(agg[0].member_count, 3)


class Finding3ResolutionTiming(AuditBase):
    """Finding 3 (documented): resolve() checks no time at all.

    Early resolution is legitimate when the written rule allows it and
    decisive evidence exists. Proposed rule: record when the outcome became
    known, and refuse a resolution unless every forecast was locked before
    that time and the written rule's timing is met.
    """

    def test_current_behaviour_resolves_with_no_timing_check(self):
        p = self.fuji.add_proposition(self.case, "LONG", "x", "365D", "Resolve at day 365.")
        self.fuji.add_forecast(self.prop, "a", 0.5)
        self.fuji.add_forecast(p, "a", 0.5)
        self.fuji.lock_case(self.case)
        self.assertIn("forecast:a", self.fuji.resolve(p, True))


class Finding4OneForecaster(AuditBase):
    """Finding 4 (fixed): the default required three members.

    The universal workflow contract says one forecaster is sufficient for an
    individual forecast. The default is now 1; an explicit panel size still works.
    """

    def test_one_forecaster_is_enough_by_default(self):
        self.fuji.add_forecast(self.prop, "only", 0.7)
        agg = self.fuji.lock_case(self.case)
        self.assertEqual(agg[0].member_count, 1)

    def test_explicit_panel_size_is_still_enforced(self):
        self.fuji.add_forecast(self.prop, "a", 0.6)
        self.fuji.add_forecast(self.prop, "b", 0.7)
        with self.assertRaises(ValueError):
            self.fuji.lock_case(self.case, min_members=3)

    def test_no_forecast_still_refused(self):
        with self.assertRaises(ValueError):
            self.fuji.lock_case(self.case)

    def test_min_members_below_one_refused(self):
        self.fuji.add_forecast(self.prop, "a", 0.6)
        with self.assertRaises(ValueError):
            self.fuji.lock_case(self.case, min_members=0)


class Finding5Leaderboard(unittest.TestCase):
    """Finding 5 (documented): the leaderboard ranks means over different questions.

    Proposed rule: head-to-head comparisons use only shared resolved
    questions and show how many there were.
    """

    def test_current_behaviour_mixes_question_sets(self):
        fuji = Fuji(":memory:")
        exp = fuji.create_experiment("board")
        # Q1 is easy: both forecasters answer it equally well.
        # Q2..Q4 are hard and only B answers them.
        for i in range(1, 5):
            case = fuji.create_case(exp, f"c{i}", "2026-11-01T00:00:00+00:00")
            p = fuji.add_proposition(case, "P", "x", "1D", "r")
            if i == 1:
                fuji.add_forecast(p, "A", 0.9)
            fuji.add_forecast(p, "B", 0.9 if i == 1 else 0.5)
            fuji.lock_case(case)
            fuji.resolve(p, True)
        rows = {r["method_name"]: r for r in fuji.leaderboard(exp) if r["method_type"] == "FORECAST"}
        # On the one shared question A and B score the same, yet A ranks better.
        self.assertLess(rows["A"]["mean_brier"], rows["B"]["mean_brier"])
        self.assertEqual((rows["A"]["n"], rows["B"]["n"]), (1, 4))
        fuji.close()


if __name__ == "__main__":
    unittest.main()

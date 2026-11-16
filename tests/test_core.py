import sqlite3
import unittest
from forecast_fuji import Fuji


class FujiTests(unittest.TestCase):
    def setUp(self):
        self.fuji = Fuji(":memory:")
        self.exp = self.fuji.create_experiment("test")
        self.case = self.fuji.create_case(self.exp, "c1", "2026-01-01T00:00:00+00:00")
        self.prop = self.fuji.add_proposition(self.case, "P1", "Something happens", "7D", "Resolve from source X")

    def tearDown(self):
        self.fuji.close()

    def test_requires_independent_members(self):
        self.fuji.add_forecast(self.prop, "a", .6)
        self.fuji.add_forecast(self.prop, "b", .7)
        with self.assertRaises(ValueError):
            self.fuji.lock_case(self.case, min_members=3)

    def test_lock_aggregate_and_resolve(self):
        self.fuji.add_baseline(self.prop, "BASE", .5)
        for member, p in [("a", .6), ("b", .7), ("c", .8)]:
            self.fuji.add_forecast(self.prop, member, p)
        agg = self.fuji.lock_case(self.case)
        self.assertAlmostEqual(agg[0].probability, .7)
        scores = self.fuji.resolve(self.prop, True)
        self.assertAlmostEqual(scores["aggregate:mean"], .09)
        board = self.fuji.leaderboard(self.exp)
        self.assertTrue(any(x["method_type"] == "BASELINE" for x in board))

    def test_forecasts_are_immutable(self):
        fid = self.fuji.add_forecast(self.prop, "a", .6)
        with self.assertRaises(sqlite3.IntegrityError):
            self.fuji.conn.execute("UPDATE forecasts SET probability=.9 WHERE forecast_id=?", (fid,))

    def test_no_forecast_after_lock(self):
        for member, p in [("a", .6), ("b", .7), ("c", .8)]:
            self.fuji.add_forecast(self.prop, member, p)
        self.fuji.lock_case(self.case)
        with self.assertRaises(ValueError):
            self.fuji.add_forecast(self.prop, "d", .9)

    def test_calibration_and_paired_baseline_comparison(self):
        for i, (forecast, baseline, outcome) in enumerate([
            (.8, .5, True), (.2, .5, False), (.7, .5, False), (.1, .5, False)
        ]):
            case = self.fuji.create_case(self.exp, f"evaluation-{i}", "2026-01-01T00:00:00Z")
            prop = self.fuji.add_proposition(case, "RESULT", "Binary result", "7D", "Fixed rule")
            for member in ("a", "b", "c"):
                self.fuji.add_forecast(prop, member, forecast)
            self.fuji.add_baseline(prop, "HISTORICAL", baseline)
            self.fuji.lock_case(case)
            self.fuji.resolve(prop, outcome)
        report = self.fuji.calibration_report(self.exp, "AGGREGATE", "mean", bins=5, min_resolved=5)
        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["resolved_count"], 4)
        self.assertEqual(sum(x["count"] for x in report["bins"]), 4)
        self.assertAlmostEqual(report["mean_brier"], (.04 + .04 + .49 + .01) / 4)
        paired = self.fuji.compare_to_baseline(self.exp, "AGGREGATE", "mean", "HISTORICAL", min_paired=4)
        self.assertEqual(paired["status"], "descriptive_only")
        self.assertEqual(paired["paired_count"], 4)
        self.assertAlmostEqual(paired["mean_brier_improvement"], .25 - .145)

    def test_empty_reports_and_no_unpaired_comparison(self):
        self.assertIsNone(self.fuji.calibration_report(self.exp, "FORECAST", "a")["mean_brier"])
        comparison = self.fuji.compare_to_baseline(self.exp, "FORECAST", "a", "MISSING")
        self.assertEqual(comparison["paired_count"], 0)
        self.assertIsNone(comparison["mean_brier_improvement"])
        with self.assertRaises(ValueError):
            self.fuji.calibration_report(self.exp, "INVALID", "a")
        with self.assertRaises(ValueError):
            self.fuji.compare_to_baseline(self.exp, "BASELINE", "a", "b")


if __name__ == "__main__":
    unittest.main()

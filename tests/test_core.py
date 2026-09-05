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


if __name__ == "__main__":
    unittest.main()

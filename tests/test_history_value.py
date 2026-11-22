import unittest

from experiments.history_value import combine
from experiments.history_value.run import verify_freeze


class HistoryValueTests(unittest.TestCase):
    def test_frozen_inputs_unchanged(self):
        # Frozen data must match; code drift (the opt-in stability guard added after the v1 freeze) is recorded.
        self.assertIn("cases.json", verify_freeze(allow_code_drift=True))

    def test_withheld_rate_falls_back_unchanged(self):
        p, applied, why = combine.adjust(0.42, {"status": "WITHHELD_CENSORED", "reasons": ["unresolved share 8/18 > 0.25"]}, [])
        self.assertEqual((p, applied), (0.42, False))
        self.assertIn("WITHHELD_CENSORED", why)

    def test_adjustment_moves_toward_rate_relative_to_own_bias(self):
        h = {"status": "AVAILABLE", "reasons": [], "rate": {"observed": 0.7, "denominator": 30}}
        p, applied, _ = combine.adjust(0.5, h, [0.5] * 30)
        self.assertTrue(applied)
        self.assertGreater(p, 0.5)
        self.assertLess(p, 0.7)
        same, _, _ = combine.adjust(0.5, h, [0.7] * 30)  # analyst already calibrated on that cohort -> no shift
        self.assertAlmostEqual(same, 0.5)


if __name__ == "__main__":
    unittest.main()


class StabilityGuardTests(unittest.TestCase):
    def test_guard_withholds_after_a_rate_change_and_is_opt_in(self):
        import tempfile
        from pathlib import Path
        from experiments.history_value import run
        cases = [c for c in __import__("json").loads((run.FROZEN / "cases.json").read_text()) if c["cohort"] == "drift"]
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "l.sqlite"
            run.build_ledger(db, cases)
            target = next(c for c in cases if c["anchor_at"] >= "2026-12-15")
            q = run.query(target)
            from forecast_fuji.history import reference_rate
            ask = lambda guards: reference_rate(db, {**q, "guards": guards}, principal_id="p", purpose="u",
                                                authorize=lambda *a: True)
            self.assertEqual(ask([])["status"], "AVAILABLE")
            guarded = ask(["stability"])
            self.assertEqual(guarded["status"], "WITHHELD_UNSTABLE")
            self.assertLess(guarded["stability"]["recent_rate"], guarded["stability"]["older_rate"])
            with self.assertRaises(ValueError):
                ask(["made_up"])

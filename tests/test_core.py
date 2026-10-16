"""Tests for spc.core.

Every numeric expectation here was worked out by hand from the definitions in the module docstring
and the AIAG constants table, not copied from the implementation's output. If the code and these
numbers disagree, the code is wrong.
"""
import math
import statistics
import unittest

from spc.core import (CONSTANTS, capability, individuals_chart, moving_ranges, nelson_rules,
                      subgroups, xbar_r_chart)


class TestMovingRangeAndSubgroups(unittest.TestCase):
    def test_moving_ranges(self):
        self.assertEqual(moving_ranges([1, 3, 6, 10]), [2, 3, 4])

    def test_subgroups_drops_short_tail(self):
        self.assertEqual(subgroups([1, 2, 3, 4, 5, 6, 7], 3), [[1, 2, 3], [4, 5, 6]])

    def test_subgroups_rejects_size_one(self):
        with self.assertRaises(ValueError):
            subgroups([1, 2, 3], 1)


class TestCapabilityHandChecked(unittest.TestCase):
    """Data: 9.9, 10.0, 10.1, 10.0, 10.0  with USL 10.2 / LSL 9.8.

    mean = 10.0
    moving ranges = 0.1, 0.1, 0.1, 0.0  -> MRbar = 0.075
    sigma_within  = 0.075 / 1.128 = 0.066489...
    6*sigma_within = 0.398936...  -> Cp = 0.4 / 0.398936 = 1.00266...
    the mean is exactly on the tolerance midpoint, so Cpk == Cp
    sigma_overall = stdev = 0.07071068...
    6*sigma_overall = 0.424264...  -> Pp = 0.4 / 0.424264 = 0.94281...
    """

    VALUES = [9.9, 10.0, 10.1, 10.0, 10.0]

    def test_within_sigma_is_from_moving_range(self):
        cap = capability(self.VALUES, usl=10.2, lsl=9.8)
        self.assertAlmostEqual(cap.std_within, 0.075 / 1.128, places=12)
        self.assertAlmostEqual(cap.std_overall, statistics.stdev(self.VALUES), places=12)

    def test_cp_and_cpk(self):
        cap = capability(self.VALUES, usl=10.2, lsl=9.8)
        self.assertAlmostEqual(cap.cp, 1.00266, places=4)
        self.assertAlmostEqual(cap.cpk, 1.00266, places=4)   # centred, so Cpk == Cp
        self.assertAlmostEqual(cap.cpk, cap.cp, places=12)

    def test_pp_and_ppk(self):
        cap = capability(self.VALUES, usl=10.2, lsl=9.8)
        self.assertAlmostEqual(cap.pp, 0.94281, places=4)
        self.assertAlmostEqual(cap.ppk, 0.94281, places=4)

    def test_pp_is_worse_than_cp_when_overall_spread_is_larger(self):
        cap = capability(self.VALUES, usl=10.2, lsl=9.8)
        self.assertLess(cap.pp, cap.cp)

    def test_mean_and_n(self):
        cap = capability(self.VALUES, usl=10.2, lsl=9.8)
        self.assertEqual(cap.n, 5)
        self.assertAlmostEqual(cap.mean, 10.0, places=12)

    def test_off_centre_lowers_cpk_only(self):
        # same spread, mean 10.05 instead of 10.00 -> distance to USL = 0.15
        vals = [9.95, 10.05, 10.15, 10.05, 10.05]
        cap = capability(vals, usl=10.2, lsl=9.8)
        self.assertAlmostEqual(cap.mean, 10.05, places=12)
        self.assertAlmostEqual(cap.cp, 1.00266, places=4)
        self.assertAlmostEqual(cap.cpk, 0.15 / (3 * (0.075 / 1.128)), places=6)
        self.assertLess(cap.cpk, cap.cp)

    def test_predicted_ppm_matches_the_normal_tail(self):
        # off-centre case: z = 0.15 / 0.0664894 = 2.2560 -> tail 1.207e-2 -> ~12,070 ppm
        vals = [9.95, 10.05, 10.15, 10.05, 10.05]
        cap = capability(vals, usl=10.2, lsl=9.8)
        self.assertTrue(11500 < cap.ppm_within < 12600, cap.ppm_within)
        expected = (1 - 0.5 * (1 + math.erf((10.2 - 10.05) / (0.075 / 1.128) / math.sqrt(2))) + 0.5 * (1 + math.erf((9.8 - 10.05) / (0.075 / 1.128) / math.sqrt(2)))) * 1e6
        self.assertAlmostEqual(cap.ppm_within, expected, places=6)

    def test_single_limit_gives_no_indices(self):
        cap = capability(self.VALUES, usl=10.2)
        self.assertIsNone(cap.cp)
        self.assertIsNone(cap.cpk)
        self.assertTrue(any("both" in n for n in cap.notes))

    def test_no_limits_still_returns_spread(self):
        cap = capability(self.VALUES)
        self.assertIsNone(cap.cpk)
        self.assertGreater(cap.std_within, 0)

    def test_constant_data_has_zero_within_sigma_and_no_indices(self):
        cap = capability([5.0] * 10, usl=5.1, lsl=4.9)
        self.assertEqual(cap.std_within, 0.0)
        self.assertIsNone(cap.cp)
        self.assertIsNone(cap.cpk)
        self.assertTrue(any("moving range is zero" in n or "constant" in n.lower()
                            for n in cap.notes))

    def test_out_of_spec_counting(self):
        cap = capability([9.7, 10.0, 10.0, 10.3], usl=10.2, lsl=9.8)
        self.assertAlmostEqual(cap.pct_out_of_spec, 50.0, places=9)

    def test_too_few_measurements(self):
        with self.assertRaises(ValueError):
            capability([1.0])


class TestControlCharts(unittest.TestCase):
    def test_xbar_r_limits_use_the_constants_table(self):
        # subgroup 1 = 10.00..10.20 (range 0.30), subgroup 2 = 10.10..10.40 (range 0.30)
        vals = [10, 10.1, 10.2, 9.9, 10.0, 10.2, 10.3, 10.4, 10.1, 10.2]
        x, r = xbar_r_chart(vals, 5)
        c = CONSTANTS[5]
        self.assertAlmostEqual(x.center, 10.14, places=9)
        self.assertAlmostEqual(x.ucl, 10.14 + c["A2"] * 0.3, places=9)
        self.assertAlmostEqual(x.lcl, 10.14 - c["A2"] * 0.3, places=9)
        self.assertAlmostEqual(r.center, 0.3, places=9)
        self.assertAlmostEqual(r.ucl, c["D4"] * 0.3, places=9)
        self.assertAlmostEqual(r.lcl, c["D3"] * 0.3, places=9)
        self.assertAlmostEqual(x.sigma, 0.3 / c["d2"], places=12)

    def test_individuals_limits_use_e2_and_d4(self):
        vals = [10.0, 10.2, 9.9, 10.1, 10.0]
        i, mr = individuals_chart(vals)
        mrbar = statistics.fmean(moving_ranges(vals))
        self.assertAlmostEqual(i.center, statistics.fmean(vals), places=12)
        self.assertAlmostEqual(i.ucl, i.center + 2.660 * mrbar, places=9)
        self.assertAlmostEqual(i.lcl, i.center - 2.660 * mrbar, places=9)
        self.assertAlmostEqual(mr.ucl, 3.267 * mrbar, places=9)
        self.assertEqual(mr.lcl, 0.0)

    def test_xbar_rejects_out_of_range_subgroup(self):
        with self.assertRaises(ValueError):
            xbar_r_chart(list(range(30)), 11)


class TestNelsonRules(unittest.TestCase):
    def test_rule_1_beyond_three_sigma(self):
        pts = [10.0] * 9 + [20.0]
        center = statistics.fmean(pts)
        sigma = statistics.fmean(moving_ranges(pts)) / 1.128
        rules = {r for r, _i, _t in nelson_rules(pts, center, sigma)}
        self.assertIn(1, rules)

    def test_rule_2_nine_on_one_side(self):
        pts = [10.0] * 10 + [11.0] * 9      # ten below then nine above
        center = 10.0
        sigma = 1.0
        rules = {r for r, _i, _t in nelson_rules(pts, center, sigma)}
        self.assertIn(2, rules)

    def test_rule_3_six_increasing(self):
        pts = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        rules = {r for r, _i, _t in nelson_rules(pts, 4.0, 2.0)}
        self.assertIn(3, rules)

    def test_rule_4_fourteen_alternating(self):
        pts = [1.0 if i % 2 == 0 else 2.0 for i in range(15)]
        rules = {r for r, _i, _t in nelson_rules(pts, 1.5, 3.0)}
        self.assertIn(4, rules)

    def test_rule_7_fifteen_within_one_sigma(self):
        pts = [10.0 + 0.1 * ((-1) ** i) for i in range(16)]
        rules = {r for r, _i, _t in nelson_rules(pts, 10.0, 1.0)}
        self.assertIn(7, rules)

    def test_zero_sigma_returns_no_violations(self):
        self.assertEqual(nelson_rules([1.0, 2.0, 3.0], 2.0, 0.0), [])

    def test_clean_process_has_no_violations(self):
        # a tight, well-behaved sequence should trip nothing
        pts = [10.00, 10.02, 9.99, 10.01, 10.00, 10.01, 9.98, 10.00, 10.02, 9.99]
        center = statistics.fmean(pts)
        sigma = statistics.fmean(moving_ranges(pts)) / 1.128
        self.assertEqual(nelson_rules(pts, center, sigma), [])


if __name__ == "__main__":
    unittest.main()

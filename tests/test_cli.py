"""Tests for the CSV reader and the command line, including its failure modes."""
import os
import shutil
import tempfile
import unittest

from spc.charts import control_chart_svg
from spc.cli import main, read_column
from spc.core import individuals_chart

GOOD = "part,value\nA,10.00\nA,10.02\nA,9.98\nA,10.01\nA,10.00\nB,10.03\nB,9.99\nB,10.00\n"


class TestReadColumn(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "m.csv")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_reads_a_named_column(self):
        self._write(GOOD)
        values, bad, empty = read_column(self.path, "value")
        self.assertEqual(len(values), 8)
        self.assertEqual((bad, empty), (0, 0))

    def test_missing_column_names_the_ones_that_exist(self):
        self._write(GOOD)
        with self.assertRaises(ValueError) as ctx:
            read_column(self.path, "diameter")
        msg = str(ctx.exception)
        self.assertIn("diameter", msg)
        self.assertIn("value", msg)          # the helpful part: show what IS there

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            read_column(os.path.join(self.dir, "nope.csv"), "value")

    def test_counts_skipped_rows(self):
        self._write("value\n10.0\n\nN/A\n10.2\n   \n10.4\n")
        values, bad, empty = read_column(self.path, "value")
        self.assertEqual(values, [10.0, 10.2, 10.4])
        self.assertEqual(bad, 1)             # "N/A"
        self.assertEqual(empty, 1)           # whitespace-only; DictReader skips truly blank lines

    def test_headerless_file_is_a_clear_error(self):
        self._write("10.0\n10.1\n10.2\n")
        with self.assertRaises(ValueError):
            read_column(self.path, "value")


class TestCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.csv = os.path.join(self.dir, "m.csv")
        with open(self.csv, "w", encoding="utf-8") as fh:
            fh.write(GOOD)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_report_succeeds_and_writes_artifacts(self):
        out = os.path.join(self.dir, "out")
        rc = main(["report", self.csv, "--value", "value", "--lsl", "9.9", "--usl", "10.1",
                   "--feature", "bore diameter", "--out", out])
        self.assertEqual(rc, 0)
        svg = os.path.join(out, "chart.svg")
        md = os.path.join(out, "report.md")
        self.assertTrue(os.path.exists(svg))
        self.assertTrue(os.path.exists(md))
        with open(svg, encoding="utf-8") as fh:
            body = fh.read()
        self.assertTrue(body.startswith("<svg"))
        self.assertIn("bore diameter", body)

    def test_bad_column_exits_one(self):
        rc = main(["report", self.csv, "--value", "nope"])
        self.assertEqual(rc, 1)

    def test_constant_column_exits_two(self):
        path = os.path.join(self.dir, "flat.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("value\n" + "\n".join(["10.000"] * 8) + "\n")
        rc = main(["report", path, "--value", "value", "--lsl", "9.9", "--usl", "10.1"])
        self.assertEqual(rc, 2)

    def test_single_measurement_exits_two(self):
        path = os.path.join(self.dir, "one.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("value\n10.0\n")
        rc = main(["report", path, "--value", "value"])
        self.assertEqual(rc, 2)

    def test_subgroup_mode_runs(self):
        vals = [str(10 + 0.01 * (i % 5)) for i in range(20)]
        path = os.path.join(self.dir, "sub.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("value\n" + "\n".join(vals) + "\n")
        rc = main(["report", path, "--value", "value", "--subgroup", "5",
                   "--lsl", "9.9", "--usl", "10.2"])
        self.assertEqual(rc, 0)


class TestSvg(unittest.TestCase):
    def test_svg_is_wellformed_ish_and_marks_violations(self):
        chart, _mr = individuals_chart([10.0] * 9 + [20.0])
        svg = control_chart_svg(chart, title="spike")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.rstrip().endswith("</svg>"))
        self.assertIn("UCL", svg)
        self.assertIn("rule", svg.lower())

    def test_svg_escapes_the_title(self):
        chart, _mr = individuals_chart([10.0, 10.1, 9.9])
        svg = control_chart_svg(chart, title="a <b> & c")
        self.assertIn("a &lt;b&gt; &amp; c", svg)


if __name__ == "__main__":
    unittest.main()

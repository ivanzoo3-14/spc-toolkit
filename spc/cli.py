"""spc.cli -- command line front end.

    spc report measurements.csv --value diameter --lsl 9.95 --usl 10.05
    spc report measurements.csv --value diameter --lsl 9.95 --usl 10.05 --subgroup 5
    spc report measurements.csv --value diameter --feature "Bore diameter"

Writes a text report to stdout and, with --out DIR, an SVG control chart plus a markdown report.

Exit codes: 0 ok, 1 usage/IO error, 2 data problem (constant data, too few samples).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import List, Optional, Sequence, Tuple

from . import __version__
from .charts import write_png, write_svg
from .core import (Capability, Chart, capability, individuals_chart, recommend, xbar_r_chart)


def read_column(path: str, column: str) -> Tuple[List[float], int, int]:
    """Read one numeric column from a CSV.

    Returns (values, skipped_non_numeric, skipped_empty). Raises ValueError with a useful message
    if the column is missing, which is the mistake people actually make.
    """
    if not os.path.exists(path):
        raise ValueError(f"file not found: {path}")
    values: List[float] = []
    skipped_bad = skipped_empty = 0
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("the file appears to be empty")
        if column not in reader.fieldnames:
            raise ValueError(
                f"column {column!r} not found. Columns present: {', '.join(reader.fieldnames)}")
        for row in reader:
            raw = (row.get(column) or "").strip()
            if raw == "":
                skipped_empty += 1
                continue
            try:
                values.append(float(raw))
            except ValueError:
                skipped_bad += 1
    return values, skipped_bad, skipped_empty


def _fmt(v: Optional[float], places: int = 4) -> str:
    return "n/a" if v is None else f"{v:.{places}g}"


def report_text(cap: Capability, charts: Sequence[Chart], feature: str) -> str:
    lines: List[str] = []
    lines.append(f"SPC report - {feature}")
    lines.append("=" * (12 + len(feature)))
    lines.append(f"measurements            : {cap.n}")
    lines.append(f"mean                    : {_fmt(cap.mean, 6)}")
    if cap.usl is not None:
        lines.append(f"USL                     : {_fmt(cap.usl, 6)}")
    if cap.lsl is not None:
        lines.append(f"LSL                     : {_fmt(cap.lsl, 6)}")
    lines.append(f"std dev, within (short) : {_fmt(cap.std_within, 6)}")
    lines.append(f"std dev, overall (long) : {_fmt(cap.std_overall, 6)}")
    lines.append("")
    lines.append(f"Cp                      : {_fmt(cap.cp, 3)}")
    lines.append(f"Cpk                     : {_fmt(cap.cpk, 3)}")
    lines.append(f"Pp                      : {_fmt(cap.pp, 3)}")
    lines.append(f"Ppk                     : {_fmt(cap.ppk, 3)}")
    if cap.ppm_within is not None:
        lines.append(f"predicted defect rate   : {cap.ppm_within:,.0f} ppm (within sigma)")
    if cap.ppm_overall is not None:
        lines.append(f"observed-shape estimate : {cap.ppm_overall:,.0f} ppm (overall sigma)")
    if cap.pct_out_of_spec is not None:
        lines.append(f"measured outside limits : {cap.pct_out_of_spec:.2f}% of samples")

    for ch in charts:
        lines.append("")
        lines.append(f"{ch.kind} chart")
        lines.append(f"  centre {_fmt(ch.center, 6)}   UCL {_fmt(ch.ucl, 6)}   LCL {_fmt(ch.lcl, 6)}")
        if ch.violations:
            for rule, idx, txt in ch.violations:
                lines.append(f"  rule {rule}: {txt}")
        else:
            lines.append("  no Nelson-rule violations")

    notes = recommend_notes(cap)
    if notes:
        lines.append("")
        lines.append("reading")
        for n in notes:
            lines.append(f"  - {n}")

    if cap.notes:
        lines.append("")
        lines.append("method notes")
        for n in cap.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)


def recommend_notes(cap: Capability) -> List[str]:
    """Re-run the conservative reading against an already-computed Capability."""
    from .core import _normal_cdf  # local import keeps the public surface small
    out: List[str] = []
    if cap.std_within == 0:
        out.append("Within sigma is zero - the column is constant. Fix the data first.")
        return out
    if cap.cpk is not None:
        if cap.cpk >= 1.33:
            out.append(f"Cpk {cap.cpk:.2f} >= 1.33: capable against these limits as measured.")
        elif cap.cpk >= 1.00:
            out.append(f"Cpk {cap.cpk:.2f} is marginal (1.00-1.33): expect occasional out-of-spec "
                       f"parts and a customer asking for improvement.")
        else:
            out.append(f"Cpk {cap.cpk:.2f} < 1.00: the spread alone produces out-of-spec parts.")
        if cap.ppk is not None and cap.cpk - cap.ppk > 0.30:
            out.append(f"Cpk {cap.cpk:.2f} vs Ppk {cap.ppk:.2f}: short-term is much better than "
                       f"actual performance - look for drift or shifts between subgroups.")
        if cap.usl is not None and cap.lsl is not None:
            centre = (cap.usl + cap.lsl) / 2.0
            half = (cap.usl - cap.lsl) / 2.0
            off = cap.mean - centre
            if half > 0 and abs(off) > 0.10 * half:
                out.append(f"The mean is {abs(off):.4g} {'above' if off > 0 else 'below'} the "
                           f"tolerance midpoint ({100 * abs(off) / half:.0f}% of half the width) - "
                           f"centring would raise Cpk without changing the spread.")
    if cap.pct_out_of_spec is not None and cap.pct_out_of_spec > 0:
        out.append(f"{cap.pct_out_of_spec:.2f}% of the measured samples are outside the limits. "
                   f"Capability indices describe a distribution; these are parts.")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spc",
        description="Process capability and control charts from a CSV of measurements.")
    p.add_argument("--version", action="version", version=f"spc {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("report", help="capability indices + control chart for one measured feature")
    r.add_argument("csv", help="CSV file containing the measurements")
    r.add_argument("--value", required=True, help="name of the column holding measurements")
    r.add_argument("--usl", type=float, default=None, help="upper specification limit")
    r.add_argument("--lsl", type=float, default=None, help="lower specification limit")
    r.add_argument("--subgroup", type=int, default=None,
                   help="subgroup size 2-10 for an X-bar/R chart (default: individuals I-MR)")
    r.add_argument("--feature", default=None, help="feature name for the report title")
    r.add_argument("--units", default="", help="unit label, e.g. mm")
    r.add_argument("--out", default=None, help="directory to write chart.svg and report.md into")
    r.add_argument("--png", action="store_true", help="also write chart.png if matplotlib is present")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "report":
        print("unknown command", file=sys.stderr)
        return 1

    feature = args.feature or args.value
    try:
        values, skipped_bad, skipped_empty = read_column(args.csv, args.value)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if len(values) < 2:
        print(f"error: only {len(values)} usable measurement(s) in column {args.value!r}. "
              f"At least 2 are needed for a moving range.", file=sys.stderr)
        return 2
    if skipped_bad or skipped_empty:
        print(f"note: skipped {skipped_empty} empty and {skipped_bad} non-numeric row(s)")

    try:
        cap = capability(values, usl=args.usl, lsl=args.lsl, subgroup_size=args.subgroup)
        if args.subgroup:
            primary, secondary = xbar_r_chart(values, args.subgroup)
        else:
            primary, secondary = individuals_chart(values)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if cap.std_within == 0:
        print("warning: within sigma is 0 (constant data). Nothing meaningful to report.",
              file=sys.stderr)

    print(report_text(cap, [primary, secondary], feature))

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        svg = os.path.join(args.out, "chart.svg")
        write_svg(svg, primary, title=f"{feature} - {primary.kind} chart", units=args.units,
                  subtitle=f"{cap.n} samples | centre {primary.center:.4g} | "
                           f"UCL {primary.ucl:.4g} | LCL {primary.lcl:.4g}")
        print(f"\nwrote {svg}")
        md = os.path.join(args.out, "report.md")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("```\n" + report_text(cap, [primary, secondary], feature) + "\n```\n")
        print(f"wrote {md}")
        if args.png:
            png = write_png(os.path.join(args.out, "chart.png"), primary,
                            title=f"{feature} - {primary.kind} chart")
            if png:
                print(f"wrote {png}")

    return 2 if cap.std_within == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

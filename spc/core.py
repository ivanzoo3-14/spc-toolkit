"""spc.core -- process capability and control-chart statistics.

Standard-library only. The control-chart constants are the AIAG SPC manual values, transcribed
literally in CONSTANTS below so they can be checked against the table by eye.

Definitions used:
  * within sigma  -- short-term, from the average moving range (individuals) or the average
                     subgroup range (X-bar/R). This is the sigma behind Cp/Cpk.
  * overall sigma -- the plain sample standard deviation of every measurement. This is the sigma
                     behind Pp/Ppk.

Cp/Cpk describe what the process could do if it stayed on target; Pp/Ppk describe what it actually
did. If Cpk and Ppk disagree badly, the process is drifting, not just spread out.

Nothing here is validated against your gauge, fixture or drawing. It validates the arithmetic.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# AIAG control-chart constants by subgroup size n (2..10).
CONSTANTS: Dict[int, Dict[str, float]] = {
    2: {"A2": 1.880, "D3": 0.000, "D4": 3.267, "d2": 1.128},
    3: {"A2": 1.023, "D3": 0.000, "D4": 2.574, "d2": 1.693},
    4: {"A2": 0.729, "D3": 0.000, "D4": 2.282, "d2": 2.059},
    5: {"A2": 0.577, "D3": 0.000, "D4": 2.114, "d2": 2.326},
    6: {"A2": 0.483, "D3": 0.000, "D4": 2.004, "d2": 2.534},
    7: {"A2": 0.419, "D3": 0.076, "D4": 1.924, "d2": 2.704},
    8: {"A2": 0.373, "D3": 0.136, "D4": 1.864, "d2": 2.847},
    9: {"A2": 0.337, "D3": 0.184, "D4": 1.816, "d2": 2.970},
    10: {"A2": 0.308, "D3": 0.223, "D4": 1.777, "d2": 3.078},
}

E2_INDIVIDUALS = 2.660   # X chart limit factor for individuals (moving range of 2)
D4_MOVING_RANGE = 3.267  # MR chart upper limit factor for a moving range of 2


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def moving_ranges(values: Sequence[float]) -> List[float]:
    """|x[i] - x[i-1]| for i in 1..n-1."""
    return [abs(values[i] - values[i - 1]) for i in range(1, len(values))]


def subgroups(values: Sequence[float], size: int) -> List[List[float]]:
    """Split into consecutive groups of `size`; a trailing short group is dropped."""
    if size < 2:
        raise ValueError("subgroup size must be >= 2")
    out = [list(values[i:i + size]) for i in range(0, len(values), size)]
    if out and len(out[-1]) < size:
        out.pop()
    return out


@dataclass
class Capability:
    """Capability and performance indices, plus the pieces they were computed from."""
    n: int
    mean: float
    std_within: float
    std_overall: float
    usl: Optional[float] = None
    lsl: Optional[float] = None
    cp: Optional[float] = None
    cpk: Optional[float] = None
    pp: Optional[float] = None
    ppk: Optional[float] = None
    ppm_within: Optional[float] = None
    ppm_overall: Optional[float] = None
    pct_out_of_spec: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["notes"] = list(self.notes)
        return d


@dataclass
class Chart:
    """A control chart: centre line, limits, the plotted points, and rule violations."""
    kind: str                       # "individuals" | "xbar" | "moving_range" | "range"
    center: float
    ucl: float
    lcl: float
    points: List[float]
    sigma: float                    # the plotted-point sigma implied by the limits
    violations: List[Tuple[int, int, str]] = field(default_factory=list)  # (rule, index, text)


def capability(values: Sequence[float], usl: Optional[float] = None, lsl: Optional[float] = None,
               subgroup_size: Optional[int] = None) -> Capability:
    """Compute capability (Cp/Cpk) and performance (Pp/Ppk) indices.

    subgroup_size=None -> individuals: within sigma from the average moving range.
    subgroup_size=n    -> X-bar/R:    within sigma from the average subgroup range.
    """
    vals = [float(v) for v in values]
    if len(vals) < 2:
        raise ValueError("need at least 2 measurements")

    mean = statistics.fmean(vals)
    std_overall = statistics.stdev(vals)
    notes: List[str] = []

    if subgroup_size and subgroup_size > 1:
        if subgroup_size not in CONSTANTS:
            raise ValueError(f"subgroup size must be between 2 and 10, got {subgroup_size}")
        groups = subgroups(vals, subgroup_size)
        if len(groups) < 2:
            raise ValueError("need at least 2 complete subgroups")
        rbar = statistics.fmean(max(g) - min(g) for g in groups)
        d2 = CONSTANTS[subgroup_size]["d2"]
        std_within = rbar / d2
        notes.append(f"within sigma from {len(groups)} subgroups of {subgroup_size} (Rbar/d2)")
    else:
        mrs = moving_ranges(vals)
        mrbar = statistics.fmean(mrs) if mrs else 0.0
        std_within = mrbar / CONSTANTS[2]["d2"]
        notes.append("within sigma from the average moving range (MRbar/1.128)")
        if mrbar == 0:
            notes.append("WARNING: every moving range is zero - within sigma is 0 and "
                         "capability indices are undefined. Check for a stuck gauge or a "
                         "constant input column.")

    cap = Capability(n=len(vals), mean=mean, std_within=std_within, std_overall=std_overall,
                     usl=usl, lsl=lsl, notes=notes)

    if usl is not None and lsl is not None:
        if std_within > 0:
            cap.cp = (usl - lsl) / (6.0 * std_within)
            cap.cpk = min((usl - mean) / (3.0 * std_within), (mean - lsl) / (3.0 * std_within))
        else:
            notes.append("Cp/Cpk not computed: within sigma is 0")
        if std_overall > 0:
            cap.pp = (usl - lsl) / (6.0 * std_overall)
            cap.ppk = min((usl - mean) / (3.0 * std_overall), (mean - lsl) / (3.0 * std_overall))
        else:
            notes.append("Pp/Ppk not computed: overall sigma is 0")
    elif usl is not None or lsl is not None:
        notes.append("only one specification limit given - Cp/Cpk/Pp/Ppk need both")

    if std_within > 0 and (usl is not None or lsl is not None):
        above = 1.0 - _normal_cdf((usl - mean) / std_within) if usl is not None else 0.0
        below = _normal_cdf((lsl - mean) / std_within) if lsl is not None else 0.0
        cap.ppm_within = (above + below) * 1e6
    if std_overall > 0 and (usl is not None or lsl is not None):
        above = 1.0 - _normal_cdf((usl - mean) / std_overall) if usl is not None else 0.0
        below = _normal_cdf((lsl - mean) / std_overall) if lsl is not None else 0.0
        cap.ppm_overall = (above + below) * 1e6

    if usl is not None or lsl is not None:
        bad = sum(1 for v in vals
                  if (usl is not None and v > usl) or (lsl is not None and v < lsl))
        cap.pct_out_of_spec = 100.0 * bad / len(vals)

    return cap


def individuals_chart(values: Sequence[float]) -> Tuple[Chart, Chart]:
    """I-MR chart: returns (individuals chart, moving range chart)."""
    vals = [float(v) for v in values]
    if len(vals) < 2:
        raise ValueError("need at least 2 measurements")
    mean = statistics.fmean(vals)
    mrs = moving_ranges(vals)
    mrbar = statistics.fmean(mrs)
    sigma = mrbar / CONSTANTS[2]["d2"]

    i_chart = Chart("individuals", mean, mean + E2_INDIVIDUALS * mrbar,
                    mean - E2_INDIVIDUALS * mrbar, vals, sigma)
    mr_chart = Chart("moving_range", mrbar, D4_MOVING_RANGE * mrbar, 0.0, mrs, sigma)

    i_chart.violations = nelson_rules(i_chart.points, i_chart.center, i_chart.sigma)
    mr_chart.violations = nelson_rules(mr_chart.points, mr_chart.center, mr_chart.sigma)
    return i_chart, mr_chart


def xbar_r_chart(values: Sequence[float], subgroup_size: int) -> Tuple[Chart, Chart]:
    """X-bar / R chart: returns (X-bar chart, R chart)."""
    if subgroup_size not in CONSTANTS:
        raise ValueError(f"subgroup size must be between 2 and 10, got {subgroup_size}")
    groups = subgroups(values, subgroup_size)
    if len(groups) < 2:
        raise ValueError("need at least 2 complete subgroups")
    c = CONSTANTS[subgroup_size]
    means = [statistics.fmean(g) for g in groups]
    ranges = [max(g) - min(g) for g in groups]
    xbarbar = statistics.fmean(means)
    rbar = statistics.fmean(ranges)
    sigma = rbar / c["d2"]

    x_chart = Chart("xbar", xbarbar, xbarbar + c["A2"] * rbar, xbarbar - c["A2"] * rbar,
                    means, sigma)
    r_chart = Chart("range", rbar, c["D4"] * rbar, c["D3"] * rbar, ranges, sigma)
    x_chart.violations = nelson_rules(x_chart.points, x_chart.center, x_chart.sigma)
    r_chart.violations = nelson_rules(r_chart.points, r_chart.center, r_chart.sigma)
    return x_chart, r_chart


# ---------------------------------------------------------------------------------------------
# Nelson rules. Implemented against the plotted sequence, centre line and sigma. Rule numbering
# follows Nelson (1984); these are the rules most SPC software offers by default.
# ---------------------------------------------------------------------------------------------
def nelson_rules(points: Sequence[float], center: float, sigma: float) -> List[Tuple[int, int, str]]:
    """Return [(rule_number, index_of_last_point_in_run, description), ...]."""
    out: List[Tuple[int, int, str]] = []
    if sigma is None or sigma <= 0:
        return out
    p = list(points)
    n = len(p)
    z = [(x - center) / sigma for x in p]

    # rule 1 -- any point beyond 3 sigma
    for i, zi in enumerate(z):
        if abs(zi) > 3.0:
            out.append((1, i, f"point {i + 1} is {zi:+.2f} sigma from the centre line"))

    # rule 2 -- nine points in a row on the same side
    for i in range(8, n):
        window = z[i - 8:i + 1]
        if all(v > 0 for v in window) or all(v < 0 for v in window):
            out.append((2, i, f"nine points in a row on one side, ending at point {i + 1}"))

    # rule 3 -- six points steadily increasing or decreasing
    for i in range(5, n):
        window = p[i - 5:i + 1]
        inc = all(window[k] < window[k + 1] for k in range(5))
        dec = all(window[k] > window[k + 1] for k in range(5))
        if inc or dec:
            out.append((3, i, f"six points {'increasing' if inc else 'decreasing'} "
                              f"in a row, ending at point {i + 1}"))

    # rule 4 -- fourteen points alternating up and down
    for i in range(13, n):
        window = p[i - 13:i + 1]
        diffs = [window[k + 1] - window[k] for k in range(13)]
        if all(d != 0 for d in diffs) and all(
                (diffs[k] > 0) != (diffs[k + 1] > 0) for k in range(len(diffs) - 1)):
            out.append((4, i, f"fourteen points alternating, ending at point {i + 1}"))

    # rule 5 -- two of three consecutive points beyond 2 sigma, same side
    for i in range(2, n):
        w = z[i - 2:i + 1]
        if sum(1 for v in w if v > 2.0) >= 2 or sum(1 for v in w if v < -2.0) >= 2:
            out.append((5, i, f"two of three points beyond 2 sigma, ending at point {i + 1}"))

    # rule 6 -- four of five consecutive points beyond 1 sigma, same side
    for i in range(4, n):
        w = z[i - 4:i + 1]
        if sum(1 for v in w if v > 1.0) >= 4 or sum(1 for v in w if v < -1.0) >= 4:
            out.append((6, i, f"four of five points beyond 1 sigma, ending at point {i + 1}"))

    # rule 7 -- fifteen points in a row within 1 sigma (either side) = stratification
    for i in range(14, n):
        if all(abs(v) < 1.0 for v in z[i - 14:i + 1]):
            out.append((7, i, f"fifteen points within 1 sigma, ending at point {i + 1}"))

    # rule 8 -- eight points in a row beyond 1 sigma (either side) = mixture
    for i in range(7, n):
        if all(abs(v) > 1.0 for v in z[i - 7:i + 1]):
            out.append((8, i, f"eight points beyond 1 sigma, ending at point {i + 1}"))

    return out


def recommend(values: Sequence[float], subgroup_size: Optional[int] = None) -> List[str]:
    """Plain-language reading of the numbers. Deliberately conservative and non-prescriptive."""
    cap = capability(values, subgroup_size=subgroup_size)
    out: List[str] = []
    if cap.std_within == 0:
        out.append("Within sigma is zero - the data is constant. Fix the data before reading "
                   "anything else.")
        return out
    if cap.cpk is not None:
        if cap.cpk >= 1.33:
            out.append(f"Cpk {cap.cpk:.2f} >= 1.33: the process is capable against these limits "
                       f"as measured, assuming the gauge is trustworthy.")
        elif cap.cpk >= 1.00:
            out.append(f"Cpk {cap.cpk:.2f} is between 1.00 and 1.33: marginal. Expect occasional "
                       f"out-of-spec parts, and expect the customer to ask for improvement.")
        else:
            out.append(f"Cpk {cap.cpk:.2f} < 1.00: not capable. The process spread alone produces "
                       f"out-of-spec parts.")
        if cap.ppk is not None and cap.cpk - cap.ppk > 0.30:
            out.append(f"Cpk {cap.cpk:.2f} vs Ppk {cap.ppk:.2f}: the short-term capability is much "
                       f"better than actual performance, which points at drift or shifts between "
                       f"subgroups rather than pure spread.")
        centre = (cap.usl + cap.lsl) / 2.0 if (cap.usl is not None and cap.lsl is not None) else None
        if centre is not None:
            off = cap.mean - centre
            half = (cap.usl - cap.lsl) / 2.0
            if half > 0 and abs(off) > 0.10 * half:
                side = "above" if off > 0 else "below"
                out.append(f"The mean sits {abs(off):.4g} {side} the midpoint of the tolerance "
                           f"({100.0 * abs(off) / half:.0f}% of half the tolerance width) - "
                           f"centring the process would raise Cpk without touching the spread.")
    return out

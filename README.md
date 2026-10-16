# spc-toolkit

Process capability indices and control charts from a CSV of measurements.

**Standard library only.** No numpy, no pandas, no matplotlib, no account, no network. Clone it and
run it.

[![ci](https://github.com/ivanzoo3-14/spc-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ivanzoo3-14/spc-toolkit/actions/workflows/ci.yml)

---

## Why this exists

I spent nine years on manufacturing floors — eight at BMW Manufacturing as a production specialist
and robot technician, then quality specialist roles at Magna International and NRTC Automation, where
I inspected parts with CMM, gauges, vision systems and weld and torque checks.

In that time the capability number always arrived the same way: a spreadsheet someone else built, or
a black-box module inside a larger package. You typed the readings in, a `Cpk` appeared, and you sent
it to the customer. Nobody in the room could tell you which sigma the number used.

This is that arithmetic, in the open, with the constants written out where you can check them against
the AIAG table by eye. It is deliberately small. It computes; it does not decide.

## Quickstart

No installation, no dependencies:

```bash
python3 -m spc report examples/bore_diameter.csv \
    --value value --lsl 9.90 --usl 10.10 \
    --feature "bore diameter" --units mm --out out
```

```
SPC report - bore diameter
==========================
measurements            : 60
mean                    : 10.0081
USL                     : 10.1
LSL                     : 9.9
std dev, within (short) : 0.0242968
std dev, overall (long) : 0.0356902

Cp                      : 1.37
Cpk                     : 1.26
Pp                      : 0.934
Ppk                     : 0.858
predicted defect rate   : 82 ppm (within sigma)
observed-shape estimate : 6,240 ppm (overall sigma)
measured outside limits : 3.33% of samples

individuals chart
  centre 10.0081   UCL 10.081   LCL 9.9352
  rule 1: point 11 is -5.68 sigma from the centre line
  rule 1: point 46 is +5.84 sigma from the centre line
  rule 5: two of three points beyond 2 sigma, ending at point 59
  rule 6: four of five points beyond 1 sigma, ending at point 48
  rule 6: four of five points beyond 1 sigma, ending at point 59
  rule 6: four of five points beyond 1 sigma, ending at point 60

moving_range chart
  centre 0.0274068   UCL 0.0895379   LCL 0
  rule 1: point 10 is +4.05 sigma from the centre line
  rule 1: point 11 is +4.65 sigma from the centre line
  rule 1: point 45 is +4.25 sigma from the centre line
  rule 1: point 46 is +3.08 sigma from the centre line
  rule 2: nine points in a row on one side, ending at point 31
  ...

reading
  - Cpk 1.26 is marginal (1.00-1.33): expect occasional out-of-spec parts and a customer asking for
    improvement.
  - Cpk 1.26 vs Ppk 0.86: short-term is much better than actual performance - look for drift or
    shifts between subgroups.
  - 3.33% of the measured samples are outside the limits. Capability indices describe a distribution;
    these are parts.

method notes
  - within sigma from the average moving range (MRbar/1.128)

wrote out\chart.svg
wrote out\report.md
```

`out/chart.svg` is a control chart with the centre line and limits drawn where the statistics put
them, and rule-breaking points marked. It is hand-written SVG, so there is nothing to render.

The example dataset is generated, not scraped or invented after the fact — and it deliberately
contains the three things a technician actually deals with: process noise, a slow drift, and two
outliers. Regenerate it with:

```bash
python3 examples/make_example.py
```

## What it computes

| | |
|---|---|
| **Capability** | Cp, Cpk (within sigma) |
| **Performance** | Pp, Ppk (overall sigma) |
| **Defect estimates** | ppm from both sigmas, plus the measured % outside the limits |
| **Individuals chart** | I chart with `Xbar ± 2.660·MRbar`, MR chart with `UCL = 3.267·MRbar` |
| **X-bar / R chart** | subgroup sizes 2–10, using the AIAG `A2`, `D3`, `D4`, `d2` constants |
| **Nelson rules** | all eight, checked against the plotted sequence |

## The method, in one paragraph

`Cp = (USL − LSL) / 6σ_within` and `Cpk = min((USL − μ)/3σ_within, (μ − LSL)/3σ_within)`. `Pp` and
`Ppk` are identical formulas using the **overall** sample standard deviation instead. Within sigma is
short-term variation from the average moving range (`MRbar / d2`, `d2 = 1.128` for a moving range of
two) or from the average subgroup range (`Rbar / d2`) in X-bar/R mode. Defect estimates come from the
normal tail, `Φ`, via `math.erf`.

The distinction is the useful part: **Cpk is what the process could do if it held still; Ppk is what
it actually did.** When they disagree by more than about 0.3, the process is drifting rather than
merely spread out, and the report says so.

## CLI

```
spc report <file.csv> --value <column> [--lsl X] [--usl Y]
                       [--subgroup N] [--feature NAME] [--units U]
                       [--out DIR] [--png]
```

| flag | meaning |
|---|---|
| `--value` | the column holding measurements (required) |
| `--lsl`, `--usl` | specification limits — both are needed for indices |
| `--subgroup N` | 2–10, switches to an X-bar/R chart (default: individuals I-MR) |
| `--out DIR` | writes `chart.svg` and `report.md` |
| `--png` | additionally writes `chart.png` **if** matplotlib happens to be installed |

Exit codes: **0** ok · **1** usage or file error · **2** data problem (constant column, too few
samples). Constant data — a stuck gauge, or a column that was never actually measured — is the most
common real failure, and it gets its own code.

## What this does **not** do

Stated plainly, because the limits matter more than the features:

- **It does not validate your measurement system.** MSA / Gage R&R is not implemented. If the gauge
  is wrong, every number here inherits that.
- **It does not decide conformance.** It reports statistics. A human signs the inspection record.
- **It assumes normality** for capability indices and ppm. A strongly skewed or bimodal process needs
  a transformation or a different method; this will happily give you a confident wrong answer.
- **It reads one column of one CSV at a time.** No gauge output formats, no multi-feature batches,
  no database connections.
- **It implements Nelson's rules only**, not the full Western Electric set.
- **It is not PPAP software.** It will not produce a PSW or a submission package, and it is not a
  substitute for whatever your customer requires you to run.

## Development

```bash
python3 -m unittest discover -s tests -v      # 37 tests, no dependencies
```

The test expectations were worked out **by hand** from the definitions and the constants table, not
copied from the implementation's output — CP/Cpk/Pp/Ppk values, X-bar/R limits, ppm tails against
`math.erf`, and each Nelson rule against a synthetic sequence engineered to trip exactly that rule.
CI runs the suite on Python 3.9 and 3.12, asserts that runtime dependencies stay empty, and smoke-runs
the CLI against the example dataset.

## Install as a package (optional)

```bash
pip install -e .            # provides the `spc` command
pip install -e ".[png]"     # adds matplotlib for PNG charts
```

## License

MIT — see [LICENSE](LICENSE).

**Not engineering advice.** This software computes statistics from numbers you supply. It does not
validate your gauge, fixture, drawing or technique, and it does not decide whether a part conforms.
The person who signs the inspection record is responsible for the result.

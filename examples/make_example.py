"""Generate examples/bore_diameter.csv -- a small, realistic, reproducible quality dataset.

Why a generator instead of a committed mystery file: anyone reading the repo can see exactly what
the numbers are and regenerate them. The dataset intentionally contains the three things a quality
technician actually deals with -- normal process noise, a slow drift, and a couple of genuine
outliers -- so the report shows something worth reading.

    python examples/make_example.py

The output is deterministic: same file, every run.
"""
import csv
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bore_diameter.csv")

NOMINAL = 10.000     # mm
NOISE_SIGMA = 0.020  # mm, short-term machine variation
DRIFT_START = 20     # sample index where the tool starts to wander
DRIFT_PER_SAMPLE = 0.0009
OUTLIERS = {10: -0.130, 45: +0.150}   # sample index -> offset in mm


def main() -> None:
    rng = random.Random(20261016)   # fixed seed: the dataset is reproducible
    rows = []
    for i in range(60):
        value = NOMINAL + rng.gauss(0.0, NOISE_SIGMA)
        if i >= DRIFT_START:
            value += DRIFT_PER_SAMPLE * (i - DRIFT_START)

        if i in OUTLIERS:
            value = NOMINAL + OUTLIERS[i]

        rows.append({"sample": i + 1, "part": f"LOT-4471-{i // 10 + 1:02d}",
                     "operator": "op2" if i % 2 else "op1",
                     "value": f"{value:.4f}"})

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["sample", "part", "operator", "value"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()

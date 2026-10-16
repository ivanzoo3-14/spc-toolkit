"""spc -- process capability and control charts for manufacturing measurements.

Standard-library only. No account, no network, no key.
"""
from .core import (  # noqa: F401
    CONSTANTS,
    Capability,
    Chart,
    capability,
    individuals_chart,
    moving_ranges,
    nelson_rules,
    recommend,
    subgroups,
    xbar_r_chart,
)

__version__ = "0.1.0"

__all__ = [
    "CONSTANTS", "Capability", "Chart", "capability", "individuals_chart", "moving_ranges",
    "nelson_rules", "recommend", "subgroups", "xbar_r_chart", "__version__",
]

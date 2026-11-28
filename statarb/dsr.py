"""Deflated Sharpe Ratio toolkit (Bailey and López de Prado, 2014)."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def expected_max(n: float) -> float:
    """Approximate the expected maximum of ``n`` independent standard normal draws.

    Parameters
    ----------
    n : float
        Number of independent trials, ``n > 1``; it can be fractional (an effective number of trials).

    Returns
    -------
    float
        ``(1 - γ) Z⁻¹(1 - 1/n) + γ Z⁻¹(1 - 1/(n e))``, with γ the Euler-Mascheroni constant and Z⁻¹ the
        standard normal quantile.

    Notes
    -----
    Eq. 5 of the paper, from the Gumbel limit of the maximum. It slightly overestimates the exact value,
    by 0.036 at n = 10 and 0.014 at n = 1000 (``notebooks/02_gumbel_check.ipynb``), so a threshold built
    on it errs on the conservative side.
    """
    assert n > 1, "the expected maximum needs more than one trial"
    g = np.euler_gamma
    return float((1 - g) * norm.ppf(1 - 1 / n) + g * norm.ppf(1 - 1 / (n * np.e)))

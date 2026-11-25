import numpy as np
import pandas as pd

from statarb.spread import ar_terms


def test_pure_bid_ask_bounce_recovers_spread() -> None:
    # constant mid, high = ask, low = bid, close randomly at bid or ask: the estimator should give s
    s, n = 0.01, 4000
    rng = np.random.default_rng(0)
    bid, ask = 100 * (1 - s / 2), 100 * (1 + s / 2)
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2010-01-01", periods=n),
            "ticker": "X",
            "source": "tiingo",
            "symbol": "X",
            "high": ask,
            "low": bid,
            "close": np.where(rng.random(n) < 0.5, bid, ask),
            "split_factor": 1.0,
        }
    )
    est = 2 * np.sqrt(ar_terms(df).mean())
    assert abs(est - s) < 5e-4


def test_split_does_not_look_like_a_spread() -> None:
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-08-27", periods=3),
            "ticker": "X",
            "source": "tiingo",
            "symbol": "X",
            "high": [101.0, 101.0, 25.25],
            "low": [99.0, 99.0, 24.75],
            "close": [100.0, 101.0, 25.0],
            "split_factor": [1.0, 1.0, 4.0],
        }
    )
    # undone split: ~0.01 * 0.01; a raw 4:1 split would give ~0.01 * log(4)
    assert abs(ar_terms(df).iloc[1]) < 1e-3

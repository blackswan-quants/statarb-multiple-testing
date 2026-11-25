import numpy as np
import pandas as pd

from statarb.returns import total_return


def test_split_dividend_and_source_switch() -> None:
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-08-27", periods=5),
            "ticker": "AAPL",
            "source": ["wiki", "wiki", "wiki", "wiki", "yahoo"],
            "symbol": "AAPL",
            "close": [500.0, 505.0, 126.25, 125.0, 30.0],
            "div_cash": [0.0, 0.0, 0.0, 1.25, 0.0],
            "split_factor": [1.0, 1.0, 4.0, 1.0, 1.0],
        }
    )
    r = total_return(df)
    assert np.isnan(r[0]) and np.isnan(r[4])  # first row of each source series
    assert np.isclose(r[1], 0.01)
    assert np.isclose(r[2], 0.0)  # 4:1 split: 126.25 * 4 / 505 - 1
    assert np.isclose(r[3], 0.0)  # (125 + 1.25) / 126.25 - 1

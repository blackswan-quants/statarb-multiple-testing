import pandas as pd

from statarb.universe import build_membership, membership_intervals


def test_membership_carries_forward_and_splits_stays() -> None:
    snaps = pd.DataFrame(
        {"tickers": [["A", "B"], ["A"], ["A", "B"]]},
        index=pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-07"]),
    )
    days = pd.bdate_range("2020-01-02", "2020-01-08", name="date")  # Thu 2, Fri 3, Mon 6, Tue 7, Wed 8
    m = build_membership(snaps, days)
    assert m.groupby("date").size().tolist() == [2, 1, 1, 2, 2]

    iv = membership_intervals(m, days).set_index("ticker")
    assert iv.loc["A", "start"] == days[0] and iv.loc["A", "end"] == days[-1]
    b = iv.loc["B"].sort_values("start")
    assert b["start"].tolist() == [days[0], days[3]]
    assert b["end"].tolist() == [days[0], days[-1]]

import pytest

from statarb.dsr import expected_max


def test_expected_max_paper_example() -> None:
    # paper's numerical example, N = 100: 0.4228 * 2.326 + 0.5772 * 2.680
    assert expected_max(100) == pytest.approx(2.531, abs=1e-3)

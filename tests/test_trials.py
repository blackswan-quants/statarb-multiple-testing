import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb.trials import canonical_json, config_hash, load_index, load_matrix, log_trial


def test_same_config_same_hash() -> None:
    a = {"window": 60, "s_entry": 1.25, "costs": {"spread_bps": 5, "impact": "ac"}}
    b = {"costs": {"impact": "ac", "spread_bps": 5}, "s_entry": 1.25, "window": 60}  # same, other order
    assert canonical_json(a) == '{"costs":{"impact":"ac","spread_bps":5},"s_entry":1.25,"window":60}'
    assert config_hash(a) == config_hash(b)
    assert len(config_hash(a)) == 64
    assert config_hash(a) != config_hash({**a, "window": 90})
    assert config_hash(a) != config_hash({**a, "window": 60.0})  # types matter


def test_nan_rejected() -> None:
    with pytest.raises(ValueError):
        config_hash({"s_entry": math.nan})


def test_dummy_run_logged(tmp_path: Path) -> None:
    dates = pd.bdate_range("2010-01-04", periods=250)
    gross = pd.Series(np.random.default_rng(0).normal(0.0005, 0.01, 250), index=dates)
    net = gross - 0.0001  # flat cost of 1 bp a day
    config = {"window": 60, "s_entry": 1.25}

    tid = log_trial(config, gross, net, root=tmp_path)

    index = load_index(tmp_path)
    assert list(index["trial_id"]) == [tid]
    assert index.loc[0, "config_hash"] == config_hash(config)
    assert index.loc[0, "summary.n_days"] == 250
    net_matrix = load_matrix("net", root=tmp_path)
    assert net_matrix.shape == (250, 1)  # T x N
    assert np.allclose(net_matrix[tid], net)

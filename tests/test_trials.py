import math

import pytest

from statarb.trials import canonical_json, config_hash


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

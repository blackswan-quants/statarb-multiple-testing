"""Trial logger: every backtest run is recorded in ``trials/`` (schema in ``docs/trials.md``)."""

from __future__ import annotations

import hashlib
import json
import logging

from statarb.config import ROOT

log = logging.getLogger(__name__)

TRIALS = ROOT / "trials"


def canonical_json(config: dict[str, object]) -> str:
    """Serialize a config as canonical JSON: sorted keys, no whitespace, UTF-8, no NaN or Infinity.

    Parameters
    ----------
    config : dict[str, object]
        Full configuration of the run.

    Returns
    -------
    str
        The canonical JSON string.

    Raises
    ------
    ValueError
        If the config contains NaN or Infinity.
    TypeError
        If a value is not JSON-serializable (e.g. a numpy scalar or a date).

    Notes
    -----
    Key order does not change the output, types do: ``60`` and ``60.0`` give different JSON and hashes.
    Non-JSON values are rejected instead of converted, so a config is hashed exactly as it is read back.
    """
    return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def config_hash(config: dict[str, object]) -> str:
    """Hash the canonical JSON of a config with SHA-256 (64 hex characters)."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()

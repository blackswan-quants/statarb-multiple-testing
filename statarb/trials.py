"""Trial logger: every backtest run is recorded in ``trials/`` (schema in ``docs/trials.md``)."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from statarb.config import ROOT
from statarb.errors import InvalidPnLError

log = logging.getLogger(__name__)

TRIALS = ROOT / "trials"
SCHEMA_VERSION = 1


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


def sharpe(r: pd.Series) -> float | None:
    """Annualized Sharpe ratio sqrt(252) * mean / std of daily returns (sample std, no risk-free rate).

    Returns None when the standard deviation is zero or undefined (a strategy that never trades, one day).
    """
    sd = r.std(ddof=1)
    return math.sqrt(252) * float(r.mean()) / sd if sd > 0 else None


def max_drawdown(r: pd.Series) -> float:
    """Largest peak-to-trough loss of the compounded equity curve, as a number <= 0 (e.g. -0.12)."""
    equity = (1 + r).cumprod()
    return float((equity / equity.cummax().clip(lower=1) - 1).min())


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def log_trial(
    config: dict[str, object], pnl_gross: pd.Series, pnl_net: pd.Series, root: Path = TRIALS
) -> str:
    """Record one backtest run as ``<trial_id>.json`` (metadata) and ``<trial_id>.parquet`` (daily PnL).

    Parameters
    ----------
    config : dict[str, object]
        Everything that can change the PnL (period, universe, windows, thresholds, cost model, seed).
    pnl_gross, pnl_net : pd.Series
        Daily portfolio returns before and after costs, indexed by the same sorted, unique trading dates.
    root : Path
        Folder of the log, ``trials/`` by default (tests pass a temporary folder).

    Returns
    -------
    str
        The ``trial_id``, ``<UTC timestamp>_<first 12 chars of config_hash>``.

    Raises
    ------
    InvalidPnLError
        If the two series do not share the same sorted, unique dates or contain missing values.

    Notes
    -----
    Every run is logged, also with uncommitted changes: it still counts in N. Such runs get ``dirty: true``
    and a warning, since the commit alone cannot reproduce them. The parquet is written before the JSON, so a
    JSON on disk always has its PnL.
    """
    if not pnl_gross.index.equals(pnl_net.index):
        raise InvalidPnLError("pnl_gross and pnl_net must have the same dates")
    dates = pd.DatetimeIndex(pnl_gross.index)
    if not (dates.is_monotonic_increasing and dates.is_unique):
        raise InvalidPnLError("dates must be sorted and unique")
    if pnl_gross.isna().any() or pnl_net.isna().any():
        raise InvalidPnLError("PnL has missing values: a day without positions has PnL 0")

    h = config_hash(config)
    now = datetime.now(UTC)
    trial_id = f"{now:%Y%m%dT%H%M%S%fZ}_{h[:12]}"
    dirty = _git("status", "--porcelain", "--untracked-files=no") != ""
    if dirty:
        log.warning("Trial %s logged with uncommitted changes (dirty=true)", trial_id)

    pnl = pd.DataFrame({"date": dates, "pnl_gross": pnl_gross.to_numpy(), "pnl_net": pnl_net.to_numpy()})
    record = {
        "schema_version": SCHEMA_VERSION,
        "trial_id": trial_id,
        "config": json.loads(canonical_json(config)),
        "config_hash": h,
        "commit": _git("rev-parse", "HEAD"),
        "dirty": dirty,
        "timestamp_utc": now.isoformat().replace("+00:00", "Z"),
        "summary": {
            "n_days": len(pnl),
            "sharpe_gross": sharpe(pnl["pnl_gross"]),
            "sharpe_net": sharpe(pnl["pnl_net"]),
            "max_drawdown_gross": max_drawdown(pnl["pnl_gross"]),
            "max_drawdown_net": max_drawdown(pnl["pnl_net"]),
        },
    }
    root.mkdir(parents=True, exist_ok=True)
    pnl.to_parquet(root / f"{trial_id}.parquet", index=False)
    (root / f"{trial_id}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    log.info("Logged trial %s (%d days)", trial_id, len(pnl))
    return trial_id


def load_index(root: Path = TRIALS) -> pd.DataFrame:
    """Read every ``<trial_id>.json`` into one row per trial, sorted by time.

    Nested fields become columns: ``config.window``, ``summary.sharpe_net``, ...
    """
    records = [json.loads(p.read_text()) for p in sorted(root.glob("*.json"))]
    return pd.json_normalize(records)


def load_matrix(kind: str = "net", root: Path = TRIALS) -> pd.DataFrame:
    """Daily returns of every trial as a T x N matrix: dates as rows, ``trial_id`` as columns.

    Parameters
    ----------
    kind : str
        ``"net"`` or ``"gross"``.
    root : Path
        Folder of the log, ``trials/`` by default.

    Returns
    -------
    pd.DataFrame
        One column per trial in time order; NaN where a trial does not cover a date.
    """
    cols = {
        p.stem: pd.read_parquet(p, columns=["date", f"pnl_{kind}"]).set_index("date")[f"pnl_{kind}"]
        for p in sorted(root.glob("*.parquet"))
    }
    return pd.DataFrame(cols)

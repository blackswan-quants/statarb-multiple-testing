"""Disk checkpoints: immutable raw files with a manifest, and processed parquet tables."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from statarb.config import DATA

log = logging.getLogger(__name__)


def save_raw(content: bytes, name: str, url: str) -> Path:
    """Write a downloaded payload to ``data/raw`` as-is and log it in the manifest.

    Parameters
    ----------
    content : bytes
        Payload exactly as received.
    name : str
        File name inside ``data/raw`` (may contain subfolders).
    url : str
        Source URL, recorded for provenance.

    Returns
    -------
    Path
        Path of the written file.

    Notes
    -----
    Raw files are never edited afterwards; re-downloading overwrites the file and appends a new manifest row,
    so the manifest keeps the full history of what was fetched and when.
    """
    path = DATA / "raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    row = pd.DataFrame(
        {
            "fetched_at": [datetime.now(UTC).isoformat(timespec="seconds")],
            "file": [name],
            "url": [url],
            "sha256": [hashlib.sha256(content).hexdigest()],
            "bytes": [len(content)],
        }
    )
    manifest = DATA / "raw" / "manifest.csv"
    row.to_csv(manifest, mode="a", header=not manifest.exists(), index=False)
    log.info("raw saved: %s (%.1f kB)", name, len(content) / 1e3)
    return path


def save(df: pd.DataFrame, name: str, stage: str = "processed") -> Path:
    """Save a table as parquet under ``data/<stage>/<name>.parquet``."""
    path = DATA / stage / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    log.info("saved %s: %d rows", path.relative_to(DATA), len(df))
    return path


def load(name: str, stage: str = "processed") -> pd.DataFrame:
    """Load a table saved with `save`."""
    return pd.read_parquet(DATA / stage / f"{name}.parquet")

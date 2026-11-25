"""``python -m statarb``: rebuild every processed table from the raw files, in order.

``--download`` also refetches the sources (index file, Tiingo list and prices, WIKI, sp500-data, FRED,
French); without it only the local steps run.
"""

from __future__ import annotations

import importlib
import sys

DOWNLOAD = ["universe", "tiingo", "wiki", "sp500data", "macro"]
PROCESS = ["symbols", "reconcile", "returns", "sector", "spread", "qa"]

if __name__ == "__main__":
    steps = DOWNLOAD + PROCESS if "--download" in sys.argv else PROCESS
    for name in steps:
        sys.argv = [name]  # modules read their own argv
        importlib.import_module(f"statarb.{name}").main()

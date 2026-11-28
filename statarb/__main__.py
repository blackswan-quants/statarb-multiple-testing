"""``python -m statarb``: rebuild every processed table from the raw files, in order.

``--download`` also refetches the index file, the Tiingo ticker list, WIKI, sp500-data, FRED and French.
Tiingo prices have their own resumable command: ``python -m statarb.tiingo prices``.
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

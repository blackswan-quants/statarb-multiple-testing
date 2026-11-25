"""Project constants and settings loaded from `.env`."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.logging import RichHandler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
START, END = "2006-01-01", "2025-12-31"
SECTOR_ETFS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
ETFS = [*SECTOR_ETFS, "SPY"]


class Settings(BaseSettings):
    """Secrets from `.env`. Instantiating it without ``TIINGO_API_KEY`` raises ``ValidationError``."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    tiingo_api_key: str


def setup_logging() -> None:
    """Configure rich logging for CLI entry points."""
    logging.basicConfig(level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])

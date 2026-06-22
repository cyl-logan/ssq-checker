"""SSQ (Chinese welfare lottery 双色球) result checker."""
from .fetcher import fetch_latest_draw, Draw
from .checker import check_prize, PrizeResult, format_report

__all__ = ["fetch_latest_draw", "Draw", "check_prize", "PrizeResult", "format_report"]

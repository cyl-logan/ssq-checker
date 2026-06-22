"""Fetch latest SSQ draw from 17500.cn (only reliable source for curl-based access)."""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from typing import List

DATA_URL = "https://www.17500.cn/getData/ssq.TXT"
DEFAULT_TIMEOUT = 10


@dataclass(frozen=True)
class Draw:
    """One SSQ draw."""
    issue: str           # e.g. "2026070"
    date: str            # "YYYY-MM-DD"
    reds: List[str]      # 6 red balls, draw order, zero-padded "01"..."33"
    blue: str            # blue ball, zero-padded "01"..."16"

    @property
    def reds_sorted(self) -> List[str]:
        return sorted(self.reds, key=int)


def parse_line(line: str) -> Draw:
    """Parse one line from 17500.cn ssq.TXT.

    Format: issue date red1 red2 red3 red4 red5 red6 blue ...sorted_reds... sales pool ...
    """
    parts = line.strip().split()
    if len(parts) < 9:
        raise ValueError(f"Malformed SSQ line, got {len(parts)} fields: {line!r}")
    return Draw(
        issue=parts[0],
        date=parts[1],
        reds=parts[2:8],
        blue=parts[8],
    )


def fetch_latest_draw(url: str = DATA_URL, timeout: int = DEFAULT_TIMEOUT) -> Draw:
    """Fetch the most recent SSQ draw."""
    req = urllib.request.Request(url, headers={"User-Agent": "ssq-checker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode("utf-8", errors="replace")
    # data is append-only; latest = last non-empty line
    for line in reversed(text.splitlines()):
        if line.strip():
            return parse_line(line)
    raise RuntimeError("Empty response from data source")

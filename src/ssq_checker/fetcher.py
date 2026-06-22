"""Fetch latest SSQ draw from 17500.cn (only reliable source for curl-based access)."""
from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from typing import List

DATA_URL = "https://www.17500.cn/getData/ssq.TXT"
DEFAULT_TIMEOUT = 10

# Strict shapes for fields that flow into filenames (history.month_of slices the
# date) and into the static dashboard. A compromised feed must not be able to
# inject path-traversal or HTML into either.
_ISSUE_RE = re.compile(r"^\d{4,10}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BALL_RE = re.compile(r"^\d{1,2}$")


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

    Fields are strictly validated — malformed issue/date/balls are rejected so
    the downstream history writer and dashboard can trust them.
    """
    parts = line.strip().split()
    if len(parts) < 9:
        raise ValueError(f"Malformed SSQ line, got {len(parts)} fields: {line!r}")
    issue, date = parts[0], parts[1]
    if not _ISSUE_RE.match(issue):
        raise ValueError(f"Invalid issue {issue!r} in line: {line!r}")
    if not _DATE_RE.match(date):
        raise ValueError(f"Invalid date {date!r} in line: {line!r}")
    reds = list(parts[2:8])
    blue = parts[8]
    for n in (*reds, blue):
        if not _BALL_RE.match(n):
            raise ValueError(f"Invalid ball number {n!r} in line: {line!r}")
    return Draw(issue=issue, date=date, reds=reds, blue=blue)


def parse_all(text: str) -> List[Draw]:
    """Parse every draw line in the feed. Malformed lines are silently dropped
    (the feed has no header, but defensive parsing keeps a single bad row from
    blowing up history sync)."""
    draws: List[Draw] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            draws.append(parse_line(line))
        except ValueError:
            continue
    return draws


def _fetch_text(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ssq-checker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_latest_draw(url: str = DATA_URL, timeout: int = DEFAULT_TIMEOUT) -> Draw:
    """Fetch the most recent SSQ draw."""
    text = _fetch_text(url, timeout)
    # data is append-only; latest = last non-empty line
    for line in reversed(text.splitlines()):
        if line.strip():
            return parse_line(line)
    raise RuntimeError("Empty response from data source")


def fetch_all_draws(url: str = DATA_URL, timeout: int = DEFAULT_TIMEOUT) -> List[Draw]:
    """Fetch the full draw history from the feed."""
    draws = parse_all(_fetch_text(url, timeout))
    if not draws:
        raise RuntimeError("Empty response from data source")
    return draws

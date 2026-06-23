"""Red/blue ball distribution statistics over the full draw feed.

Pure computation, no I/O in `compute_stats`. The classic SSQ analytics:
- count      出现次数: how many draws the ball appeared in
- gap        当前遗漏: draws since its last appearance (0 = in the latest draw)
- max_gap    最大遗漏: longest run of consecutive draws without it
- avg_gap    平均遗漏: total omissions / (count + 1) = (total_draws - count) / (count + 1)

Frequency (出现概率) is derived client-side from count/total_draws to keep the
JSON minimal and avoid float drift. These describe past data only — each draw is
an independent random event, so this is reference, not prediction.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from .fetcher import Draw

RED_NUMS = [f"{i:02d}" for i in range(1, 34)]   # 01..33
BLUE_NUMS = [f"{i:02d}" for i in range(1, 17)]  # 01..16


def _ball_stats(draws: List[Draw], nums: List[str], pick) -> List[dict]:
    """Per-ball count / current gap / max gap / avg gap, draws assumed in order.

    `pick(draw)` returns the set of balls drawn (reds set, or single-blue set).
    """
    count: Dict[str, int] = {n: 0 for n in nums}
    cur_gap: Dict[str, int] = {n: 0 for n in nums}
    max_gap: Dict[str, int] = {n: 0 for n in nums}
    for draw in draws:
        present = pick(draw)
        for n in nums:
            if n in present:
                count[n] += 1
                cur_gap[n] = 0
            else:
                cur_gap[n] += 1
                if cur_gap[n] > max_gap[n]:
                    max_gap[n] = cur_gap[n]
    total = len(draws)
    out: List[dict] = []
    for n in nums:
        c = count[n]
        out.append({
            "num": n,
            "count": c,
            "gap": cur_gap[n],
            "max_gap": max_gap[n],
            "avg_gap": round((total - c) / (c + 1), 1),
        })
    return out


def compute_stats(draws: List[Draw]) -> dict:
    """Frequency + omission stats for every red (01-33) and blue (01-16) ball.

    Returns the body dict (no timestamp); see `write_stats` for persistence.
    """
    ordered = sorted(draws, key=lambda d: (d.date, d.issue))
    reds = _ball_stats(ordered, RED_NUMS, lambda d: set(d.reds))
    blue = _ball_stats(ordered, BLUE_NUMS, lambda d: {d.blue})
    span = {}
    if ordered:
        span = {
            "first_date": ordered[0].date,
            "last_date": ordered[-1].date,
            "first_issue": ordered[0].issue,
            "last_issue": ordered[-1].issue,
        }
    return {
        "total_draws": len(ordered),
        "span": span,
        "reds": reds,
        "blue": blue,
    }


def write_stats(
    data_dir: str,
    draws: List[Draw],
    generated_at: str | None = None,
) -> dict:
    """Compute stats and write `data_dir/stats.json`, preserving `generated_at`
    when the body is unchanged so re-runs without a new draw stay diff-clean."""
    body = compute_stats(draws)

    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "stats.json")
    existing: dict | None = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, ValueError):
            existing = None

    existing_body = {k: v for k, v in existing.items() if k != "generated_at"} if existing else None
    if existing_body == body and existing is not None:
        return existing

    manifest = {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **body,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest

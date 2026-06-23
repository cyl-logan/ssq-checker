"""Append-only, month-partitioned profit/loss history.

Each draw is recorded **once**, with a snapshot of the bets that were active when
it was recorded, then frozen. Changing `bets.csv` later only affects draws recorded
afterwards — past months are never recomputed. This lets the user switch numbers
over time without rewriting history.

Layout (committed to git, served by Pages):
    docs/data/YYYY-MM.json   one file per month, list of draw records
    docs/data/index.json     manifest: month list + order-independent totals
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List

from .bets import Bet
from .checker import bet_winnings, check_prize
from .fetcher import Draw

TIER_RANK = {"一等奖": 1, "二等奖": 2, "三等奖": 3, "四等奖": 4, "五等奖": 5, "六等奖": 6}

# Month files are exactly `YYYY-MM.json`; anything else in the data dir (index.json,
# stats.json, stray files) must not be loaded as a month record.
_MONTH_FILE_RE = re.compile(r"^\d{4}-\d{2}\.json$")


def month_of(date: str) -> str:
    """'2025-01-02' -> '2025-01'."""
    return date[:7]


def build_record(draw: Draw, bets: List[Bet]) -> dict:
    """Compute a frozen, self-contained record for one draw against `bets`."""
    won = 0
    pool_win = False
    best_rank: int | None = None
    for b in bets:
        r = check_prize(b.reds, b.blue, draw)
        if r.tier is not None:
            rank = TIER_RANK[r.tier]
            best_rank = rank if best_rank is None else min(best_rank, rank)
        w = bet_winnings(r, b.multiplier)
        if w is None:
            pool_win = True
        else:
            won += w
    cost = sum(b.cost for b in bets)
    best_tier = next((t for t, rk in TIER_RANK.items() if rk == best_rank), None)
    return {
        "issue": draw.issue,
        "date": draw.date,
        "bets": [{"reds": b.reds, "blue": b.blue, "multiplier": b.multiplier} for b in bets],
        "cost": cost,
        "won": won,
        "net": won - cost,
        "best_tier": best_tier,
        "pool_win": pool_win,
    }


def _load_months(data_dir: str) -> Dict[str, List[dict]]:
    months: Dict[str, List[dict]] = {}
    if not os.path.isdir(data_dir):
        return months
    for name in os.listdir(data_dir):
        if not _MONTH_FILE_RE.match(name):
            continue
        with open(os.path.join(data_dir, name), encoding="utf-8") as f:
            payload = json.load(f)
        months[payload["month"]] = payload["draws"]
    return months


def sync_history(
    data_dir: str,
    draws: List[Draw],
    bets: List[Bet],
    start_date: str,
    generated_at: str | None = None,
) -> dict:
    """Add records for any draws (>= start_date) not yet stored, then rewrite the
    affected month files and the manifest. Existing records are left untouched.

    Returns the manifest dict, with an extra `added` count of new records.
    """
    months = _load_months(data_dir)
    known = {rec["issue"] for recs in months.values() for rec in recs}

    added = 0
    touched: set[str] = set()
    for d in draws:
        if d.date < start_date or d.issue in known:
            continue
        m = month_of(d.date)
        months.setdefault(m, []).append(build_record(d, bets))
        known.add(d.issue)
        touched.add(m)
        added += 1

    os.makedirs(data_dir, exist_ok=True)
    for m in touched:
        months[m].sort(key=lambda r: (r["date"], r["issue"]))
        with open(os.path.join(data_dir, f"{m}.json"), "w", encoding="utf-8") as f:
            json.dump({"month": m, "draws": months[m]}, f, ensure_ascii=False, indent=2)

    all_records = [rec for recs in months.values() for rec in recs]
    total_cost = sum(r["cost"] for r in all_records)
    total_won = sum(r["won"] for r in all_records)
    pool_wins = sum(1 for r in all_records if r["pool_win"])
    latest = max(all_records, key=lambda r: (r["date"], r["issue"]), default=None)

    body = {
        "start_date": start_date,
        "months": sorted(months.keys()),
        "summary": {
            "draws": len(all_records),
            "total_cost": total_cost,
            "total_won": total_won,
            "net": total_won - total_cost,
            "pool_wins": pool_wins,
        },
        "current_bets": [
            {"reds": b.reds, "blue": b.blue, "multiplier": b.multiplier} for b in bets
        ],
        "latest": latest,
    }

    # Preserve `generated_at` when business data is unchanged so the workflow's
    # git diff stays clean and we don't push empty bot commits every run.
    idx_path = os.path.join(data_dir, "index.json")
    existing: dict | None = None
    if os.path.exists(idx_path):
        try:
            with open(idx_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, ValueError):
            existing = None

    existing_body = {k: v for k, v in existing.items() if k != "generated_at"} if existing else None
    if existing_body == body and existing is not None:
        manifest = existing
    else:
        manifest = {
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **body,
        }
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    manifest = {**manifest, "added": added}
    return manifest

"""CLI entrypoint: python -m ssq_checker [--reds 01 02 ...] [--blue 07] [--bets bets.csv]"""
from __future__ import annotations

import argparse
import os
import sys

from .bets import load_bets
from .checker import (
    bet_winnings,
    check_prize,
    format_bets_report,
    format_report,
    normalize,
)
from .fetcher import fetch_all_draws, fetch_latest_draw
from .history import sync_history
from .notify import send_telegram
from .stats import write_stats

DEFAULT_REDS = ["01", "02", "03", "04", "08", "09"]
DEFAULT_BLUE = "07"
DEFAULT_BETS_PATH = "bets.csv"
DEFAULT_START_DATE = "2025-01-01"
DEFAULT_DATA_DIR = "docs/data"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check SSQ draw against your bet table or fixed numbers.")
    p.add_argument("--reds", nargs=6, default=None,
                   help="6 red balls (1-33) for a one-off check. Overrides the bet table.")
    p.add_argument("--blue", default=None,
                   help="1 blue ball (1-16) for a one-off check.")
    p.add_argument("--bets", default=None,
                   help=f"Path to the bet-table CSV. Default: {DEFAULT_BETS_PATH} "
                        "(used automatically if it exists and --reds is not given). "
                        "If explicitly set to a missing file the command errors out.")
    p.add_argument("--json", action="store_true", help="Output JSON instead of formatted report.")
    p.add_argument("--telegram", action="store_true",
                   help="Also send the report to Telegram. Reads TELEGRAM_BOT_TOKEN "
                        "and TELEGRAM_CHAT_ID from the environment.")
    p.add_argument("--sync-history", action="store_true",
                   help="Record any not-yet-stored draws into the month-partitioned "
                        "history (for the Pages dashboard). Past records are frozen.")
    p.add_argument("--start-date", default=DEFAULT_START_DATE,
                   help=f"First draw date to include in history. Default: {DEFAULT_START_DATE}.")
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                   help=f"Directory holding the month history files. Default: {DEFAULT_DATA_DIR}.")
    args = p.parse_args(argv)
    args.bets_path = args.bets if args.bets is not None else DEFAULT_BETS_PATH

    # `--blue` only makes sense alongside `--reds` (the one-off path); without
    # `--reds` we can't tell whether the user wants the bet table or a defaulted
    # red set, so refuse rather than silently ignore the flag.
    if args.blue is not None and args.reds is None:
        p.error("--blue requires --reds")

    if args.sync_history:
        return _sync_history(args)

    # Mode selection: explicit --reds forces a one-off single check. Otherwise
    # the bet table is used if present; an explicit --bets pointing at a missing
    # file is a hard error (don't silently fall back to defaults and report the
    # wrong numbers).
    if args.reds is not None:
        use_table = False
    elif args.bets is not None and not os.path.exists(args.bets_path):
        print(f"❌ 投注表不存在：{args.bets_path}", file=sys.stderr)
        return 4
    else:
        use_table = os.path.exists(args.bets_path)

    try:
        draw = fetch_latest_draw()
    except Exception as e:
        print(f"❌ 拉取双色球开奖数据失败：{e}", file=sys.stderr)
        return 2

    if use_table:
        try:
            bets = load_bets(args.bets_path)
        except (OSError, ValueError) as e:
            print(f"❌ 读取投注表失败（{args.bets_path}）：{e}", file=sys.stderr)
            return 4
        results = [(b, check_prize(b.reds, b.blue, draw)) for b in bets]
        report = format_bets_report(draw, results)
        payload = {
            "issue": draw.issue, "date": draw.date,
            "draw_reds": draw.reds_sorted, "draw_blue": draw.blue,
            "total_cost": sum(b.cost for b in bets),
            "bets": [
                {
                    "reds": b.reds, "blue": b.blue, "multiplier": b.multiplier,
                    "cost": b.cost, "red_hits": r.red_hits,
                    "red_matched": r.red_matched, "blue_hit": r.blue_hit,
                    "tier": r.tier, "winnings": bet_winnings(r, b.multiplier),
                }
                for b, r in results
            ],
        }
    else:
        user_reds = normalize(args.reds if args.reds is not None else DEFAULT_REDS)
        user_blue = f"{int(args.blue if args.blue is not None else DEFAULT_BLUE):02d}"
        result = check_prize(user_reds, user_blue, draw)
        report = format_report(draw, user_reds, user_blue, result)
        payload = {
            "issue": draw.issue, "date": draw.date,
            "draw_reds": draw.reds_sorted, "draw_blue": draw.blue,
            "user_reds": user_reds, "user_blue": user_blue,
            "red_hits": result.red_hits, "red_matched": result.red_matched,
            "blue_hit": result.blue_hit,
            "tier": result.tier, "amount": result.amount,
        }

    if args.json:
        import json as _json
        print(_json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(report)

    if args.telegram:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        try:
            send_telegram(report, token, chat_id)
        except Exception as e:
            print(f"❌ Telegram 投递失败：{e}", file=sys.stderr)
            return 3

    return 0


def _sync_history(args) -> int:
    try:
        bets = load_bets(args.bets_path)
    except (OSError, ValueError) as e:
        print(f"❌ 读取投注表失败（{args.bets_path}）：{e}", file=sys.stderr)
        return 4
    try:
        draws = fetch_all_draws()
    except Exception as e:
        print(f"❌ 拉取历史开奖数据失败：{e}", file=sys.stderr)
        return 2

    manifest = sync_history(args.data_dir, draws, bets, args.start_date)
    stats = write_stats(args.data_dir, draws)
    s = manifest["summary"]
    verdict = "盈利" if s["net"] > 0 else ("持平" if s["net"] == 0 else "亏损")
    print(f"✅ 历史已同步到 {args.data_dir}（新增{manifest['added']}期，共{s['draws']}期）："
          f"投入¥{s['total_cost']}，中奖¥{s['total_won']}，"
          f"净{verdict} ¥{abs(s['net'])}"
          + (f"（另有{s['pool_wins']}次奖池大奖未计入）" if s["pool_wins"] else ""))
    print(f"✅ 号码分布统计已更新（统计 {stats['total_draws']} 期）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

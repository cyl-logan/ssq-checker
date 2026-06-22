"""CLI entrypoint: python -m ssq_checker [--reds 01 02 ...] [--blue 07]"""
from __future__ import annotations

import argparse
import sys

from .checker import check_prize, format_report, normalize
from .fetcher import fetch_latest_draw


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check SSQ draw against your fixed numbers.")
    p.add_argument("--reds", nargs=6, default=["01", "02", "03", "04", "08", "09"],
                   help="6 red balls (1-33). Default: Logan's numbers.")
    p.add_argument("--blue", default="07",
                   help="1 blue ball (1-16). Default: 07.")
    p.add_argument("--json", action="store_true", help="Output JSON instead of formatted report.")
    args = p.parse_args(argv)

    user_reds = normalize(args.reds)
    user_blue = f"{int(args.blue):02d}"

    try:
        draw = fetch_latest_draw()
    except Exception as e:
        print(f"❌ 拉取双色球开奖数据失败：{e}", file=sys.stderr)
        return 2

    result = check_prize(user_reds, user_blue, draw)

    if args.json:
        import json as _json
        print(_json.dumps({
            "issue": draw.issue, "date": draw.date,
            "draw_reds": draw.reds_sorted, "draw_blue": draw.blue,
            "user_reds": user_reds, "user_blue": user_blue,
            "red_hits": result.red_hits, "red_matched": result.red_matched,
            "blue_hit": result.blue_hit,
            "tier": result.tier, "amount": result.amount,
        }, ensure_ascii=False, indent=2))
    else:
        print(format_report(draw, user_reds, user_blue, result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

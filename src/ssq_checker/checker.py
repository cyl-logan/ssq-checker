"""Compare a user's fixed numbers against an SSQ draw and report the prize."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from .fetcher import Draw


# Official SSQ prize table (single-bet only; user's 6+1 ticket = one bet).
# (red_hits, blue_hit) -> (tier_label, fixed_amount_rmb or None for jackpot/pool)
PRIZE_TABLE = {
    (6, True):  ("一等奖", None),       # jackpot, pool-based
    (6, False): ("二等奖", None),       # pool-based
    (5, True):  ("三等奖", 3000),
    (5, False): ("四等奖", 200),
    (4, True):  ("四等奖", 200),
    (4, False): ("五等奖", 10),
    (3, True):  ("五等奖", 10),
    (2, True):  ("六等奖", 5),
    (1, True):  ("六等奖", 5),
    (0, True):  ("六等奖", 5),
}


@dataclass(frozen=True)
class PrizeResult:
    red_hits: int
    red_matched: List[str]   # which red balls matched, ascending int order
    blue_hit: bool
    tier: str | None         # e.g. "五等奖", or None for no prize
    amount: int | None       # fixed amount in RMB, None if pool-based or no prize


def check_prize(
    user_reds: List[str],
    user_blue: str,
    draw: Draw,
) -> PrizeResult:
    """Check user's numbers against a draw.

    Numbers should be zero-padded 2-char strings ("01".."33" reds, "01".."16" blue).
    """
    user_red_set: Set[str] = set(user_reds)
    draw_red_set: Set[str] = set(draw.reds)
    matched = sorted(user_red_set & draw_red_set, key=int)
    red_hits = len(matched)
    blue_hit = user_blue == draw.blue

    prize = PRIZE_TABLE.get((red_hits, blue_hit))
    if prize is None:
        return PrizeResult(red_hits, matched, blue_hit, tier=None, amount=None)
    tier, amount = prize
    return PrizeResult(red_hits, matched, blue_hit, tier=tier, amount=amount)


def normalize(numbers: List[str | int]) -> List[str]:
    """Normalize ball numbers to zero-padded 2-char strings."""
    return [f"{int(n):02d}" for n in numbers]


def format_report(draw: Draw, user_reds: List[str], user_blue: str, result: PrizeResult) -> str:
    """Format the report message exactly as the cron job used to produce."""
    reds_disp = " ".join(draw.reds_sorted)
    date_short = draw.date[5:].replace("-", "月") + "日"  # "06-21" -> "06月21日"

    lines = [
        f"🎱 双色球第{draw.issue}期开奖（{date_short}）",
        "",
        f"🔴 红球：{reds_disp}",
        f"🔵 蓝球：{draw.blue}",
        "",
        f"你的号码：🔴 {' '.join(user_reds)}  🔵 {user_blue}",
        f"红球命中：{result.red_hits}个" + (f"（{' '.join(result.red_matched)}）" if result.red_matched else ""),
        f"蓝球命中：{'✅' if result.blue_hit else '❌'}",
        "",
    ]

    if result.tier is None:
        lines.append("中奖结论：未中奖")
    else:
        amt = "奖池/浮动" if result.amount is None else f"¥{result.amount}"
        lines.append(f"中奖结论：🎉 {result.tier}（{amt}）")

    return "\n".join(lines)

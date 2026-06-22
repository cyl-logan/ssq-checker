"""Compare a user's fixed numbers against an SSQ draw and report the prize."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Set, Tuple

from .fetcher import Draw

if TYPE_CHECKING:
    from .bets import Bet


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


def bet_winnings(result: PrizeResult, multiplier: int) -> int | None:
    """Winnings for a bet at the given multiplier, in RMB.

    Returns 0 for no prize, a positive int for fixed-amount tiers, and None for
    pool-based tiers (一/二等奖) whose value can't be known here.
    """
    if result.tier is None:
        return 0
    if result.amount is None:
        return None
    return result.amount * multiplier


def format_bets_report(draw: Draw, results: List[Tuple["Bet", PrizeResult]]) -> str:
    """Format a report covering every bet in the user's table, with totals."""
    reds_disp = " ".join(draw.reds_sorted)
    date_short = draw.date[5:].replace("-", "月") + "日"

    lines = [
        f"🎱 双色球第{draw.issue}期开奖（{date_short}）",
        "",
        f"🔴 红球：{reds_disp}",
        f"🔵 蓝球：{draw.blue}",
        "",
    ]

    total_cost = sum(bet.cost for bet, _ in results)
    lines.append(f"你的投注（共{len(results)}注，总投入 ¥{total_cost}）：")
    lines.append("")

    total_won = 0
    has_pool_win = False
    circled = "①②③④⑤⑥⑦⑧⑨⑩"

    for idx, (bet, result) in enumerate(results):
        marker = circled[idx] if idx < len(circled) else f"{idx + 1}."
        won = bet_winnings(result, bet.multiplier)
        hit_note = f"（{' '.join(result.red_matched)}）" if result.red_matched else ""
        lines.append(
            f"{marker} 🔴 {' '.join(bet.reds)}  🔵 {bet.blue}  ×{bet.multiplier}倍（¥{bet.cost}）"
        )
        status = (
            f"红球{result.red_hits}个{hit_note}｜蓝球{'✅' if result.blue_hit else '❌'} → "
        )
        if result.tier is None:
            status += "未中奖"
        elif won is None:
            has_pool_win = True
            status += f"🎉 {result.tier}（奖池/浮动 ×{bet.multiplier}倍）"
        else:
            total_won += won
            mult_note = f" ×{bet.multiplier} = ¥{won}" if bet.multiplier > 1 else ""
            status += f"🎉 {result.tier}（¥{result.amount}{mult_note}）"
        lines.append(f"   {status}")

    lines.append("")
    won_disp = f"¥{total_won}"
    if has_pool_win:
        won_disp += "（另有奖池/浮动大奖，金额以官方为准）"
    lines.append(f"总中奖：{won_disp}")

    return "\n".join(lines)

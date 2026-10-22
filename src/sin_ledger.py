"""麦门罪恶引擎：把麦当劳订单翻译成教廷术语。

核心概念：
- 罪恶点(Sin Point)  = 千卡 x 0.1
- 赎罪工时            = 千卡 x 3 分钟（步行消耗）
- 罪级                = 按累计罪恶点划分
- 赦免                = 卡包内真实优惠券可抵扣赎罪工时
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .nutrition_table import Food, NutritionTable

# --------------------------------------------------------------------- #
# 常量：罪律
# --------------------------------------------------------------------- #
SIN_PER_KCAL = 0.1           # 每千卡 = 0.1 罪恶点
WALK_MIN_PER_KCAL = 3        # 每千卡 = 步行赎罪 3 分钟

LATE_NIGHT_START = 22        # 22:00 之后
LATE_NIGHT_END = 5           # 05:00 之前
LATE_NIGHT_FACTOR = 2.0      # 深夜下单，罪加一等
FRIDAY_FACTOR = 1.2          # 周末前夜的放纵
TINY_ORDER_THRESHOLD = 5.0   # 实付 <= 5 元
TINY_ORDER_FACTOR = 0.5      # 小罪，酌情减轻
FEAST_THRESHOLD = 100.0      # 实付 >= 100 元
FEAST_FACTOR = 1.5           # 暴食罪
GREED_QTY = 3                # 同款 >= 3 件
GREED_FACTOR = 1.3           # 贪
DIET_COLA_FACTOR = 0.9       # 选择无糖，将功补过

ABSOLVE_RATE = 0.05          # 每张赦免券减免 5% 赎罪工时
ABSOLVE_CAP = 0.40           # 赦免上限 40%

# 罪级体系：(下限罪恶点, 称号, 罪级描述)
SIN_RANKS = [
    (500, "逐出麦籍", "死罪"),
    (200, "麦门叛徒", "大罪"),
    (50, "黑袍常客", "中罪"),
    (0, "白衣罪徒", "小罪"),
]

_TIME_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def parse_time(value: str) -> datetime | None:
    m = _TIME_RE.search(value or "")
    if not m:
        return None
    return datetime(*(int(g) for g in m.groups()))


# --------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------- #
@dataclass
class SinItem:
    """订单中的单个餐品条目。"""

    name: str
    quantity: int
    kcal: int
    matched: bool
    nutrition: Food | None = None


@dataclass
class SinCase:
    """一桩罪案 = 一笔历史订单。"""

    order_id: str
    time_text: str
    store_name: str
    amount: float
    items: list[SinItem] = field(default_factory=list)
    kcal: int = 0
    base_sin: float = 0.0
    final_sin: float = 0.0
    modifiers: list[str] = field(default_factory=list)

    @property
    def time(self) -> datetime | None:
        return parse_time(self.time_text)


@dataclass
class Verdict:
    """总判决。"""

    cases: list[SinCase]
    total_kcal: int = 0
    total_amount: float = 0.0
    total_sin: float = 0.0
    walk_minutes: int = 0
    rank: str = ""
    rank_desc: str = ""
    # 赦免
    coupons: list[dict] = field(default_factory=list)
    absolved_minutes: int = 0
    final_walk_minutes: int = 0
    # 统计
    top_food: tuple[str, int] | None = None      # (餐品名, 次数)
    worst_case: SinCase | None = None            # 罪孽最重的一单
    late_night_ratio: float = 0.0                # 深夜犯罪率


# --------------------------------------------------------------------- #
# 判罪逻辑
# --------------------------------------------------------------------- #
def build_case(order: dict, table: NutritionTable) -> SinCase:
    items: list[SinItem] = []
    for prod in order.get("orderProductList") or []:
        name = str(prod.get("productName") or "")
        qty = int(prod.get("quantity") or 1)
        unit_kcal, food = table.kcal_of(name)
        items.append(
            SinItem(name=name, quantity=qty, kcal=unit_kcal * qty, matched=food is not None, nutrition=food)
        )

    case = SinCase(
        order_id=str(order.get("orderId") or ""),
        time_text=str(order.get("createTime") or ""),
        store_name=str(order.get("storeName") or "未知门店"),
        amount=float(order.get("realTotalAmount") or 0),
        items=items,
    )
    case.kcal = sum(i.kcal for i in items)
    case.base_sin = round(case.kcal * SIN_PER_KCAL, 2)

    # ---- 量刑 ----
    factor = 1.0
    dt = case.time
    if dt is not None:
        hour = dt.hour
        if hour >= LATE_NIGHT_START or hour < LATE_NIGHT_END:
            factor *= LATE_NIGHT_FACTOR
            case.modifiers.append("深夜下单，罪加一等 (x2)")
        if dt.weekday() == 4:  # 周五
            factor *= FRIDAY_FACTOR
            case.modifiers.append("周五综合征，周末前夜的放纵 (x1.2)")

    if case.amount <= TINY_ORDER_THRESHOLD and case.amount > 0:
        factor *= TINY_ORDER_FACTOR
        case.modifiers.append("金额过小，酌情减轻 (x0.5)")
    elif case.amount >= FEAST_THRESHOLD:
        factor *= FEAST_FACTOR
        case.modifiers.append("单人暴食罪 (x1.5)")

    names = " ".join(i.name for i in items)
    if "无糖" in names:
        factor *= DIET_COLA_FACTOR
        case.modifiers.append("选择无糖，将功补过 (x0.9)")
    if any(i.quantity >= GREED_QTY for i in items):
        factor *= GREED_FACTOR
        case.modifiers.append("同款三件起，贪 (x1.3)")

    case.final_sin = round(case.base_sin * factor, 2)
    return case


def parse_coupons(coupon_text: str) -> list[dict]:
    """尽力解析 query-my-coupons 的文本返回，提取券名与有效期。

    形如::

        ## 11.9元麦辣鸡腿堡
        - **有效期**: 2026-10-19 10:30-2026-10-23 23:59 ...
    """
    coupons: list[dict] = []
    if not coupon_text:
        return coupons
    name: str | None = None
    for line in coupon_text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            name = line[3:].strip()
        elif line.startswith("- **有效期**") and name:
            m = re.search(r"有效期\*\*:\s*([0-9\- :]+)", line)
            expire = m.group(1).strip() if m else ""
            coupons.append({"name": name, "expire": expire})
            name = None
    return coupons


def judge(orders: list[dict], table: NutritionTable, coupons: list[dict] | None = None,
          now: datetime | None = None) -> Verdict:
    """对全部历史订单进行终审判决。"""
    now = now or datetime.now()
    cases = [build_case(o, table) for o in orders]
    cases.sort(key=lambda c: c.time_text)

    verdict = Verdict(cases=cases, coupons=coupons or [])
    verdict.total_kcal = sum(c.kcal for c in cases)
    verdict.total_amount = round(sum(c.amount for c in cases), 2)
    verdict.total_sin = round(sum(c.final_sin for c in cases), 2)
    verdict.walk_minutes = int(round(verdict.total_kcal * WALK_MIN_PER_KCAL))

    for threshold, title, desc in SIN_RANKS:
        if verdict.total_sin >= threshold:
            verdict.rank, verdict.rank_desc = title, desc
            break

    # ---- 赦免：每张真实优惠券抵扣 5% 赎罪工时，上限 40% ----
    if verdict.coupons and verdict.walk_minutes > 0:
        rate = min(ABSOLVE_RATE * len(verdict.coupons), ABSOLVE_CAP)
        verdict.absolved_minutes = int(round(verdict.walk_minutes * rate))
        verdict.final_walk_minutes = verdict.walk_minutes - verdict.absolved_minutes
    else:
        verdict.final_walk_minutes = verdict.walk_minutes

    # ---- 统计 ----
    if cases:
        verdict.worst_case = max(cases, key=lambda c: c.final_sin)
        counter: dict[str, int] = {}
        for c in cases:
            for i in c.items:
                counter[i.name] = counter.get(i.name, 0) + i.quantity
        if counter:
            name = max(counter, key=lambda k: counter[k])
            verdict.top_food = (name, counter[name])
        night = sum(1 for c in cases if c.time and (c.time.hour >= LATE_NIGHT_START or c.time.hour < LATE_NIGHT_END))
        verdict.late_night_ratio = round(night / len(cases), 3)
    return verdict


def format_walk(minutes: int) -> str:
    """把赎罪分钟数格式化为人类可读形式。"""
    if minutes <= 0:
        return "0 分钟"
    if minutes < 60:
        return "{} 分钟".format(minutes)
    hours = minutes / 60.0
    if hours < 24:
        return "约 {:.1f} 小时".format(hours)
    return "约 {:.1f} 天".format(hours / 24.0)

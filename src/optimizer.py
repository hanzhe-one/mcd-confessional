"""券 + 套餐组合优化器（确定性算法，位掩码 DP）。

问题定义
--------
用户有一组"想要的餐品"（demand），手里有若干优惠券。每张券可以覆盖一个子集的餐品
并给出一个更低的打包价。目标：把需求全部满足的前提下，**总价最低**。

这是一个带券约束的集合划分问题（set partition），规模小（单次点餐需求通常 <12 件），
用位掩码 DP 精确求解：

    dp[mask] = 覆盖 mask 这些需求的最小花费
    dp[mask] = min(
        单买任意一个未覆盖项 + dp[mask | bit],          # 原价路径
        用任意一张券覆盖一个可行子集 + dp[mask | sub],   # 券路径
    )

所有金额均为确定性计算，同一输入必得同一输出，可复现、可测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

# 需求件数上限：3^14 ≈ 478 万次转移，毫秒级；超过则退化到保守策略
MAX_UNITS = 14


@dataclass
class OrderItem:
    """一个可购买的商品（菜单项）。"""

    code: str
    name: str
    price: float          # 单价（元）
    kcal: int = 0


@dataclass
class Coupon:
    """一张优惠券。

    kind:
      - "discount": 指定商品的券后价（price 为券后单价），target 为商品名关键词
      - "threshold": 满 threshold 元减 discount 元，target 为 None 表示全场通用
    """

    cid: str
    name: str
    kind: str
    price: float = 0.0
    target: str = ""
    threshold: float = 0.0
    discount: float = 0.0
    channel: str = "any"      # pickup / delivery / any
    max_qty: int = 99         # 该券最多覆盖几份


@dataclass
class PlanLine:
    """方案中的一行。"""

    desc: str                 # 人类可读描述
    kind: str                 # "single" / "coupon"
    amount: float             # 该行金额
    coupon_name: str = ""
    codes: tuple[str, ...] = ()


@dataclass
class Plan:
    """一个完整的购买方案。"""

    lines: list[PlanLine] = field(default_factory=list)
    total: float = 0.0
    list_total: float = 0.0   # 全部原价单买的金额
    coupon_names: list[str] = field(default_factory=list)

    @property
    def saved(self) -> float:
        return round(self.list_total - self.total, 2)

    @property
    def saved_pct(self) -> float:
        if self.list_total <= 0:
            return 0.0
        return round(self.saved / self.list_total * 100, 1)

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "list_total": round(self.list_total, 2),
            "saved": self.saved,
            "saved_pct": self.saved_pct,
            "coupons": self.coupon_names,
            "lines": [
                {
                    "desc": l.desc,
                    "kind": l.kind,
                    "amount": round(l.amount, 2),
                    "coupon": l.coupon_name,
                }
                for l in self.lines
            ],
        }


def _expand_units(items: list[OrderItem], qty: list[int]) -> list[OrderItem]:
    """把 (商品, 数量) 展开成一个个独立需求单元。"""
    units: list[OrderItem] = []
    for item, q in zip(items, qty):
        units.extend([item] * max(0, int(q)))
    return units


def same_food(coupon_target: str, product_name: str) -> bool:
    """判断券面写的商品名与订单里的商品名是否指同一样东西。

    麦当劳的券名和菜单名经常差一个字：券叫「麦辣鸡腿堡」，菜单叫「麦辣鸡腿汉堡」。
    直接子串匹配会全部落空——后果是券池看起来是空的，审计永远算出「0 元可省」。
    这里先做归一化（去掉「汉堡」的「汉」、「堡/汉堡」互换），再退回子串双向包含。
    """
    if not coupon_target or not product_name:
        return False
    a = coupon_target.replace("汉堡", "堡")
    b = product_name.replace("汉堡", "堡")
    return a in b or b in a


def _coupon_covers(coupon: Coupon, subset: list[OrderItem]) -> tuple[bool, float]:
    """判断一张券能否覆盖给定子集，返回 (可行, 该子集用券后的金额)。"""
    if not subset:
        return False, 0.0

    if coupon.kind == "discount":
        # 单品券：子集内每一件都必须是券适用的商品，且数量不超过限购
        if len(subset) > coupon.max_qty:
            return False, 0.0
        if coupon.target and not all(same_food(coupon.target, u.name) for u in subset):
            return False, 0.0
        return True, round(coupon.price * len(subset), 2)

    if coupon.kind == "threshold":
        # 满减券：子集原价合计达到门槛
        if coupon.target and not all(same_food(coupon.target, u.name) for u in subset):
            return False, 0.0
        amount = round(sum(u.price for u in subset), 2)
        if amount + 1e-9 < coupon.threshold:
            return False, 0.0
        return True, round(max(amount - coupon.discount, 0.0), 2)

    return False, 0.0


def optimize(
    items: list[OrderItem],
    qty: list[int],
    coupons: list[Coupon] | None = None,
    channel: str = "pickup",
) -> Plan:
    """求解最小花费方案。

    items / qty 一一对应；coupons 为可用券池（会按 channel 过滤）。
    需求件数超过 MAX_UNITS 时退化为"逐件单买"，保证永不出错。
    """
    coupons = [c for c in (coupons or []) if c.channel in ("any", channel)]
    units = _expand_units(items, qty)

    plan = Plan()
    plan.list_total = round(sum(u.price for u in units), 2)

    if not units:
        plan.total = 0.0
        return plan

    if len(units) > MAX_UNITS:
        plan.lines = [PlanLine(desc="{} x1".format(u.name), kind="single", amount=u.price, codes=(u.code,)) for u in units]
        plan.total = plan.list_total
        return plan

    n = len(units)
    full = (1 << n) - 1

    # 预处理：每个券 × 每个子集 的可行性
    coupon_opts: list[tuple[int, Coupon, float]] = []  # (submask, coupon, amount)
    for coupon in coupons:
        for size in range(1, min(coupon.max_qty, n) + 1):
            for idxs in combinations(range(n), size):
                subset = [units[i] for i in idxs]
                ok, amount = _coupon_covers(coupon, subset)
                if ok:
                    mask = 0
                    for i in idxs:
                        mask |= 1 << i
                    coupon_opts.append((mask, coupon, amount))

    # 满减券允许覆盖任意子集，可能数量爆炸；按 mask 去重保留最便宜的那张
    best_coupon_for_mask: dict[int, tuple[Coupon, float]] = {}
    for mask, coupon, amount in coupon_opts:
        cur = best_coupon_for_mask.get(mask)
        if cur is None or amount < cur[1]:
            best_coupon_for_mask[mask] = (coupon, amount)

    INF = float("inf")
    # 正向 DP：从 mask=0（什么都没买）出发，直到 full（需求全部满足）
    dp2 = [INF] * (1 << n)
    choice2: list[tuple | None] = [None] * (1 << n)
    dp2[0] = 0.0
    for mask in range(0, full + 1):
        if dp2[mask] == INF:
            continue
        base = dp2[mask]
        for i in range(n):
            if mask & (1 << i):
                continue
            nmask = mask | (1 << i)
            cost = base + units[i].price
            if cost < dp2[nmask]:
                dp2[nmask] = cost
                choice2[nmask] = ("single", i, None, units[i].price, mask)
        for sub, (coupon, amount) in best_coupon_for_mask.items():
            if sub & mask:
                continue
            nmask = mask | sub
            cost = base + amount
            if cost < dp2[nmask]:
                dp2[nmask] = cost
                choice2[nmask] = ("coupon", sub, coupon, amount, mask)

    plan.total = round(dp2[full], 2)
    lines_rev: list[PlanLine] = []
    mask = full
    while mask:
        step = choice2[mask]
        if step is None:
            break
        kind, payload, coupon, amount, prev = step
        if kind == "single":
            u = units[payload]
            lines_rev.append(PlanLine(desc="{} x1".format(u.name), kind="single", amount=u.price, codes=(u.code,)))
        else:
            idxs = [i for i in range(n) if payload & (1 << i)]
            names = [units[i].name for i in idxs]
            desc = " + ".join(names)
            lines_rev.append(
                PlanLine(
                    desc="{}（用券：{}）".format(desc, coupon.name),
                    kind="coupon",
                    amount=amount,
                    coupon_name=coupon.name,
                    codes=tuple(units[i].code for i in idxs),
                )
            )
            if coupon.name not in plan.coupon_names:
                plan.coupon_names.append(coupon.name)
        mask = prev

    plan.lines = list(reversed(lines_rev))
    return plan


def brute_force_best(
    items: list[OrderItem],
    qty: list[int],
    coupons: list[Coupon] | None = None,
    channel: str = "pickup",
) -> float:
    """暴力枚举所有划分方式，仅用于自测对拍（n <= 8）。"""
    coupons = [c for c in (coupons or []) if c.channel in ("any", channel)]
    units = _expand_units(items, qty)
    n = len(units)
    if n == 0:
        return 0.0
    full = (1 << n) - 1

    from functools import lru_cache

    @lru_cache(maxsize=None)
    def best(mask: int) -> float:
        if mask == full:
            return 0.0
        # 单买第一件未覆盖的
        for i in range(n):
            if not (mask & (1 << i)):
                res = units[i].price + best(mask | (1 << i))
                break
        # 所有包含这件商品的券子集
        for coupon in coupons:
            for size in range(1, min(coupon.max_qty, n) + 1):
                for idxs in combinations(range(n), size):
                    if not any(not (mask & (1 << i)) for i in idxs):
                        continue
                    if mask & sum(1 << i for i in idxs):
                        continue
                    ok, amount = _coupon_covers(coupon, [units[i] for i in idxs])
                    if ok:
                        m2 = mask | sum(1 << i for i in idxs)
                        res = min(res, amount + best(m2))
        return res

    return round(best(0), 2)

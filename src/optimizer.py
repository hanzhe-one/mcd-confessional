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

    uses:
      这张券能被使用几次。麦当劳卡包里的券几乎都是**一次性**的（券面 totalCount=1），
      所以默认 1。把它当成「一份需求可以用券覆盖多次」会让亏损金额虚高——
      买 2 个汉堡、手里 1 张券，正确结果是「1 个用券 + 1 个原价」，
      而不是「2 个都用券价」。
    max_qty:
      单次使用最多覆盖几份。**只对 discount 券有意义**：大多数单品券只抵 1 份，
      所以默认 1；「中薯买一送一」这类才显式写 2。
      满减券看的是整单金额是否达门槛，天然要覆盖多件，不受此限制。
    """

    cid: str
    name: str
    kind: str
    price: float = 0.0
    target: str = ""
    threshold: float = 0.0
    discount: float = 0.0
    channel: str = "any"      # pickup / delivery / any
    max_qty: int = 1          # 单次使用最多覆盖几份（仅 discount 券）
    uses: int = 1             # 这张券总共能用几次


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


def cover_limit(coupon: Coupon, n: int) -> int:
    """这张券单次最多覆盖几件需求。

    满减券看的是整单金额是否达到门槛，天然要覆盖多件，不受 max_qty 限制；
    单品券默认只抵 1 件，「买一送一」这类才允许覆盖 2 件。
    """
    if coupon.kind == "threshold":
        return n
    return max(1, min(coupon.max_qty, n))


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

    # 每张券最多能在这单里被用几次：券本身的使用次数上限，且不可能超过需求件数
    caps = [max(0, min(c.uses, n)) for c in coupons]

    # 预处理：每张券 × 每个子集 的可行性。
    # 按 (子集, 券) 去重保留最便宜的一行——同一张券覆盖同一个子集只有一种价钱。
    best_for: dict[tuple[int, int], float] = {}
    for ci, coupon in enumerate(coupons):
        if caps[ci] <= 0:
            continue
        for size in range(1, cover_limit(coupon, n) + 1):
            for idxs in combinations(range(n), size):
                subset = [units[i] for i in idxs]
                ok, amount = _coupon_covers(coupon, subset)
                if not ok:
                    continue
                mask = 0
                for i in idxs:
                    mask |= 1 << i
                key = (mask, ci)
                if key not in best_for or amount < best_for[key]:
                    best_for[key] = amount

    # 按子集归组，DP 时逐个子集扫一遍即可
    opts_by_mask: dict[int, list[tuple[int, float]]] = {}
    for (mask, ci), amount in best_for.items():
        opts_by_mask.setdefault(mask, []).append((ci, amount))

    # 已用券次数编码：base 进制，每一位是某张券用掉的次数。
    # 这是「券只能用一次」的落地方式——用过的券不能再覆盖别的子集。
    strides: list[int] = []
    stride = 1
    for cap in caps:
        strides.append(stride)
        stride *= (cap + 1)
    total_codes = stride

    INF = float("inf")

    def code_of(counts: list[int]) -> int:
        return sum(c * s for c, s in zip(counts, strides))

    # 正向 DP：状态 = (已满足的需求掩码, 各券已用次数)
    # dp[mask][code] = 最小花费；choice 记录 (前一状态, 动作)，用于回溯
    dp: list[dict[int, float]] = [dict() for _ in range(1 << n)]
    choice: list[dict[int, tuple]] = [dict() for _ in range(1 << n)]
    dp[0][0] = 0.0

    for mask in range(0, full + 1):
        if not dp[mask]:
            continue
        # 快照：本轮写入的目标状态属于更大的 mask，不会回写到当前 mask
        for code, base_cost in list(dp[mask].items()):
            counts = [(code // s) % (cap + 1) for s, cap in zip(strides, caps)]

            for i in range(n):
                if mask & (1 << i):
                    continue
                nmask = mask | (1 << i)
                cost = base_cost + units[i].price
                cur = dp[nmask].get(code)
                if cur is None or cost < cur:
                    dp[nmask][code] = cost
                    choice[nmask][code] = ("single", i, None, units[i].price, mask, code)

            for sub, entries in opts_by_mask.items():
                if sub & mask:
                    continue
                nmask = mask | sub
                for ci, amount in entries:
                    if counts[ci] >= caps[ci]:
                        continue
                    ncode = code + strides[ci]
                    cost = base_cost + amount
                    cur = dp[nmask].get(ncode)
                    if cur is None or cost < cur:
                        dp[nmask][ncode] = cost
                        choice[nmask][ncode] = ("coupon", sub, coupons[ci], amount, mask, code)

    final_code = min(dp[full], key=lambda c: dp[full][c])
    plan.total = round(dp[full][final_code], 2)

    # 回溯：从 (full, final_code) 倒推每一步
    lines_rev: list[PlanLine] = []
    mask, code = full, final_code
    while mask:
        step = choice[mask].get(code)
        if step is None:
            break
        kind, payload, coupon, amount, pmask, pcode = step
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
        mask, code = pmask, pcode

    plan.lines = list(reversed(lines_rev))
    return plan


def brute_force_best(
    items: list[OrderItem],
    qty: list[int],
    coupons: list[Coupon] | None = None,
    channel: str = "pickup",
) -> float:
    """暴力枚举所有划分方式，仅用于自测对拍（n <= 8）。

    与 optimize() 使用同一套规则：券可用次数受 Coupon.uses 限制。
    这里用显式递归枚举「剩下的需求怎么分配」，不做记忆化——状态里带着
    各券已用次数，记忆化收益不抵复杂度，规模本来就只有 n <= 8。
    """
    coupons = [c for c in (coupons or []) if c.channel in ("any", channel)]
    units = _expand_units(items, qty)
    n = len(units)
    if n == 0:
        return 0.0

    caps = [max(0, min(c.uses, n)) for c in coupons]
    INF = float("inf")

    def best(mask: int, used: tuple[int, ...]) -> float:
        if mask == (1 << n) - 1:
            return 0.0

        res = INF
        # 单买第一件未覆盖的
        for i in range(n):
            if not (mask & (1 << i)):
                res = units[i].price + best(mask | (1 << i), used)
                break

        # 用一张还有剩余次数的券覆盖一个包含未满足需求的子集
        for ci, coupon in enumerate(coupons):
            if used[ci] >= caps[ci]:
                continue
            for size in range(1, cover_limit(coupon, n) + 1):
                for idxs in combinations(range(n), size):
                    sub = sum(1 << i for i in idxs)
                    if mask & sub:
                        continue
                    ok, amount = _coupon_covers(coupon, [units[i] for i in idxs])
                    if not ok:
                        continue
                    nused = list(used)
                    nused[ci] += 1
                    res = min(res, amount + best(mask | sub, tuple(nused)))
        return res

    return round(best(0, tuple([0] * len(coupons))), 2)

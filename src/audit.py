"""消费审计引擎：每笔订单「本该花多少」，以及差额到底亏在哪。

审计口径（全部可复现）
----------------------
- 菜单价合计 list_total：按当前菜单价重算订单里的餐品（不含任何优惠）
- 理论最优 optimal：把订单里的餐品丢进券组合优化器，用**当前券池**求最低到手价
- 亏损 gap = 实付 - 理论最优（>0 即"当时还能更便宜"）

归因（causes）
-------------
- full_price      全价买单，一张券都没用
- suboptimal      用了优惠，但没用到最优组合（券没用到位 / 凑单不划算）
- spec_loss       规格不划算（同品类里单价热量比更差的规格）
- clean           这一单已经等于或低于理论最优，无可指摘
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .nutrition_table import NutritionTable
from .optimizer import Coupon, OrderItem, Plan, optimize


@dataclass
class BasketItem:
    name: str
    qty: int
    unit_price: float
    kcal: int


@dataclass
class AuditCase:
    """一笔订单的审计结论。"""

    order_id: str
    time_text: str
    store_name: str
    paid: float
    basket: list[BasketItem] = field(default_factory=list)
    list_total: float = 0.0
    optimal: float = 0.0
    gap: float = 0.0
    saved_then: float = 0.0        # 当时已经省下的（菜单价 - 实付）
    causes: list[str] = field(default_factory=list)
    plan: Plan | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def kcal(self) -> int:
        return sum(i.kcal * i.qty for i in self.basket)

    @property
    def cause_text(self) -> str:
        mapping = {
            "full_price": "全价买单，未使用任何优惠",
            "suboptimal": "用了优惠，但未用到最优组合",
            "spec_loss": "规格选择不划算",
            "clean": "无可指摘",
        }
        return "；".join(mapping.get(c, c) for c in self.causes) or "—"


@dataclass
class AuditSummary:
    cases: list[AuditCase] = field(default_factory=list)
    total_paid: float = 0.0
    total_optimal: float = 0.0
    total_gap: float = 0.0
    total_kcal: int = 0
    # 归因分布（金额）
    by_cause: dict[str, float] = field(default_factory=dict)
    worst: AuditCase | None = None
    clean_count: int = 0
    gap_rate: float = 0.0          # 亏损占实付比例


def _kcal_of(table: NutritionTable, name: str) -> int:
    kcal, _ = table.kcal_of(name)
    return kcal


def audit_order(
    order: dict,
    menu: dict[str, float],
    table: NutritionTable,
    coupons: list[Coupon] | None = None,
    channel: str = "pickup",
) -> AuditCase:
    """审计单笔订单。菜单价为 None 的餐品按订单实付比例回填。"""
    products = order.get("orderProductList") or []
    paid = float(order.get("realTotalAmount") or 0)

    basket: list[BasketItem] = []
    unknown_value = 0.0
    known_total = 0.0

    for p in products:
        name = str(p.get("productName") or "")
        qty = int(p.get("quantity") or 1)
        price = menu.get(name)
        if price is None:
            price = menu.get(_normalize_name(name))
        if price is None:
            # 菜单里没有这个餐品：先记 0，稍后按比例回填
            basket.append(BasketItem(name=name, qty=qty, unit_price=0.0, kcal=_kcal_of(table, name)))
            unknown_value += qty
        else:
            basket.append(BasketItem(name=name, qty=qty, unit_price=float(price), kcal=_kcal_of(table, name)))
            known_total += float(price) * qty

    # 未知餐品：按实付均摊回填（保守，避免虚高亏损）
    if unknown_value > 0:
        remainder = max(paid - known_total, 0.0)
        per_unit = round(remainder / unknown_value, 2) if unknown_value else 0.0
        for item in basket:
            if item.unit_price == 0.0:
                item.unit_price = per_unit
                known_total += per_unit * item.qty

    case = AuditCase(
        order_id=str(order.get("orderId") or ""),
        time_text=str(order.get("createTime") or ""),
        store_name=str(order.get("storeName") or "未知门店"),
        paid=round(paid, 2),
        basket=basket,
    )
    case.list_total = round(sum(i.unit_price * i.qty for i in basket), 2)

    # 理论最优：把订单餐品丢进券优化器
    items = [OrderItem(code=str(idx), name=i.name, price=i.unit_price, kcal=i.kcal) for idx, i in enumerate(basket)]
    qty = [i.qty for i in basket]
    plan = optimize(items, qty, coupons, channel=channel)
    case.plan = plan
    case.optimal = round(min(plan.total, case.list_total), 2)
    case.gap = round(max(case.paid - case.optimal, 0.0), 2)
    case.saved_then = round(max(case.list_total - case.paid, 0.0), 2)

    # ---- 归因 ----
    if case.gap <= 0.5:
        case.causes = ["clean"]
    else:
        nearly_full_price = case.list_total > 0 and case.paid >= case.list_total - 0.5
        used_coupon = bool(plan.coupon_names) and plan.total < case.list_total - 0.5
        if nearly_full_price and used_coupon:
            case.causes.append("full_price")
        elif used_coupon:
            case.causes.append("suboptimal")
        elif case.saved_then > 0:
            case.causes.append("suboptimal")
        else:
            case.causes.append("full_price")

        # 规格性价比：同族里有明显更划算的规格
        spec_note = _spec_check(basket, table, menu)
        if spec_note:
            case.causes.append("spec_loss")
            case.notes.append(spec_note)

    if plan.coupon_names:
        case.notes.append("若用当时的券池最优组合：{} 元（可省 {} 元）".format(
            round(plan.total, 2), max(round(case.paid - plan.total, 2), 0.0)))

    return case


def _normalize_name(name: str) -> str:
    return name.translate(str.maketrans("", "", "()（）"))


# 规格族：同名商品的大/中/小份
_SPEC_FAMILIES = [
    ("薯条", ["大薯条", "中薯条", "小薯条", "迷你薯条"]),
    ("可乐", ["可乐大杯", "可乐中杯", "可乐小杯"]),
    ("雪碧", ["雪碧大杯", "雪碧中杯", "雪碧小杯"]),
    ("玉米杯", ["大杯玉米杯", "小杯玉米杯"]),
]


def _spec_check(basket: list[BasketItem], table: NutritionTable, menu: dict[str, float]) -> str | None:
    """检查规格性价比：同族里存在「每元热量」明显更高的规格时给出提示。

    口径：kcal/元 = 该规格热量 ÷ 菜单价。这是纯性价比指标，不涉及健康判断。
    """
    for _family_name, members in _SPEC_FAMILIES:
        chosen = [b for b in basket if _normalize_name(b.name) in members or b.name in members]
        if not chosen:
            continue
        b = chosen[0]
        if b.unit_price <= 0 or b.kcal <= 0:
            continue
        chosen_ratio = b.kcal / b.unit_price

        ratios: list[tuple[str, float]] = []
        for m in members:
            food = table.exact(m)
            price = menu.get(m)
            if food and food.kcal > 0 and price:
                ratios.append((m, food.kcal / float(price)))
        if len(ratios) < 2:
            continue

        best_name, best_ratio = max(ratios, key=lambda x: x[1])
        norm_chosen = _normalize_name(b.name)
        if norm_chosen == best_name:
            continue
        # 只有差距超过 15% 才认为"明显不划算"，避免吹毛求疵
        if best_ratio > chosen_ratio * 1.15:
            return "规格性价比：{} 每元热量 {:.1f} kcal/元，你选的 {} 只有 {:.1f} kcal/元".format(
                best_name, best_ratio, b.name, chosen_ratio)
    return None


def audit_all(
    orders: list[dict],
    menu: dict[str, float],
    table: NutritionTable,
    coupons: list[Coupon] | None = None,
    channel: str = "pickup",
) -> AuditSummary:
    """批量审计并汇总。"""
    summary = AuditSummary()
    for order in orders:
        case = audit_order(order, menu, table, coupons, channel)
        summary.cases.append(case)
        summary.total_paid += case.paid
        summary.total_optimal += case.optimal
        summary.total_gap += case.gap
        summary.total_kcal += case.kcal
        if "clean" in case.causes:
            summary.clean_count += 1
        for cause in case.causes:
            if cause == "clean":
                continue
            summary.by_cause[cause] = round(summary.by_cause.get(cause, 0.0) + case.gap, 2)

    summary.total_paid = round(summary.total_paid, 2)
    summary.total_optimal = round(summary.total_optimal, 2)
    summary.total_gap = round(summary.total_gap, 2)
    if summary.cases:
        summary.worst = max(summary.cases, key=lambda c: c.gap)
    if summary.total_paid > 0:
        summary.gap_rate = round(summary.total_gap / summary.total_paid * 100, 1)
    return summary

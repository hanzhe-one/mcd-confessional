"""优化器自测：与暴力枚举对拍 + 边界用例 + 可复现性。

运行：python -m src.selftest
"""

from __future__ import annotations

import random
import sys

from src.console import harden_stdout
from src.optimizer import Coupon, OrderItem, brute_force_best, optimize

PASS = 0
FAIL = 0


def check(name: str, got, want, tol: float = 0.01) -> None:
    global PASS, FAIL
    ok = (abs(got - want) <= tol) if isinstance(want, (int, float)) and isinstance(got, (int, float)) else (got == want)
    if ok:
        PASS += 1
        print("  PASS  {}".format(name))
    else:
        FAIL += 1
        print("  FAIL  {}  得到 {} 期望 {}".format(name, got, want))


BIG_MAC = OrderItem("1001", "巨无霸", 25.0, 513)
FRIES_M = OrderItem("1002", "中薯条", 12.0, 289)
COLA_M = OrderItem("1003", "可乐(中杯)", 10.0, 147)
PIE = OrderItem("1004", "香芋派", 7.5, 232)


def test_basic() -> None:
    print("\n[1] 基础路径：无券 = 原价")
    plan = optimize([BIG_MAC, FRIES_M], [1, 1], [])
    check("总价", plan.total, 37.0)
    check("原价合计", plan.list_total, 37.0)
    check("节省", plan.saved, 0.0)


def test_discount_coupon() -> None:
    print("\n[2] 单品券：券后价生效")
    c = Coupon("c1", "巨无霸券价 19.9", "discount", price=19.9, target="巨无霸")
    plan = optimize([BIG_MAC, FRIES_M], [1, 1], [c])
    check("总价", plan.total, 31.9)
    check("节省", plan.saved, 5.1)
    check("券名", plan.coupon_names, ["巨无霸券价 19.9"])


def test_threshold_coupon() -> None:
    print("\n[3] 满减券：达门槛才可用")
    c = Coupon("c2", "满35减7", "threshold", threshold=35, discount=7)
    plan = optimize([BIG_MAC, FRIES_M], [1, 1], [c])
    check("总价(37>=35 可用)", plan.total, 30.0)

    plan2 = optimize([COLA_M], [1], [c])
    check("总价(10<35 不可用)", plan2.total, 10.0)


def test_coupon_beats_single() -> None:
    print("\n[4] 券包优于单买：需要正确分配到最优子集")
    # 两张单品券分别覆盖不同商品
    c1 = Coupon("c1", "巨无霸 19.9", "discount", price=19.9, target="巨无霸")
    c2 = Coupon("c2", "中薯 6.9", "discount", price=6.9, target="中薯条")
    plan = optimize([BIG_MAC, FRIES_M, COLA_M], [1, 1, 1], [c1, c2])
    check("总价", plan.total, 36.8)   # 19.9 + 6.9 + 10
    check("用券数", len(plan.coupon_names), 2)


def test_quantity() -> None:
    print("\n[5] 数量处理")
    c = Coupon("c1", "巨无霸 19.9", "discount", price=19.9, target="巨无霸")
    plan = optimize([BIG_MAC], [2], [c])
    check("两份都用券", plan.total, 39.8)
    check("原价", plan.list_total, 50.0)


def test_random_vs_bruteforce() -> None:
    print("\n[6] 随机场景 200 例：DP vs 暴力枚举")
    rng = random.Random(20261022)
    mismatched = 0
    for trial in range(200):
        n_items = rng.randint(1, 4)
        items = []
        qty = []
        for i in range(n_items):
            items.append(
                OrderItem(
                    code="R{}".format(i),
                    name=["巨无霸", "中薯条", "可乐(中杯)", "香芋派", "麦辣鸡腿汉堡"][i % 5],
                    price=round(rng.uniform(5, 30), 1),
                )
            )
            qty.append(rng.randint(1, 2))
        if sum(qty) > 8:
            continue

        coupons = []
        for j in range(rng.randint(0, 3)):
            kind = rng.choice(["discount", "threshold"])
            if kind == "discount":
                coupons.append(
                    Coupon(
                        "r{}".format(j),
                        "随机单品券{}".format(j),
                        "discount",
                        price=round(rng.uniform(3, 20), 1),
                        target=rng.choice(["", "巨无霸", "中薯条", "可乐"]),
                    )
                )
            else:
                coupons.append(
                    Coupon(
                        "r{}".format(j),
                        "随机满减券{}".format(j),
                        "threshold",
                        threshold=round(rng.uniform(10, 60), 1),
                        discount=round(rng.uniform(1, 15), 1),
                    )
                )

        got = optimize(items, qty, coupons).total
        want = brute_force_best(items, qty, coupons)
        if abs(got - want) > 0.01:
            mismatched += 1
            if mismatched <= 3:
                print("    不一致: DP={} 暴力={} items={} coupons={}".format(
                    got, want, [(i.name, q) for i, q in zip(items, qty)], [c.name for c in coupons]))
    check("200 例中有 {} 例不一致".format(mismatched), mismatched, 0)


def test_reproducible() -> None:
    print("\n[7] 可复现性：同输入必同输出")
    c1 = Coupon("c1", "巨无霸 19.9", "discount", price=19.9, target="巨无霸")
    c2 = Coupon("c2", "满35减7", "threshold", threshold=35, discount=7)
    results = [optimize([BIG_MAC, FRIES_M, COLA_M], [1, 1, 1], [c1, c2]).total for _ in range(20)]
    check("20 次结果唯一", len(set(results)), 1)


def test_channel_filter() -> None:
    print("\n[8] 渠道过滤：外送券不用于到店")
    c = Coupon("c1", "仅外送券", "discount", price=1.0, target="巨无霸", channel="delivery")
    plan = optimize([BIG_MAC], [1], [c], channel="pickup")
    check("到店不应用外送券", plan.total, 25.0)


def test_coupon_name_variants() -> None:
    """券面名与菜单名差一个字的真实场景。

    实测：卡包券叫「11.9元麦辣鸡腿堡」，菜单与订单叫「麦辣鸡腿汉堡」。
    严格子串匹配会全部落空，券池看起来是空的，审计永远算出「0 元可省」。
    """
    print("\n[9] 券名与菜单名不一致（真实券面写法）")
    burger = OrderItem("1440", "麦辣鸡腿汉堡", 23.0, 485)
    fries = OrderItem("4810", "薯条", 14.5, 289)
    c = Coupon("live0", "11.9元麦辣鸡腿堡", "discount", price=11.9, target="麦辣鸡腿堡")
    plan = optimize([burger, fries], [1, 1], [c])
    check("券被识别", plan.coupon_names, ["11.9元麦辣鸡腿堡"])
    check("总价 = 券价 + 薯条原价", plan.total, 26.4)

    other = OrderItem("1100", "巨无霸", 26.0, 513)
    plan2 = optimize([other, fries], [1, 1], [c])
    check("不相干的商品不套用该券", plan2.coupon_names, [])


def main() -> int:
    harden_stdout()
    print("=" * 56)
    print("麦门告解室 · 优化器自测")
    print("=" * 56)
    test_basic()
    test_discount_coupon()
    test_threshold_coupon()
    test_coupon_beats_single()
    test_quantity()
    test_random_vs_bruteforce()
    test_reproducible()
    test_channel_filter()
    test_coupon_name_variants()

    print("\n" + "=" * 56)
    print("结果: {} passed, {} failed".format(PASS, FAIL))
    print("=" * 56)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

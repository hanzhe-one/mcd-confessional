"""麦门告解室命令行入口。

命令
----
    python -m src.cli trial               # 完整庭审（虚构档案，无需 Token）
    python -m src.cli trial --live        # 完整庭审（真实订单，需 MCD_MCP_TOKEN）
    python -m src.cli audit               # 只看审计结果（逐单亏损）
    python -m src.cli checkin -m 30       # 赎罪打卡 30 分钟
    python -m src.cli ledger              # 查看罪恶账本
    python -m src.cli demo                # 旧版罪状报告（Markdown + 证书）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audit import audit_all  # noqa: E402
from src.demo_data import DEMO_COUPON_TEXT, DEMO_COUPONS, DEMO_MENU, DEMO_ORDERS  # noqa: E402
from src.mcp_client import MCPClient, MCPError  # noqa: E402
from src.nutrition_table import NutritionTable  # noqa: E402
from src.optimizer import Coupon  # noqa: E402
from src.report import render_certificate_html, render_markdown  # noqa: E402
from src.render_trial import render_trial_html  # noqa: E402
from src.sin_ledger import judge, parse_coupons, parse_time  # noqa: E402
from src.state import DEFAULT_LEDGER_PATH, Ledger  # noqa: E402
from src.trial import Trial  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


def _load_table() -> NutritionTable:
    return NutritionTable.from_baseline()


def _load_data(live: bool) -> tuple[list[dict], dict[str, float], list[Coupon], str, str]:
    """返回 (订单, 菜单价, 券池, 券文本, 数据来源说明)。"""
    if not live:
        return DEMO_ORDERS, DEMO_MENU, DEMO_COUPONS, DEMO_COUPON_TEXT, "内置虚构演示档案（非真实数据）"

    client = MCPClient()
    try:
        client.initialize()
        orders = client.get_orders()
        coupon_text = client.get_coupons_text()
    except MCPError as exc:
        print("[告解室] MCP 调用失败: {}".format(exc), file=sys.stderr)
        print("[告解室] 请设置环境变量 MCD_MCP_TOKEN，或去掉 --live 使用演示数据。", file=sys.stderr)
        raise SystemExit(1)

    return orders, DEMO_MENU, _coupons_from_text(coupon_text), coupon_text, "麦当劳 MCP 真实订单（菜单价为演示快照）"


def _coupons_from_text(text: str) -> list[Coupon]:
    """把卡包券文本尽量转成优化器可用的券（券名为 "11.9元麦辣鸡腿堡" 形式时）。"""
    coupons: list[Coupon] = []
    for idx, item in enumerate(parse_coupons(text)):
        name = item.get("name", "")
        m = re.match(r"([0-9.]+)\s*元\s*(.+)", name)
        if m:
            coupons.append(Coupon(
                cid="live{}".format(idx),
                name=name,
                kind="discount",
                price=float(m.group(1)),
                target=m.group(2).replace("任选2", "").strip(),
            ))
    return coupons


def _stats(orders: list[dict]) -> tuple[float, int]:
    """(深夜订单占比, 时间跨度天数)。"""
    times = [t for t in (parse_time(o.get("createTime", "")) for o in orders) if t]
    if not times:
        return 0.0, 1
    late = sum(1 for t in times if t.hour >= 22 or t.hour < 5)
    span = max((max(times) - min(times)).days, 1)
    return round(late / len(times), 3), span


def cmd_trial(args: argparse.Namespace) -> int:
    orders, menu, coupons, coupon_text, source = _load_data(args.live)
    table = _load_table()
    now = datetime.now()

    summary = audit_all(orders, menu, table, coupons)
    verdict = judge(orders, table, coupons=parse_coupons(coupon_text), now=now)
    late_ratio, span = _stats(orders)
    coupon_used_ratio = sum(1 for c in summary.cases if c.saved_then > 0) / max(len(summary.cases), 1)

    trial = Trial(summary, verdict, now=now, late_night_ratio=late_ratio,
                  coupon_used_ratio=coupon_used_ratio, days_span=span)
    print("=" * 64)
    print("麦门告解室 · 庭审记录　（{}）".format(source))
    print("=" * 64)
    print(trial.run())

    if args.save:
        ledger = Ledger.load(args.ledger)
        record = ledger.add_case(
            store="（{} 单汇总）".format(len(summary.cases)),
            kcal=summary.total_kcal,
            sin=verdict.total_sin,
            paid=summary.total_paid,
            optimal=summary.total_optimal,
            gap=summary.total_gap,
            penance_minutes=trial.result.final_penance,
            verdict=verdict.rank,
        )
        path = ledger.save(args.ledger)
        print("\n[执事] 已登记入账：{}　案号 {}".format(path, record.case_no))

    os.makedirs(OUT_DIR, exist_ok=True)
    cert = os.path.join(OUT_DIR, "confession-certificate.html")
    with open(cert, "w", encoding="utf-8") as fh:
        fh.write(render_certificate_html(verdict, now, audit_summary=summary))

    record = os.path.join(OUT_DIR, "trial-record.html")
    with open(record, "w", encoding="utf-8") as fh:
        fh.write(render_trial_html(trial, now))
    print("[执事] 告解证书：{}".format(cert))
    print("[执事] 庭审记录：{}".format(record))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    orders, menu, coupons, _coupon_text, source = _load_data(args.live)
    table = _load_table()
    summary = audit_all(orders, menu, table, coupons)

    print("=" * 64)
    print("审计结果（{}）".format(source))
    print("=" * 64)
    for case in summary.cases:
        print("\n{}　{}".format(case.time_text, case.store_name))
        print("  实付 {:.2f} 元 ｜ 菜单价 {:.2f} 元 ｜ 理论最优 {:.2f} 元".format(
            case.paid, case.list_total, case.optimal))
        print("  亏损 {:.2f} 元　归因：{}".format(case.gap, case.cause_text))
        for note in case.notes:
            print("  · {}".format(note))
    print("\n" + "-" * 64)
    print("合计实付 {:.2f} 元，理论最优 {:.2f} 元，白扔 {:.2f} 元（{:.1f}%）".format(
        summary.total_paid, summary.total_optimal, summary.total_gap, summary.gap_rate))
    return 0


def cmd_checkin(args: argparse.Namespace) -> int:
    ledger = Ledger.load(args.ledger)
    if not ledger.records:
        print("[执事] 账本还是空的。先说一句「开庭」，审完才有罪可赎。")
        return 0
    ledger.add_checkin(args.minutes, args.note or "")
    ledger.save(args.ledger)
    s = ledger.summary()
    print("[执事] 已登记打卡 {} 分钟{}".format(
        args.minutes, "（{}）".format(args.note) if args.note else ""))
    print("  赎罪进度：{} / {} 分钟（{:.1f}%）".format(s["penance_done"], s["penance_total"], s["done_pct"]))
    print("  尚欠：{} 分钟　连续打卡：{} 天".format(s["outstanding"], s["streak_days"]))
    if s["outstanding"] == 0:
        print("  本席宣布：你的罪，赎完了。下次开庭见。")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    ledger = Ledger.load(args.ledger)
    s = ledger.summary()
    print("=" * 64)
    print("罪恶账本")
    print("=" * 64)
    if not ledger.records:
        print("（空账本）先说一句「开庭」。")
        return 0
    print("案件数 {}　累计罪恶点 {:.2f}　累计热量 {} 千卡".format(s["cases"], s["total_sin"], s["total_kcal"]))
    print("累计实付 {:.2f} 元　累计白扔 {:.2f} 元".format(s["total_paid"], s["total_gap"]))
    print("赎罪 {} / {} 分钟（{:.1f}%）　尚欠 {} 分钟".format(
        s["penance_done"], s["penance_total"], s["done_pct"], s["outstanding"]))
    print("连续打卡 {} 天　累计打卡 {} 次".format(s["streak_days"], s["checkin_count"]))
    print("\n最近案件：")
    for r in ledger.recent_cases(5):
        print("  {}　{}　{}　亏损 {:.2f} 元　赎罪 {} 分钟（已完成 {:.0f}%）".format(
            r.case_no, r.date, r.verdict or "—", r.gap, r.penance_minutes, r.done_pct))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """旧版：年度罪状报告 + 告解证书。"""
    table = _load_table()
    now = datetime.now()
    verdict = judge(DEMO_ORDERS, table, coupons=parse_coupons(DEMO_COUPON_TEXT), now=now)

    os.makedirs(OUT_DIR, exist_ok=True)
    md_path = os.path.join(OUT_DIR, "sin-report.md")
    html_path = os.path.join(OUT_DIR, "confession-certificate.html")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(verdict, now, source_note="内置虚构演示档案"))
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_certificate_html(verdict, now))
    print("[告解室] 罪状报告：{}".format(md_path))
    print("[告解室] 告解证书：{}".format(html_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcd-confessional", description="麦门告解室：多角色消费审判庭")
    sub = parser.add_subparsers(dest="command", required=True)

    p_trial = sub.add_parser("trial", help="完整庭审")
    p_trial.add_argument("--live", action="store_true", help="使用真实 MCP 订单")
    p_trial.add_argument("--save", action="store_true", help="判决写入账本")
    p_trial.add_argument("--ledger", default=None, help="账本路径")
    p_trial.set_defaults(func=cmd_trial)

    p_audit = sub.add_parser("audit", help="只看审计结果")
    p_audit.add_argument("--live", action="store_true")
    p_audit.add_argument("--ledger", default=None)
    p_audit.set_defaults(func=cmd_audit)

    p_check = sub.add_parser("checkin", help="赎罪打卡")
    p_check.add_argument("-m", "--minutes", type=int, required=True, help="本次赎罪分钟数")
    p_check.add_argument("--note", default="", help="备注，如「夜跑」")
    p_check.add_argument("--ledger", default=None)
    p_check.set_defaults(func=cmd_checkin)

    p_ledger = sub.add_parser("ledger", help="查看账本")
    p_ledger.add_argument("--ledger", default=None)
    p_ledger.set_defaults(func=cmd_ledger)

    p_demo = sub.add_parser("demo", help="旧版年度罪状报告")
    p_demo.add_argument("--ledger", default=None)
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    if getattr(args, "ledger", None) is None:
        args.ledger = DEFAULT_LEDGER_PATH
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

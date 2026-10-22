"""麦门告解室命令行入口。

用法::

    # 离线演示（无需 Token，使用内置虚构档案）
    python -m src.cli demo

    # 接入 MCP，对你的真实历史订单宣判（需要 MCD_MCP_TOKEN 环境变量）
    python -m src.cli confess

    # 只输出 Markdown / HTML
    python -m src.cli confess --format md
    python -m src.cli confess --format html
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

if __package__ in (None, ""):  # 支持 python src/cli.py 直接运行
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.demo_data import DEMO_COUPONS, DEMO_ORDERS  # noqa: E402
from src.mcp_client import MCPClient, MCPError  # noqa: E402
from src.nutrition_table import NutritionTable  # noqa: E402
from src.report import render_certificate_html, render_markdown  # noqa: E402
from src.sin_ledger import judge, parse_coupons  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


def _load_table(refresh: bool = False) -> NutritionTable:
    """加载热量圣经：优先本地基线，必要时通过 MCP 刷新缓存。"""
    table = NutritionTable.from_baseline()
    if refresh:
        client = MCPClient()
        try:
            table = NutritionTable.from_text(client.get_nutrition_text())
        except MCPError as exc:
            print("[告解室] 刷新营养数据失败，改用内置基线: {}".format(exc), file=sys.stderr)
    return table


def _run(orders: list[dict], coupon_text: str, table: NutritionTable, now: datetime,
         fmt: str, source_note: str) -> tuple[str, str]:
    coupons = parse_coupons(coupon_text)
    verdict = judge(orders, table, coupons=coupons, now=now)

    os.makedirs(OUT_DIR, exist_ok=True)
    md_path = os.path.join(OUT_DIR, "sin-report.md")
    html_path = os.path.join(OUT_DIR, "confession-certificate.html")

    markdown = render_markdown(verdict, now, source_note=source_note)
    html = render_certificate_html(verdict, now)

    if fmt in ("md", "both"):
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        print("[告解室] 罪状报告已生成: {}".format(md_path))
    if fmt in ("html", "both"):
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print("[告解室] 告解证书已生成: {}".format(html_path))
    if fmt == "md":
        print()
        print(markdown)
    return md_path, html_path


def cmd_demo(args: argparse.Namespace) -> int:
    print("[告解室] 演示模式：使用虚构罪徒档案（非真实数据）")
    table = _load_table(refresh=False)
    now = datetime.now()
    _run(DEMO_ORDERS, "", table, now, args.format, "内置虚构演示档案")
    return 0


def cmd_confess(args: argparse.Namespace) -> int:
    client = MCPClient()
    try:
        client.initialize()
        time_info = client.get_current_time()
        orders = client.get_orders()
        nutrition_text = client.get_nutrition_text()
        coupon_text = client.get_coupons_text()
    except MCPError as exc:
        print("[告解室] MCP 调用失败: {}".format(exc), file=sys.stderr)
        print("[告解室] 请确认已设置环境变量 MCD_MCP_TOKEN，或先运行 demo 模式体验。", file=sys.stderr)
        return 1

    now = datetime.now()
    if time_info.get("formatted"):
        try:
            now = datetime.strptime(time_info["formatted"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    print("[告解室] 已拉取 {} 笔历史订单，开始宣判……".format(len(orders)))
    table = NutritionTable.from_text(nutrition_text) if nutrition_text else _load_table()
    _run(orders, coupon_text, table, now, args.format, "麦当劳 MCP 真实数据（order-list）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcd-confessional", description="麦门告解室：麦当劳年度罪状报告生成器")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="离线演示（无需 Token）")
    p_demo.add_argument("--format", choices=["md", "html", "both"], default="both")
    p_demo.set_defaults(func=cmd_demo)

    p_confess = sub.add_parser("confess", help="接入麦当劳 MCP，对真实订单宣判")
    p_confess.add_argument("--format", choices=["md", "html", "both"], default="both")
    p_confess.set_defaults(func=cmd_confess)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

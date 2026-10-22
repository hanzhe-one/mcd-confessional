"""告解文书生成：年度罪状报告 (Markdown) + 可截图分享的告解证书 (HTML)。"""

from __future__ import annotations

from datetime import datetime

from .sin_ledger import Verdict, format_walk

CASE_NO_PREFIX = "MCD-CONF"


def _fmt_amount(value: float) -> str:
    return "{:.2f}".format(value)


def render_markdown(verdict: Verdict, now: datetime, source_note: str = "") -> str:
    """生成《年度罪状报告》Markdown。"""
    lines: list[str] = []
    add = lines.append

    add("# 麦当劳年度罪状报告")
    add("")
    add("> 案号：{}-{}".format(CASE_NO_PREFIX, now.strftime("%Y%m%d%H%M")))
    add("> 判决日期：{}".format(now.strftime("%Y-%m-%d %H:%M")))
    add("> 本报告由麦门告解室依据麦当劳 MCP 真实数据自动生成，仅供娱乐，不构成营养或医疗建议。")
    if source_note:
        add("> 数据来源：{}".format(source_note))
    add("")

    # ---- 总表 ----
    add("## 一、罪状总览")
    add("")
    add("| 项目 | 数值 |")
    add("| --- | --- |")
    add("| 作案次数 | {} 单 |".format(len(verdict.cases)))
    add("| 累计摄入热量 | {} 千卡 |".format(verdict.total_kcal))
    add("| 累计挥霍 | {} 元 |".format(_fmt_amount(verdict.total_amount)))
    add("| 累计罪恶点 | {} |".format(verdict.total_sin))
    add("| 罪级判定 | **{}（{}）** |".format(verdict.rank, verdict.rank_desc))
    add("| 基准赎罪工时 | 步行 {} |".format(format_walk(verdict.walk_minutes)))
    add("")

    # ---- 案情录 ----
    add("## 二、案情录")
    add("")
    if not verdict.cases:
        add("经查，你与麦当劳的过往清白如水，本席无从判罪。")
        add("（也可能是历史订单还没同步，建议在麦当劳 App 多消费几顿再来。）")
    for idx, case in enumerate(verdict.cases, 1):
        add("### 第 {} 案 · {}".format(idx, case.time_text or "时间不详"))
        add("")
        add("- 作案地点：{}".format(case.store_name))
        add("- 涉案金额：{} 元".format(_fmt_amount(case.amount)))
        add("- 涉案物品：")
        for item in case.items:
            mark = "" if item.matched else "（热量未录，按 0 计）"
            add("  - {} x{} —— {} 千卡{}".format(item.name, item.quantity, item.kcal, mark))
        add("- 本案热量：{} 千卡，罪恶点 {}".format(case.kcal, case.final_sin))
        if case.modifiers:
            add("- 量刑情节：{}".format("；".join(case.modifiers)))
        else:
            add("- 量刑情节：无从轻或从重情节，按基准刑论处。")
        add("")

    # ---- 量刑摘要 ----
    add("## 三、量刑摘要")
    add("")
    if verdict.worst_case:
        w = verdict.worst_case
        add("- 罪孽最重的一单：**{}** 在 {} 消费 {} 元，单笔罪恶点 {}。".format(
            w.time_text, w.store_name, _fmt_amount(w.amount), w.final_sin))
    if verdict.top_food:
        add("- 你最忠实的共犯：**{}**，共出现 {} 次。".format(*verdict.top_food))
    add("- 深夜犯罪率：**{:.0%}**（22:00 后至 05:00 前的下单占比）。".format(verdict.late_night_ratio))
    add("")

    # ---- 终审判决 ----
    add("## 四、终审判决")
    add("")
    add("本席认定：你在上述期间内共计犯下 **{}（{}）**，须于判决生效之日起，".format(verdict.rank, verdict.rank_desc))
    add("完成步行赎罪 **{}**。".format(format_walk(verdict.walk_minutes)))
    if verdict.coupons:
        add("")
        add("另查，你卡包内持有如下麦当劳官方赦免凭证：")
        add("")
        for c in verdict.coupons:
            add("- {}（有效期至 {}）".format(c.get("name", "?"), c.get("expire", "?")))
        add("")
        add("依据赦免条例，每张凭证可抵扣 5% 赎罪工时（上限 40%），")
        add("本席准予减免 **{}**，最终赎罪义务为：**步行 {}**。".format(
            format_walk(verdict.absolved_minutes), format_walk(verdict.final_walk_minutes)))
        add("")
        add("⚠️ 提醒：赦免凭证设有有效期，逾期未用，赦免失效，概不续期。")
    else:
        add("你卡包内暂无赦免凭证，全额赎罪，概不通融。")
    add("")

    # ---- 神父批注 ----
    add("## 五、告解师批注")
    add("")
    add(_priest_note(verdict))
    add("")
    add("---")
    add("")
    add("*麦门告解室 · 以代码之名，行审判之实 🍟*")
    add("")
    return "\n".join(lines)


def _priest_note(verdict: Verdict) -> str:
    """神父根据罪级给出不同批注。"""
    if not verdict.cases:
        return "孩子，你清白的像一张没开封的优惠券。但这并非终点——麦门的大门永远为你敞开。"
    notes = {
        "逐出麦籍": (
            "本席从业多年，从未见过如此虔诚又如此放纵的灵魂。"
            "你对麦当劳的忠诚已超越商业关系，升华为信仰；"
            "遗憾的是，信仰不能抵扣卡路里。去走路吧，走到麦浪尽头。"
        ),
        "麦门叛徒": (
            "你的账单显示，你与麦当劳的关系早已超越'偶尔吃吃'。"
            "建议你把本报告打印出来，贴在冰箱门上——这是你与理智之间最后的屏障。"
        ),
        "黑袍常客": (
            "有罪，但罪不至死。你的罪恶曲线平稳中带着放纵，"
            "像大多数成年人一样：明知故犯，犯完再吃。"
        ),
        "白衣罪徒": (
            "嗯……就这点？你甚至不好意思自称麦门信徒。"
            "不过万事开头难，谁还不是从第一个圆筒开始的。"
        ),
    }
    return notes.get(verdict.rank, notes["白衣罪徒"])


def render_certificate_html(verdict: Verdict, now: datetime, audit_summary=None) -> str:
    """生成单文件 HTML 告解证书，适合截图分享。

    audit_summary 可选：传入审计结果后，证书会多出一行"白扔金额"——
    这是整个项目里最能让人截图传播的数字。
    """
    case_no = "{}-{}".format(CASE_NO_PREFIX, now.strftime("%Y%m%d%H%M"))
    top_food = verdict.top_food[0] if verdict.top_food else "—"

    audit_row = ""
    audit_block = ""
    if audit_summary is not None and getattr(audit_summary, "cases", None):
        bad = sum(1 for c in audit_summary.cases if c.gap > 0.5)
        audit_row = "<div class='row'><span class='k'>审计结论</span><span class='v'>{}/{} 单本可更便宜</span></div>".format(
            bad, len(audit_summary.cases))
        audit_block = (
            "<div class='gapbox'><div class='gap-t'>按当前券池复核，你白扔了</div>"
            "<div class='gap-v'>{:.2f} 元</div>"
            "<div class='gap-s'>占实付 {:.1f}%　最惨一单白扔 {:.2f} 元</div></div>"
        ).format(
            audit_summary.total_gap,
            audit_summary.gap_rate,
            max((c.gap for c in audit_summary.cases), default=0.0),
        )

    coupons_html = ""
    if verdict.coupons:
        lis = "".join(
            "<li>{} <span class='exp'>（有效期至 {}）</span></li>".format(
                c.get("name", "?"), c.get("expire", "?"))
            for c in verdict.coupons
        )
        coupons_html = (
            "<div class='absolve'><div class='absolve-title'>官方赦免凭证</div>"
            "<ul>{}</ul><div class='absolve-note'>每张抵扣 5% 赎罪工时（上限40%），已减免 {}</div></div>".format(
                lis, format_walk(verdict.absolved_minutes))
        )
    else:
        coupons_html = "<div class='absolve empty'>卡包内暂无赦免凭证，全额赎罪，概不通融。</div>"

    worst = ""
    if verdict.worst_case:
        w = verdict.worst_case
        worst = "<div class='worst'>罪孽最重的一单：<b>{}</b> 于 {} 消费 {} 元</div>".format(
            w.time_text, w.store_name, _fmt_amount(w.amount))

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>麦门告解证书</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f5efe3; color: #3d2b1f; display: flex;
    justify-content: center; align-items: center; min-height: 100vh; padding: 24px;
  }}
  .cert {{
    width: 420px; background: #fffdf6; border: 2px solid #c9a86a; border-radius: 12px;
    padding: 32px 28px; position: relative; box-shadow: 0 8px 30px rgba(61,43,31,.15);
  }}
  .cert::before {{
    content: ""; position: absolute; inset: 8px; border: 1px dashed #c9a86a;
    border-radius: 8px; pointer-events: none;
  }}
  .head {{ text-align: center; margin-bottom: 18px; }}
  .head .org {{ font-size: 12px; letter-spacing: 4px; color: #a08454; }}
  .head h1 {{ font-size: 26px; letter-spacing: 6px; margin: 6px 0 2px; }}
  .head .no {{ font-size: 11px; color: #a08454; }}
  .seal {{
    position: absolute; top: 18px; right: 20px; width: 64px; height: 64px;
    border: 3px solid #b03a2e; border-radius: 50%; color: #b03a2e;
    display: flex; align-items: center; justify-content: center; text-align: center;
    font-size: 13px; font-weight: 700; line-height: 1.2; transform: rotate(-12deg);
    opacity: .85;
  }}
  .row {{ display: flex; justify-content: space-between; padding: 7px 0;
         border-bottom: 1px dashed #e3d5b8; font-size: 14px; }}
  .row .k {{ color: #8a6d3b; }}
  .row .v {{ font-weight: 600; }}
  .rank-box {{
    margin: 16px 0; padding: 14px; text-align: center; background: #faf3e3;
    border: 1px solid #c9a86a; border-radius: 8px;
  }}
  .rank-box .t {{ font-size: 12px; color: #a08454; letter-spacing: 2px; }}
  .rank-box .r {{ font-size: 24px; font-weight: 800; margin: 4px 0; }}
  .rank-box .p {{ font-size: 18px; font-weight: 700; color: #b03a2e; }}
  .absolve {{ margin-top: 14px; font-size: 12px; }}
  .absolve-title {{ font-weight: 700; margin-bottom: 4px; }}
  .absolve ul {{ padding-left: 18px; }}
  .absolve .exp {{ color: #a08454; }}
  .absolve-note {{ margin-top: 4px; color: #8a6d3b; }}
  .absolve.empty {{ color: #8a6d3b; font-style: italic; }}
  .worst {{ margin-top: 10px; font-size: 12px; color: #6b4f2a; }}
  .gapbox {{
    margin-top: 12px; padding: 10px 12px; border: 1px dashed #b03a2e;
    border-radius: 8px; text-align: center; background: #fdf5f4;
  }}
  .gapbox .gap-t {{ font-size: 11px; color: #8a6d3b; }}
  .gapbox .gap-v {{ font-size: 22px; font-weight: 800; color: #b03a2e; line-height: 1.3; }}
  .gapbox .gap-s {{ font-size: 11px; color: #8a6d3b; }}
  .foot {{ margin-top: 18px; text-align: center; font-size: 11px; color: #a08454; }}
</style>
</head>
<body>
<div class="cert">
  <div class="seal">麦门<br>告解</div>
  <div class="head">
    <div class="org">麦 门 告 解 室</div>
    <h1>年度告解证书</h1>
    <div class="no">案号 {case_no} · 判决于 {date}</div>
  </div>
  <div class="row"><span class="k">作案次数</span><span class="v">{count} 单</span></div>
  <div class="row"><span class="k">累计摄入热量</span><span class="v">{kcal} 千卡</span></div>
  <div class="row"><span class="k">累计挥霍</span><span class="v">{amount} 元</span></div>
  <div class="row"><span class="k">累计罪恶点</span><span class="v">{sin}</span></div>
  <div class="row"><span class="k">忠实共犯</span><span class="v">{top_food}</span></div>
  {audit_row}
  <div class="rank-box">
    <div class="t">罪 级 判 定</div>
    <div class="r">{rank}（{rank_desc}）</div>
    <div class="p">须步行赎罪 {walk}</div>
  </div>
  {audit_block}
  {worst}
  {coupons_html}
  <div class="foot">本证书由麦当劳 MCP 真实数据驱动 · 截图分享即传教<br>仅供娱乐，不构成营养或医疗建议</div>
</div>
</body>
</html>""".format(
        case_no=case_no,
        date=now.strftime("%Y-%m-%d %H:%M"),
        count=len(verdict.cases),
        kcal=verdict.total_kcal,
        amount=_fmt_amount(verdict.total_amount),
        sin=verdict.total_sin,
        top_food=top_food,
        rank=verdict.rank,
        rank_desc=verdict.rank_desc,
        walk=format_walk(verdict.walk_minutes),
        audit_row=audit_row,
        audit_block=audit_block,
        worst=worst,
        coupons_html=coupons_html,
    )

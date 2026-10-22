"""庭审记录页渲染：把 Trial 的结构化数据排成一页可视化的庭审记录。

设计意图
--------
CLI 的纯文本是给终端看的，分享传播需要一张能截图的"文书"。
本模块不生成文本，而是直接读 Trial 的结构化字段做版式：
- 左侧竖排角色印章，让四个角色视觉上分得开
- 关键金额用衬线大字号，一眼能看到 36.00 元、1.1 天
- 采纳/驳回用不同底色，判决部分用红章收尾
"""

from __future__ import annotations

import html
from datetime import datetime

from .trial import Trial


def _esc(value: object) -> str:
    return html.escape(str(value))


def _cause_rows(trial: Trial) -> str:
    labels = {
        "full_price": "全价买单",
        "suboptimal": "券未用到位",
        "spec_loss": "规格不划算",
    }
    rows = []
    total = sum(v for v in trial.summary.by_cause.values()) or 1.0
    for cause, amount in sorted(trial.summary.by_cause.items(), key=lambda kv: -kv[1]):
        pct = amount / total * 100
        rows.append(
            "<div class='cause'><div class='cause-head'><span>{}</span>"
            "<span class='num'>{:.2f} 元</span></div>"
            "<div class='bar'><i style='width:{:.0f}%'></i></div></div>".format(
                _esc(labels.get(cause, cause)), amount, pct)
        )
    return "".join(rows) or "<div class='muted'>无亏损归因</div>"


def _defense_rows(trial: Trial) -> str:
    accepted = trial.result.accepted
    rejected = [p for p in trial.result.defense_points if p not in accepted]
    out = []
    for p in accepted:
        out.append(
            "<li class='ok'><b>采纳</b><span>{}</span><em>{}</em></li>".format(
                _esc(p.claim), _esc(p.evidence))
        )
    for p in rejected:
        out.append(
            "<li class='no'><b>驳回</b><span>{}</span><em>{}</em></li>".format(
                _esc(p.claim), _esc(p.evidence))
        )
    return "".join(out) or "<li class='muted'>无辩护意见</li>"


def _cases_rows(trial: Trial) -> str:
    out = []
    for case in trial.summary.cases:
        names = "、".join("{}×{}".format(i.name, i.qty) for i in case.basket)
        gap_cls = "gap-pos" if case.gap > 0.5 else "gap-zero"
        gap_text = "{:.2f} 元".format(case.gap) if case.gap > 0.5 else "无亏损"
        out.append(
            "<tr><td class='t'>{}</td><td>{}</td><td>{}</td>"
            "<td class='num'>{:.2f}</td><td class='num'>{:.2f}</td>"
            "<td class='num {}'>{}</td></tr>".format(
                _esc(case.time_text[5:16]), _esc(case.store_name), _esc(names),
                case.paid, case.optimal, gap_cls, gap_text)
        )
    return "".join(out)


def render_trial_html(trial: Trial, now: datetime | None = None) -> str:
    now = now or trial.now
    s = trial.summary
    r = trial.result
    case_no = "MCD-TRIAL-{}".format(now.strftime("%Y%m%d%H%M"))
    daily = 60
    plan_days = max(1, int(round(r.final_penance / daily)))
    bad = sum(1 for c in s.cases if c.gap > 0.5)

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>庭审记录 · 麦门告解室</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  :root {{
    --paper:#faf7f0; --ink:#2b2118; --ink2:#6b5b4a;
    --line:#e0d4bd; --red:#a63a2e; --gold:#b08b4f; --green:#4a7c59;
  }}
  body {{
    font-family:"PingFang SC","Microsoft YaHei",sans-serif;
    background:#efe8da; color:var(--ink); line-height:1.75; padding:28px 16px 60px;
  }}
  .doc {{
    max-width:760px; margin:0 auto; background:var(--paper);
    border:1px solid var(--line); box-shadow:0 10px 40px rgba(43,33,24,.14);
  }}
  /* 文头 */
  .head {{ padding:34px 40px 24px; border-bottom:2px solid var(--ink);
           display:flex; justify-content:space-between; align-items:flex-end; }}
  .head h1 {{ font-size:26px; letter-spacing:8px; font-weight:700; }}
  .head .en {{ font-size:10px; letter-spacing:3px; color:var(--gold); margin-top:4px; }}
  .head .meta {{ text-align:right; font-size:11px; color:var(--ink2); line-height:1.9; }}
  .head .meta b {{ color:var(--ink); font-weight:600; }}

  /* 阶段 */
  .stage {{ display:flex; border-bottom:1px solid var(--line); }}
  .seal {{
    flex:0 0 62px; background:#f3ece0; border-right:1px solid var(--line);
    display:flex; align-items:center; justify-content:center; padding:18px 0;
  }}
  .seal span {{
    writing-mode:vertical-rl; letter-spacing:4px; font-size:13px; font-weight:700;
    color:var(--red); border:1.5px solid var(--red); border-radius:3px;
    padding:8px 5px; opacity:.9;
  }}
  .seal.plain span {{ color:var(--gold); border-color:var(--gold); }}
  .body {{ flex:1; padding:20px 26px 24px; min-width:0; }}
  .body h2 {{ font-size:15px; font-weight:700; letter-spacing:2px; margin-bottom:2px; }}
  .motto {{ font-size:12.5px; color:var(--gold); font-style:italic; margin-bottom:14px; }}

  /* 总览数字 */
  .figures {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px;
              background:var(--line); border:1px solid var(--line); margin-bottom:14px; }}
  .fig {{ background:#fffdf8; padding:12px 10px; text-align:center; }}
  .fig .k {{ font-size:11px; color:var(--ink2); }}
  .fig .v {{ font-family:Georgia,"Times New Roman",serif; font-size:22px;
             font-weight:700; line-height:1.25; margin-top:2px; }}
  .fig .v.red {{ color:var(--red); }}
  .fig .u {{ font-size:11px; font-weight:400; color:var(--ink2); }}

  p.line {{ font-size:13.5px; margin-bottom:6px; }}
  .hl {{ color:var(--red); font-weight:700; font-family:Georgia,serif; font-size:15px; }}

  /* 归因条 */
  .cause {{ margin-top:10px; }}
  .cause-head {{ display:flex; justify-content:space-between; font-size:12.5px; }}
  .cause-head .num {{ font-family:Georgia,serif; font-weight:700; }}
  .bar {{ height:5px; background:#eae0cd; margin-top:4px; border-radius:3px; overflow:hidden; }}
  .bar i {{ display:block; height:100%; background:var(--red); opacity:.75; }}

  /* 案情表 */
  table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:4px; }}
  th {{ text-align:left; font-weight:600; color:var(--ink2); font-size:11px;
        border-bottom:1px solid var(--line); padding:6px 4px; white-space:nowrap; }}
  td {{ padding:7px 4px; border-bottom:1px dashed #ece2cf; vertical-align:top; }}
  td.num {{ text-align:right; font-family:Georgia,serif; white-space:nowrap; }}
  td.t {{ white-space:nowrap; color:var(--ink2); }}
  .gap-pos {{ color:var(--red); font-weight:700; }}
  .gap-zero {{ color:var(--green); }}

  /* 辩护 */
  ul.def {{ list-style:none; }}
  ul.def li {{ display:flex; gap:8px; font-size:12.5px; padding:7px 0;
               border-bottom:1px dashed #ece2cf; align-items:baseline; }}
  ul.def li b {{ flex:0 0 30px; font-size:10px; font-weight:700; text-align:center;
                 border-radius:3px; padding:1px 0; }}
  ul.def li.ok b {{ color:#fff; background:var(--green); }}
  ul.def li.no b {{ color:var(--ink2); background:#e6dcc8; }}
  ul.def li.no span {{ color:var(--ink2); text-decoration:line-through; text-decoration-color:#c9bda6; }}
  ul.def li em {{ display:block; font-style:normal; font-size:11px; color:var(--gold); }}

  /* 量刑 */
  .calc {{ font-size:13px; background:#f6f0e3; border-left:3px solid var(--gold);
           padding:12px 14px; margin:6px 0 12px; line-height:2; }}
  .calc .row {{ display:flex; justify-content:space-between; }}
  .calc .row.total {{ border-top:1px solid var(--line); margin-top:6px; padding-top:8px;
                      font-size:15px; font-weight:700; }}
  .calc .num {{ font-family:Georgia,serif; }}

  /* 判决 */
  .verdict {{ background:#fffdf8; border:2px solid var(--red); padding:22px 24px;
              position:relative; }}
  .verdict .rank {{ font-size:24px; font-weight:800; letter-spacing:4px; color:var(--red);
                    font-family:Georgia,serif; }}
  .verdict .rank small {{ font-size:12px; letter-spacing:1px; color:var(--ink2); font-weight:400; }}
  .verdict .pen {{ font-size:14px; margin-top:8px; }}
  .verdict .note {{ font-size:12.5px; color:var(--ink2); margin-top:12px;
                    border-top:1px dashed var(--line); padding-top:10px; }}
  .stamp {{ position:absolute; right:18px; bottom:14px; width:72px; height:72px;
            border:3px solid var(--red); border-radius:50%; color:var(--red);
            display:flex; align-items:center; justify-content:center; text-align:center;
            font-size:12px; font-weight:700; line-height:1.3; transform:rotate(-11deg); opacity:.72; }}

  /* 执事 */
  .plan {{ display:flex; gap:26px; align-items:center; flex-wrap:wrap; }}
  .plan .big {{ font-family:Georgia,serif; font-size:30px; font-weight:700; color:var(--ink); }}
  .plan .big small {{ font-size:12px; color:var(--ink2); font-weight:400; }}
  .plan .txt {{ font-size:12.5px; color:var(--ink2); }}
  code {{ background:#efe7d6; padding:1px 6px; border-radius:3px; font-size:12px; }}

  .foot {{ padding:16px 40px 22px; font-size:10.5px; color:#98876f; text-align:center;
           border-top:1px solid var(--line); line-height:1.9; }}
  .muted {{ color:var(--ink2); font-size:12px; }}
  @media (max-width:560px) {{
    .head {{ padding:24px 20px 18px; flex-direction:column; align-items:flex-start; gap:10px; }}
    .head .meta {{ text-align:left; }}
    .body {{ padding:16px 16px 20px; }}
    .seal {{ flex:0 0 44px; }}
    .seal span {{ font-size:11px; letter-spacing:2px; }}
    .figures {{ grid-template-columns:repeat(3,1fr); }}
    .fig .v {{ font-size:17px; }}
  }}
</style>
</head>
<body>
<div class="doc">
  <div class="head">
    <div>
      <h1>麦门告解室</h1>
      <div class="en">McDonald's Confessional · Trial Record</div>
    </div>
    <div class="meta">
      案号 <b>{case_no}</b><br>
      受理区间 <b>{days} 天</b> · <b>{n}</b> 笔订单<br>
      开庭时间 <b>{date}</b>
    </div>
  </div>

  <!-- ① 案情总览 -->
  <div class="stage">
    <div class="seal plain"><span>案情</span></div>
    <div class="body">
      <h2>一、受理范围</h2>
      <div class="figures">
        <div class="fig"><div class="k">涉案金额</div><div class="v">{paid:.2f}<span class="u"> 元</span></div></div>
        <div class="fig"><div class="k">累计热量</div><div class="v">{kcal}<span class="u"> 千卡</span></div></div>
        <div class="fig"><div class="k">订单笔数</div><div class="v">{n}<span class="u"> 笔</span></div></div>
      </div>
      <table>
        <thead><tr><th>时间</th><th>门店</th><th>涉案餐品</th>
        <th style="text-align:right">实付</th><th style="text-align:right">最优</th>
        <th style="text-align:right">亏损</th></tr></thead>
        <tbody>{cases_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- ② 审计官 -->
  <div class="stage">
    <div class="seal"><span>审计官</span></div>
    <div class="body">
      <h2>二、审计官陈词</h2>
      <div class="motto">「感情归你，数字归我。」</div>
      <div class="figures">
        <div class="fig"><div class="k">实付合计</div><div class="v">{paid:.2f}<span class="u"> 元</span></div></div>
        <div class="fig"><div class="k">理论最优</div><div class="v">{optimal:.2f}<span class="u"> 元</span></div></div>
        <div class="fig"><div class="k">白扔</div><div class="v red">{gap:.2f}<span class="u"> 元</span></div></div>
      </div>
      <p class="line">{n} 单中有 <span class="hl">{bad}</span> 单本可更便宜，
      差额占实付 <span class="hl">{gap_rate:.1f}%</span>。</p>
      {worst_line}
      {cause_rows}
    </div>
  </div>

  <!-- ③ 辩护律师 -->
  <div class="stage">
    <div class="seal"><span>辩护人</span></div>
    <div class="body">
      <h2>三、辩护意见</h2>
      <div class="motto">「没有人天生就是罪人，只是没人替他算过账。」</div>
      <ul class="def">{defense_rows}</ul>
    </div>
  </div>

  <!-- ④ 量刑 -->
  <div class="stage">
    <div class="seal"><span>合议</span></div>
    <div class="body">
      <h2>四、合议量刑</h2>
      <div class="calc">
        <div class="row"><span>热量赎罪（{kcal} 千卡 × 0.25 分钟）</span><span class="num">{heat_min} 分钟</span></div>
        <div class="row"><span>亏损罚金（{gap:.2f} 元白扔 × 10 分钟）</span><span class="num">{gap_min} 分钟</span></div>
        <div class="row"><span>基准刑</span><span class="num">{base_min} 分钟</span></div>
        <div class="row"><span>减刑（采纳 {acc} 条 × 5%，上限 30%）</span><span class="num">−{disc_pct}%</span></div>
        <div class="row total"><span>最终赎罪义务</span><span class="num">{final_h}</span></div>
      </div>
    </div>
  </div>

  <!-- ⑤ 宣判 -->
  <div class="stage">
    <div class="seal"><span>判决</span></div>
    <div class="body">
      <h2>五、宣判</h2>
      <div class="verdict">
        <div class="rank">{rank} <small>（{rank_desc}）</small></div>
        <div class="pen">判处步行赎罪 <b>{final_h}</b>。</div>
        <div class="note">{note}</div>
        <div class="stamp">麦门<br>告解</div>
      </div>
    </div>
  </div>

  <!-- ⑥ 执事 -->
  <div class="stage">
    <div class="seal"><span>执事</span></div>
    <div class="body">
      <h2>六、执行登记</h2>
      <div class="plan">
        <div class="big">{daily}<small> 分钟 / 日</small></div>
        <div class="txt">
          预计 <b>{plan_days}</b> 天走完。<br>
          打卡方式：对执事说 <code>打卡 60 分钟</code><br>
          提醒：每晚 22:00 晚祷 · 优惠券到期前 24 小时预警
        </div>
      </div>
    </div>
  </div>

  <div class="foot">
    本记录由麦门告解室自动生成 · 麦当劳 MCP 真实数据驱动<br>
    审计金额为按当前券池重算的反事实估算 · 菜单价为演示快照 · 仅供娱乐，不构成营养或医疗建议
  </div>
</div>
</body>
</html>""".format(
        case_no=case_no,
        days=trial.days_span,
        n=len(s.cases),
        date=now.strftime("%Y-%m-%d %H:%M"),
        paid=s.total_paid,
        kcal=s.total_kcal,
        optimal=s.total_optimal,
        gap=s.total_gap,
        gap_rate=s.gap_rate,
        bad=bad,
        cases_rows=_cases_rows(trial),
        worst_line=(
            "<p class='line'>亏损最重一单：{} 于 {}，实付 <span class='hl'>{:.2f}</span> 元，"
            "本可 <span class='hl'>{:.2f}</span> 元，白扔 <span class='hl'>{:.2f}</span> 元。</p>".format(
                _esc(s.worst.time_text), _esc(s.worst.store_name), s.worst.paid, s.worst.optimal, s.worst.gap)
            if s.worst and s.worst.gap > 0 else ""
        ),
        cause_rows=_cause_rows(trial),
        defense_rows=_defense_rows(trial),
        heat_min=int(s.total_kcal * 0.25),
        gap_min=int(s.total_gap * 10),
        base_min=r.base_penance,
        acc=len(r.accepted),
        disc_pct=int(r.discount * 100),
        final_h=_fmt_minutes(r.final_penance),
        rank=_esc(trial.verdict.rank),
        rank_desc=_esc(trial.verdict.rank_desc),
        note=_esc(r.verdict_text.split("批注：")[-1] if "批注：" in r.verdict_text else "维持原判。"),
        daily=daily,
        plan_days=plan_days,
    )


def _fmt_minutes(minutes: int) -> str:
    if minutes < 60:
        return "{} 分钟".format(minutes)
    hours = minutes / 60.0
    if hours < 24:
        return "{:.1f} 小时".format(hours)
    return "{:.1f} 天".format(hours / 24.0)

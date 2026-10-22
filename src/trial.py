"""多角色审判庭：四个角色、七个阶段，编排一场完整的消费审判。

角色分工（不是各说各话，而是真正咬合）
------------------------------------
- 审计官 Auditor  ：把每一单的真实亏损算出来（调用 audit.py，金额可验证）
- 辩护律师 Advocate：从数据里找减刑情节（深夜=加班？选无糖=有向善之心？）
- 告解师 Confessor：主审，盘问 + 定罪 + 量刑
- 执事 Bailiff    ：登记账本、下达赎罪计划、盯打卡

量刑公式（透明可复现）
--------------------
    赎罪工时 = 卡路里 x 3 分钟  +  亏损金额 x 5 分钟
    减刑     = 有效辩护条数 x 5%（上限 30%）
    最终     = 赎罪工时 x (1 - 减刑)

辩护不是摆设：每条被采纳的辩护都真实减少赎罪工时。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .audit import AuditCase, AuditSummary
from .sin_ledger import WALK_MIN_PER_KCAL, Verdict, format_walk

# 赎罪换算统一从 sin_ledger 取，避免两处常量漂移：
# 每千卡 = 0.25 分钟步行（慢走 4 km/h 约 4 kcal/min）
SIN_MIN_PER_KCAL = WALK_MIN_PER_KCAL
# 亏损罚金：每白扔 1 元 = 10 分钟赎罪（让"浪费的钱"有痛感，但不至于压过健康账）
PENANCE_MIN_PER_YUAN = 10
DEFENSE_DISCOUNT_PER_ITEM = 0.05
DEFENSE_DISCOUNT_CAP = 0.30


# --------------------------------------------------------------------- #
# 角色画像
# ---------------------------------------------------------------------
@dataclass
class Role:
    key: str
    name: str
    title: str
    motto: str
    duty: str
    prompt: str = ""


ROLES: dict[str, Role] = {
    "auditor": Role(
        key="auditor",
        name="审计官",
        title="The Auditor",
        motto="感情归你，数字归我。",
        duty="调用 calculate-price 与券优化器，算出每一单本该花多少，把亏损摆到台面上。",
        prompt=(
            "你是麦门告解室的审计官，只讲数字不讲感情。"
            "拿到订单后逐单给出：实付、按当前券池的最优价、差额（亏损）、归因"
            "（没用券/券没用到位/规格不划算）。所有金额必须来自工具计算结果，"
            "严禁自行估算。语气冷峻简短，像在念审计底稿。"
        ),
    ),
    "advocate": Role(
        key="advocate",
        name="辩护律师",
        title="The Advocate",
        motto="没有人天生就是罪人，只是没人替他算过账。",
        duty="从真实数据里找减刑情节，为罪人争取更轻的赎罪工时。",
        prompt=(
            "你是麦门告解室的辩护律师，为当事人争取减刑。"
            "只允许基于真实数据提出辩护（深夜下单率、无糖选择次数、券使用率、"
            "客单价、复购周期、规格选择），每条辩护必须附上具体数字。"
            "禁止编造情节。若数据确实无可辩驳，要坦率认罪。"
        ),
    ),
    "confessor": Role(
        key="confessor",
        name="告解师",
        title="The Confessor",
        motto="本席不同情你，但本席理解你。",
        duty="主审：盘问可疑订单、认定罪级、宣判赎罪工时。",
        prompt=(
            "你是麦门告解室的主审告解师，毒舌但慈悲。"
            "基于审计官的数据与辩护律师的意见量刑，量刑公式见 trial.py。"
            "盘问要针对数据里的异常点（单笔金额最高、深夜下单、券过期未用）。"
            "判决后给一段批注：既不安慰过度，也不羞辱当事人。"
        ),
    ),
    "bailiff": Role(
        key="bailiff",
        name="执事",
        title="The Bailiff",
        motto="判决书签了字，就得走完这段路。",
        duty="登记账本、下达可执行的赎罪计划、跟踪打卡与券到期预警。",
        prompt=(
            "你是麦门告解室的执事，负责执行。"
            "把判决写进账本（state.py 的 Ledger），把赎罪工时拆成每天可完成的小任务，"
            "并在用户打卡时如实登记。提醒券到期时必须给出券名与剩余时间。"
            "语气干练，不说废话。"
        ),
    ),
}


# --------------------------------------------------------------------- #
# 辩护要点（全部由数据推导）
# ---------------------------------------------------------------------
@dataclass
class DefensePoint:
    claim: str
    evidence: str
    weight: float = 1.0     # 1.0 = 一条有效辩护


def build_defense(
    cases: list[AuditCase],
    total_kcal: int,
    late_night_ratio: float,
    coupon_used_ratio: float,
    avg_ticket: float,
    days_span: int,
) -> list[DefensePoint]:
    """辩护律师的开庭陈词：每条都必须有数据支撑。"""
    points: list[DefensePoint] = []

    sugar_free = sum(1 for c in cases if any("无糖" in i.name for i in c.basket))
    if sugar_free:
        points.append(DefensePoint(
            claim="当事人曾主动选择无糖饮品，具备向善意愿",
            evidence="共 {} 单出现过无糖选择".format(sugar_free),
        ))

    if coupon_used_ratio >= 0.3:
        points.append(DefensePoint(
            claim="当事人并非挥霍之人，多数订单已在主动使用优惠",
            evidence="{:.0f}% 的订单实付低于菜单原价".format(coupon_used_ratio * 100),
        ))

    if avg_ticket <= 35:
        points.append(DefensePoint(
            claim="单均消费克制，无奢侈之举",
            evidence="客单价仅 {:.2f} 元".format(avg_ticket),
        ))

    if late_night_ratio > 0 and late_night_ratio <= 0.35:
        points.append(DefensePoint(
            claim="深夜下单虽有过，但占比有限，且多为加班后的必要补给",
            evidence="深夜订单占比 {:.0f}%".format(late_night_ratio * 100),
        ))
    elif late_night_ratio > 0.35:
        points.append(DefensePoint(
            claim="深夜下单比例虽高，但当事人承担着高强度工作",
            evidence="深夜订单占比 {:.0f}%，属高压人群的普遍行为".format(late_night_ratio * 100),
            weight=0.5,
        ))

    if days_span >= 30:
        points.append(DefensePoint(
            claim="消费频次有节制，并非沉溺",
            evidence="{} 天内仅 {} 单，平均 {:.1f} 天一次".format(
                days_span, len(cases), days_span / max(len(cases), 1)),
        ))

    clean = sum(1 for c in cases if "clean" in c.causes)
    if clean:
        points.append(DefensePoint(
            claim="当事人有过零亏损的完美订单，证明其具备自律能力",
            evidence="{} 单实付等于或低于理论最优价".format(clean),
        ))

    # 小份规格的选择
    small_spec = sum(1 for c in cases if any(i.name in ("小薯条", "可乐小杯", "迷你薯条", "小杯玉米杯") for i in c.basket))
    if small_spec:
        points.append(DefensePoint(
            claim="当事人多次选择小份规格，未有暴食倾向",
            evidence="{} 单选择了小份规格".format(small_spec),
        ))

    return points


# --------------------------------------------------------------------- #
# 庭审
# ---------------------------------------------------------------------
@dataclass
class TrialResult:
    base_penance: int = 0
    defense_points: list[DefensePoint] = field(default_factory=list)
    accepted: list[DefensePoint] = field(default_factory=list)
    discount: float = 0.0
    final_penance: int = 0
    verdict_text: str = ""


class Trial:
    """一场审判。run() 可以无人值守跑完全流程，也可以逐阶段交互。"""

    def __init__(
        self,
        summary: AuditSummary,
        verdict: Verdict,
        now: datetime | None = None,
        late_night_ratio: float = 0.0,
        coupon_used_ratio: float = 0.0,
        days_span: int = 1,
    ) -> None:
        self.summary = summary
        self.verdict = verdict
        self.now = now or datetime.now()
        self.late_night_ratio = late_night_ratio
        self.coupon_used_ratio = coupon_used_ratio
        self.days_span = max(days_span, 1)
        self.result = TrialResult()
        self.transcript: list[str] = []

    # -- 各阶段 ------------------------------------------------------- #
    def stage_open(self) -> str:
        s = self.summary
        text = (
            "【开庭】\n"
            "案号 MCD-TRIAL-{no}　审判庭：麦门告解室\n"
            "本庭受理被告在过去 {days} 天内的 {n} 笔麦当劳消费，涉案金额 {paid:.2f} 元，"
            "累计摄入 {kcal} 千卡。\n"
            "出庭人员：审计官、辩护律师、告解师、执事。"
        ).format(
            no=self.now.strftime("%Y%m%d%H%M"),
            days=self.days_span,
            n=len(s.cases),
            paid=s.total_paid,
            kcal=s.total_kcal,
        )
        self.transcript.append(text)
        return text

    def stage_audit(self) -> str:
        s = self.summary
        lines = ["【审计官陈词】", s_quote(ROLES["auditor"])]
        lines.append(
            "经逐单复核：按当前券池的最优组合，{n} 单里有 {bad} 单本可以更便宜。".format(
                n=len(s.cases), bad=sum(1 for c in s.cases if c.gap > 0.5))
        )
        lines.append("实付合计 {:.2f} 元，理论最优合计 {:.2f} 元，差额 {:.2f} 元（占实付 {:.1f}%）。".format(
            s.total_paid, s.total_optimal, s.total_gap, s.gap_rate))
        if s.worst and s.worst.gap > 0:
            w = s.worst
            lines.append("亏损最重的一单：{} 于{}，实付 {:.2f} 元，最优价 {:.2f} 元，白扔 {:.2f} 元。".format(
                w.time_text, w.store_name, w.paid, w.optimal, w.gap))
        for cause, amount in sorted(s.by_cause.items(), key=lambda kv: -kv[1]):
            label = {"full_price": "全价买单", "suboptimal": "券未用到位", "spec_loss": "规格不划算"}.get(cause, cause)
            lines.append("　· {}：{:.2f} 元".format(label, amount))
        text = "\n".join(lines)
        self.transcript.append(text)
        return text

    def stage_defense(self) -> str:
        points = build_defense(
            self.summary.cases,
            self.summary.total_kcal,
            self.late_night_ratio,
            self.coupon_used_ratio,
            self.summary.total_paid / max(len(self.summary.cases), 1),
            self.days_span,
        )
        self.result.defense_points = points
        lines = ["【辩护律师抗辩】", s_quote(ROLES["advocate"])]
        if not points:
            lines.append("　本律师无话可说。数据摆在面前，当事人确实无可辩解。")
        for idx, p in enumerate(points, 1):
            lines.append("　{}. {}（依据：{}）".format(idx, p.claim, p.evidence))
        lines.append("　请求法庭据此从轻量刑。")
        text = "\n".join(lines)
        self.transcript.append(text)
        return text

    def stage_interrogation(self) -> list[str]:
        """告解师针对数据异常点发问（给交互式 Agent 用）。"""
        questions: list[str] = []
        s = self.summary
        if s.worst and s.worst.gap >= 5:
            questions.append("{} 那一单，你实付 {:.2f} 元，本来 {:.2f} 元就能吃到同样的东西。当时是懒得凑券，还是根本不知道有券？".format(
                s.worst.time_text, s.worst.paid, s.worst.optimal))
        if self.late_night_ratio >= 0.3:
            questions.append("你有 {:.0f}% 的订单在 22 点之后下单。是加班到那个点，还是睡不着？".format(
                self.late_night_ratio * 100))
        spec_cases = [c for c in s.cases if "spec_loss" in c.causes]
        if spec_cases:
            questions.append("有 {} 单的规格性价比不划算。你点大份，是因为真吃得下，还是因为「大份更划算」的错觉？".format(len(spec_cases)))
        if not questions:
            questions.append("本席看不出明显破绽。你自己说，这一年有没有哪一顿，你明知不该吃？")
        return questions

    def stage_sentencing(self, accepted_count: int | None = None) -> str:
        """合议量刑：辩护每被采纳一条减 5%，上限 30%。

        采纳规则（避免"全盘采纳"的失真）：
        - weight >= 1.0 的辩护才算有效
        - 最多采纳 4 条
        - 其余当庭驳回并说明理由
        """
        all_points = self.result.defense_points
        if accepted_count is None:
            eligible = [p for p in all_points if p.weight >= 1.0]
            accepted = eligible[:4]
        else:
            accepted = all_points[:accepted_count]
        rejected = [p for p in all_points if p not in accepted]

        self.result.accepted = accepted
        self.result.base_penance = int(round(self.summary.total_kcal * SIN_MIN_PER_KCAL
                                             + self.summary.total_gap * PENANCE_MIN_PER_YUAN))
        self.result.discount = round(min(len(accepted) * DEFENSE_DISCOUNT_PER_ITEM, DEFENSE_DISCOUNT_CAP), 3)
        self.result.final_penance = int(round(self.result.base_penance * (1 - self.result.discount)))

        lines = ["【合议量刑】"]
        lines.append("　基准刑：热量赎罪 {} + 亏损罚金赎罪 {} = {}".format(
            format_walk(int(self.summary.total_kcal * SIN_MIN_PER_KCAL)),
            format_walk(int(self.summary.total_gap * PENANCE_MIN_PER_YUAN)),
            format_walk(self.result.base_penance)))
        if accepted:
            lines.append("　采纳辩护 {} 条，减刑 {}%：".format(len(accepted), int(self.result.discount * 100)))
            for p in accepted:
                lines.append("　　√ {}".format(p.claim))
        if rejected:
            lines.append("　驳回 {} 条，理由：证据不足或属普遍行为，不构成减刑事由。".format(len(rejected)))
        lines.append("　最终赎罪义务：{}".format(format_walk(self.result.final_penance)))
        if self.result.discount >= DEFENSE_DISCOUNT_CAP:
            lines.append("　（已达减刑上限 {}%）".format(int(DEFENSE_DISCOUNT_CAP * 100)))
        text = "\n".join(lines)
        self.transcript.append(text)
        return text

    def stage_verdict(self) -> str:
        v = self.verdict
        text = "【宣判】\n本席认定：被告犯下 {}（{}），判处步行赎罪 {}。\n\n批注：{}".format(
            v.rank, v.rank_desc, format_walk(self.result.final_penance), _verdict_note(v, self.summary)
        )
        self.result.verdict_text = text
        self.transcript.append(text)
        return text

    def stage_registry(self) -> str:
        daily = 60
        days = max(1, int(round(self.result.final_penance / daily)))
        text = (
            "【执事登记】\n"
            "已登记入账。赎罪计划：每日步行 {daily} 分钟，预计 {days} 天完成。\n"
            "打卡方式：对执事说「打卡 60 分钟」。\n"
            "提醒：本庭会在每晚 22:00 询问你是否要下单，并在你的优惠券到期前 24 小时预警。"
        ).format(daily=daily, days=days)
        self.transcript.append(text)
        return text

    # -- 全自动 ------------------------------------------------------- #
    def run(self) -> str:
        parts = [
            self.stage_open(),
            self.stage_audit(),
            self.stage_defense(),
            self.stage_sentencing(),
            self.stage_verdict(),
            self.stage_registry(),
        ]
        return "\n\n".join(parts)


def s_quote(role: Role) -> str:
    return "「{}」".format(role.motto)


def _verdict_note(verdict: Verdict, summary: AuditSummary) -> str:
    if summary.total_gap >= 100:
        return ("你最大的问题不是吃，是白花钱。这一年你在麦当劳扔掉了 {:.0f} 元，"
                "够再吃 {} 顿。赎罪从学会用券开始。").format(
            summary.total_gap, int(summary.total_gap / max(summary.total_paid / max(len(summary.cases), 1), 1)))
    notes = {
        "逐出麦籍": "你与麦当劳的关系已超越消费，进入信仰范畴。遗憾的是，信仰不能抵扣卡路里。",
        "麦门叛徒": "数据不会说谎，你的账单比你的嘴诚实。",
        "黑袍常客": "有罪，但罪不至死。像大多数成年人一样：明知故犯，犯完再吃。",
        "白衣罪徒": "就这点份量，你甚至不好意思自称麦门信徒。不过万事开头难。",
    }
    return notes.get(verdict.rank, notes["白衣罪徒"])

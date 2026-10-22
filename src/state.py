"""罪恶账本：Agent 的长期记忆。

一个真正的 Agent 需要记住：判过哪些案、欠多少赎罪工时、打卡打到第几天。
本模块负责账本的持久化（JSON）与累计统计。

账本文件默认位于 data/ledger.json（已在 .gitignore 中排除，避免把个人消费记录提交）。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

DEFAULT_LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ledger.json"
)

LEDGER_VERSION = "2.0"


@dataclass
class CaseRecord:
    """账本里的一桩案子。"""

    case_no: str
    date: str                     # 判决日期 YYYY-MM-DD
    store: str
    kcal: int
    sin: float
    paid: float
    optimal: float
    gap: float
    penance_minutes: int
    done_minutes: int = 0
    verdict: str = ""             # 罪级
    order_id: str = ""

    @property
    def remaining(self) -> int:
        return max(self.penance_minutes - self.done_minutes, 0)

    @property
    def done_pct(self) -> float:
        if self.penance_minutes <= 0:
            return 100.0
        return round(min(self.done_minutes / self.penance_minutes * 100, 100), 1)


@dataclass
class Ledger:
    """罪恶账本。"""

    version: str = LEDGER_VERSION
    created_at: str = ""
    records: list[CaseRecord] = field(default_factory=list)
    checkins: list[dict] = field(default_factory=list)   # [{"date": "2026-10-22", "minutes": 30, "note": "夜跑"}]
    owner_note: str = ""

    # ------------------------------------------------------------------ #
    # 读写
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: str = DEFAULT_LEDGER_PATH) -> "Ledger":
        if not os.path.exists(path):
            ledger = cls(created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            return ledger
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        ledger = cls(
            version=raw.get("version", LEDGER_VERSION),
            created_at=raw.get("created_at", ""),
            checkins=raw.get("checkins", []),
            owner_note=raw.get("owner_note", ""),
        )
        ledger.records = [CaseRecord(**r) for r in raw.get("records", [])]
        return ledger

    def save(self, path: str = DEFAULT_LEDGER_PATH) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "version": self.version,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "owner_note": self.owner_note,
            "records": [asdict(r) for r in self.records],
            "checkins": self.checkins,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return path

    # ------------------------------------------------------------------ #
    # 记账
    # ------------------------------------------------------------------ #
    def add_case(self, *, store: str, kcal: int, sin: float, paid: float, optimal: float,
                 gap: float, penance_minutes: int, verdict: str, order_id: str = "",
                 on: str | None = None) -> CaseRecord:
        on = on or date.today().isoformat()
        seq = len(self.records) + 1
        record = CaseRecord(
            case_no="CASE-{:04d}".format(seq),
            date=on,
            store=store,
            kcal=int(kcal),
            sin=round(float(sin), 2),
            paid=round(float(paid), 2),
            optimal=round(float(optimal), 2),
            gap=round(float(gap), 2),
            penance_minutes=int(penance_minutes),
            verdict=verdict,
            order_id=order_id,
        )
        self.records.append(record)
        return record

    def add_checkin(self, minutes: int, note: str = "", on: str | None = None) -> dict:
        """登记一次赎罪打卡，按时间顺序抵扣最早未还清的案子。"""
        on = on or date.today().isoformat()
        entry = {"date": on, "minutes": int(minutes), "note": note}
        self.checkins.append(entry)

        left = int(minutes)
        for record in self.records:
            if left <= 0:
                break
            if record.remaining <= 0:
                continue
            take = min(left, record.remaining)
            record.done_minutes += take
            left -= take
        return entry

    # ------------------------------------------------------------------ #
    # 累计
    # ------------------------------------------------------------------ #
    @property
    def total_sin(self) -> float:
        return round(sum(r.sin for r in self.records), 2)

    @property
    def total_kcal(self) -> int:
        return sum(r.kcal for r in self.records)

    @property
    def total_paid(self) -> float:
        return round(sum(r.paid for r in self.records), 2)

    @property
    def total_gap(self) -> float:
        return round(sum(r.gap for r in self.records), 2)

    @property
    def total_penance(self) -> int:
        return sum(r.penance_minutes for r in self.records)

    @property
    def total_done(self) -> int:
        return sum(r.done_minutes for r in self.records)

    @property
    def outstanding(self) -> int:
        return max(self.total_penance - self.total_done, 0)

    @property
    def done_pct(self) -> float:
        if self.total_penance <= 0:
            return 100.0
        return round(min(self.total_done / self.total_penance * 100, 100), 1)

    @property
    def streak_days(self) -> int:
        """连续打卡天数（从今天或昨天往前数）。"""
        if not self.checkins:
            return 0
        days = sorted({c["date"] for c in self.checkins}, reverse=True)
        today = date.today()
        latest = date.fromisoformat(days[0])
        if (today - latest).days > 1:
            return 0
        streak = 1
        cursor = latest
        for d in days[1:]:
            cur = date.fromisoformat(d)
            if (cursor - cur).days == 1:
                streak += 1
                cursor = cur
            elif cur == cursor:
                continue
            else:
                break
        return streak

    def summary(self) -> dict:
        return {
            "cases": len(self.records),
            "total_sin": self.total_sin,
            "total_kcal": self.total_kcal,
            "total_paid": self.total_paid,
            "total_gap": self.total_gap,
            "penance_total": self.total_penance,
            "penance_done": self.total_done,
            "outstanding": self.outstanding,
            "done_pct": self.done_pct,
            "streak_days": self.streak_days,
            "checkin_count": len(self.checkins),
        }

    def recent_cases(self, n: int = 5) -> list[CaseRecord]:
        return self.records[-n:][::-1]

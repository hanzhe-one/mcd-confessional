"""麦门热量圣经：解析麦当劳 MCP 返回的营养成分数据，并提供餐品名 -> 热量 的模糊匹配。

数据来源：MCP 工具 list-nutrition-foods（返回为一段类 CSV 文本），
首次调用后会缓存到本地，离线演示模式则直接使用仓库内置基线文件。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

BASELINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "nutrition_baseline.txt",
)

_ROW_RE = re.compile(r"^\s*([^,]+),(.*?),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\s*$")

_BRACKETS = str.maketrans("", "", "()（）")

# 同义词映射：真实订单里的商品名与营养表的标准名常常对不上
# （实测：订单叫「柠檬蛋奶风味双旋圆筒」，营养表叫「圆筒冰淇淋」）。
# 顺序从具体到宽泛，命中即取。
_ALIASES: list[tuple[str, str]] = [
    ("柠檬蛋奶", "圆筒冰淇淋"),
    ("双旋", "圆筒冰淇淋"),
    ("圆筒", "圆筒冰淇淋"),
    ("甜筒", "圆筒冰淇淋"),
    ("麦旋风", "奥利奥麦旋风"),
    ("新地", "朱古力新地"),
    ("麦辣鸡腿", "麦辣鸡腿汉堡"),
    ("板烧", "板烧鸡腿堡"),
    ("不素之霸", "不素之霸双层牛堡"),
    ("安格斯", "芝士安格斯厚牛堡"),
    ("麦香鱼", "麦香鱼"),
    ("麦香鸡", "麦香鸡"),
    ("麦乐鸡", "麦乐鸡5块"),
    ("鸡翅", "麦辣鸡翅-2块"),
    ("鸡排", "那么大鸡排"),
    ("鸡球", "麦麦趣鸡球"),
    ("薯饼", "脆薯饼"),
    ("油条", "脆香油条"),
    ("玉米杯", "小杯玉米杯"),
    ("香芋派", "香芋派"),
    ("菠萝派", "菠萝派"),
    ("红茶", "锡兰红茶"),
    ("豆浆", "优品豆浆中杯"),
    ("牛奶", "纯牛奶（盒装）"),
    ("苹果汁", "100%苹果汁"),
    ("苹果片", "苹果片"),
    ("薯条", "中薯条"),
    ("可乐", "可乐中杯"),
    ("雪碧", "雪碧中杯"),
    ("咖啡", "大杯鲜萃咖啡"),
]


@dataclass
class Food:
    name: str
    kcal: int
    protein: int = 0
    fat: int = 0
    carb: int = 0


def parse_nutrition_text(text: str) -> list[Food]:
    """解析 list-nutrition-foods 返回的文本为 Food 列表。

    格式形如::

        [160]{productName,...,energyKcal,...}:
          巨无霸,null,2146,513,27,26,42,961,171
    """
    foods: list[Food] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        m = _ROW_RE.match(line)
        if not m:
            continue
        try:
            foods.append(
                Food(
                    name=m.group(1).strip(),
                    kcal=int(m.group(4)),
                    protein=int(m.group(5)),
                    fat=int(m.group(6)),
                    carb=int(m.group(7)),
                )
            )
        except ValueError:
            continue
    return foods


class NutritionTable:
    """餐品名 -> 热量 查询表，带最长匹配模糊查找。"""

    def __init__(self, foods: list[Food]) -> None:
        self._foods = foods
        self._by_name = {f.name: f for f in foods}

    @classmethod
    def from_text(cls, text: str) -> "NutritionTable":
        return cls(parse_nutrition_text(text))

    @classmethod
    def from_baseline(cls, path: str | None = None) -> "NutritionTable":
        with open(path or BASELINE_PATH, encoding="utf-8") as fh:
            return cls.from_text(fh.read())

    def __len__(self) -> int:
        return len(self._foods)

    def exact(self, name: str) -> Food | None:
        return self._by_name.get(name)

    @staticmethod
    def _normalize(name: str) -> str:
        """归一化餐品名：去掉括号字符，'可乐(中杯)' -> '可乐中杯'。"""
        return name.translate(_BRACKETS)

    def find(self, name: str) -> Food | None:
        """模糊匹配订单里的餐品名。

        订单里的商品名常常带规格后缀（如"麦辣鸡腿汉堡(中)"、"可乐(大杯)"），
        策略：先精确，再归一化（去括号）精确，最后互相包含，取最长匹配者。
        """
        if not name:
            return None
        hit = self.exact(name)
        if hit:
            return hit

        norm = self._normalize(name)
        hit = self.exact(norm)
        if hit:
            return hit

        candidates = [f for f in self._foods if f.name in name or name in f.name]
        if not candidates:
            candidates = [f for f in self._foods if self._normalize(f.name) in norm or norm in self._normalize(f.name)]
        if not candidates:
            # 兜底：去掉括号内容再试一次
            cleaned = re.sub(r"[（(].*?[)）]", "", name)
            candidates = [f for f in self._foods if f.name in cleaned or cleaned in f.name]
        if not candidates:
            # 最后一步：同义词映射（真实订单的商品名与营养表命名差异很大）
            for keyword, target in _ALIASES:
                if keyword in name:
                    hit = self.exact(target)
                    if hit:
                        return hit
            return None
        return max(candidates, key=lambda f: len(f.name))

    def kcal_of(self, name: str) -> tuple[int, Food | None]:
        """返回 (热量, 匹配到的条目)。未匹配到时热量按 0 计并返回 None。"""
        food = self.find(name)
        return (food.kcal if food else 0, food)

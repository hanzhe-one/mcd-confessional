"""演示数据：一份虚构的"重度罪徒"档案 + 菜单价 + 券池。

⚠️ 全部为虚构数据，仅用于展示报告效果；接入 MCP 后展示的是你自己的真实罪状。
菜单价为演示快照，真实价格以麦当劳门店实时返回为准。
"""

from __future__ import annotations

from .optimizer import Coupon

# --------------------------------------------------------------------- #
# 菜单价（演示快照）
# --------------------------------------------------------------------- #
DEMO_MENU: dict[str, float] = {
    "麦辣鸡腿汉堡": 22.0,
    "巨无霸": 25.0,
    "板烧鸡腿堡": 21.0,
    "麦香鱼": 20.0,
    "不素之霸双层牛堡": 27.0,
    "中薯条": 12.0,
    "大薯条": 16.0,
    "小薯条": 10.5,
    "麦乐鸡5块": 13.0,
    "那么大鸡排": 19.0,
    "麦辣鸡翅-2块": 13.5,
    "脆薯饼": 8.0,
    "香芋派": 7.5,
    "可乐(中杯)": 10.0,
    "可乐大杯": 11.0,
    "雪碧(大杯)": 11.0,
    "无糖可口可乐(大杯)": 11.0,
    "热朱古力(中杯)": 12.0,
    "奥利奥麦旋风": 13.5,
    "圆筒冰淇淋": 4.0,
    "小杯玉米杯": 9.0,
    "锡兰红茶": 10.0,
}

# --------------------------------------------------------------------- #
# 当前券池（审计"本该花多少"的依据）
# --------------------------------------------------------------------- #
DEMO_COUPONS: list[Coupon] = [
    Coupon("c1", "11.9元麦辣鸡腿堡", "discount", price=11.9, target="麦辣鸡腿堡"),
    Coupon("c2", "巨无霸券价 19.9", "discount", price=19.9, target="巨无霸"),
    Coupon("c3", "中薯买一送一", "discount", price=6.0, target="中薯条", max_qty=2),
    Coupon("c4", "满 35 减 7", "threshold", threshold=35, discount=7),
    Coupon("c5", "满 60 减 15", "threshold", threshold=60, discount=15),
]

# 卡包券文本（与 MCP query-my-coupons 返回格式对齐，供告解室解析"赦免凭证"）
DEMO_COUPON_TEXT = """# 您的优惠券列表

## 11.9元麦辣鸡腿堡
- **优惠**: ¥11.9 (用券价格)
- **有效期**: 2026-10-19 10:30-2026-10-23 23:59

## 19.9元王牌炸鸡任选2
- **优惠**: ¥19.9 (用券价格)
- **有效期**: 2026-10-19 10:30-2026-10-23 23:59
"""

# --------------------------------------------------------------------- #
# 虚构订单档案（含全价买单、券用一半、零亏损三类样本）
# --------------------------------------------------------------------- #
DEMO_ORDERS = [
    {
        "orderId": "DEMO-2025-0001",
        "createTime": "2025-11-05 12:31:05",
        "storeName": "广州天河城餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "44",
        "orderProductList": [
            {"productCode": "D01", "productName": "麦辣鸡腿汉堡", "quantity": 1},
            {"productCode": "D02", "productName": "中薯条", "quantity": 1},
            {"productCode": "D03", "productName": "可乐(中杯)", "quantity": 1},
        ],
    },
    {
        "orderId": "DEMO-2025-0002",
        "createTime": "2025-12-12 23:47:12",
        "storeName": "深圳南山科技园餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "52",
        "orderProductList": [
            {"productCode": "D04", "productName": "巨无霸", "quantity": 2},
            {"productCode": "D05", "productName": "麦乐鸡5块", "quantity": 1},
            {"productCode": "D06", "productName": "大薯条", "quantity": 1},
        ],
    },
    {
        "orderId": "DEMO-2026-0001",
        "createTime": "2026-01-16 01:12:44",
        "storeName": "上海静安大融城餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "39",
        "orderProductList": [
            {"productCode": "D07", "productName": "板烧鸡腿堡", "quantity": 1},
            {"productCode": "D08", "productName": "香芋派", "quantity": 2},
            {"productCode": "D09", "productName": "热朱古力(中杯)", "quantity": 1},
        ],
    },
    {
        "orderId": "DEMO-2026-0002",
        "createTime": "2026-03-19 19:05:31",
        "storeName": "北京朝阳大悦城餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "122",
        "orderProductList": [
            {"productCode": "D10", "productName": "不素之霸双层牛堡", "quantity": 2},
            {"productCode": "D11", "productName": "那么大鸡排", "quantity": 1},
            {"productCode": "D12", "productName": "奥利奥麦旋风", "quantity": 2},
            {"productCode": "D13", "productName": "雪碧(大杯)", "quantity": 2},
        ],
    },
    {
        "orderId": "DEMO-2026-0003",
        "createTime": "2026-05-29 15:22:08",
        "storeName": "成都春熙路餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "4",
        "orderProductList": [
            {"productCode": "D14", "productName": "圆筒冰淇淋", "quantity": 1},
        ],
    },
    {
        "orderId": "DEMO-2026-0004",
        "createTime": "2026-08-14 22:58:50",
        "storeName": "杭州西湖银泰餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "33",
        "orderProductList": [
            {"productCode": "D15", "productName": "麦辣鸡翅-2块", "quantity": 1},
            {"productCode": "D16", "productName": "脆薯饼", "quantity": 2},
            {"productCode": "D17", "productName": "无糖可口可乐(大杯)", "quantity": 1},
        ],
    },
    {
        "orderId": "DEMO-2026-0005",
        "createTime": "2026-10-04 11:30:19",
        "storeName": "武汉江汉路餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "39",
        "orderProductList": [
            {"productCode": "D18", "productName": "麦香鱼", "quantity": 1},
            {"productCode": "D19", "productName": "小杯玉米杯", "quantity": 1},
            {"productCode": "D20", "productName": "锡兰红茶", "quantity": 1},
        ],
    },
]

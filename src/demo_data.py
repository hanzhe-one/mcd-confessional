"""演示数据：一份虚构的"重度罪徒"档案，用于无 Token 的离线演示。

⚠️ 以下数据均为虚构，仅用于展示报告效果；接入 MCP 后展示的是你自己的真实罪状。
"""

DEMO_ORDERS = [
    {
        "orderId": "DEMO-2025-0001",
        "createTime": "2025-11-07 12:31:05",
        "storeName": "广州天河某餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "23.5",
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
        "realTotalAmount": "36",
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
        "realTotalAmount": "58.5",
        "orderProductList": [
            {"productCode": "D07", "productName": "板烧鸡腿堡", "quantity": 1},
            {"productCode": "D08", "productName": "香芋派", "quantity": 2},
            {"productCode": "D09", "productName": "热朱古力(中杯)", "quantity": 1},
        ],
    },
    {
        "orderId": "DEMO-2026-0002",
        "createTime": "2026-03-20 19:05:31",
        "storeName": "北京朝阳大悦城餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "108",
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
        "storeName": "杭州西湖餐厅",
        "orderStatus": "订单已完成",
        "realTotalAmount": "45",
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
        "realTotalAmount": "29.9",
        "orderProductList": [
            {"productCode": "D18", "productName": "麦香鱼", "quantity": 1},
            {"productCode": "D19", "productName": "小杯玉米杯", "quantity": 1},
            {"productCode": "D20", "productName": "锡兰红茶", "quantity": 1},
        ],
    },
]

DEMO_COUPONS = [
    {"name": "11.9元麦辣鸡腿堡", "expire": "2026-10-23 23:59"},
    {"name": "19.9元王牌炸鸡任选2", "expire": "2026-10-23 23:59"},
]

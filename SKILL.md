---
name: mcd-confessional
summary: 麦门告解室：拉取麦当劳历史订单，生成《年度罪状报告》与可分享的告解证书
read_when:
  - 用户想生成麦当劳年度罪状报告/告解证书
  - 用户提到麦门、麦当劳订单审判、卡路里忏悔、赎罪工时
  - 用户要求分析自己的麦当劳消费历史
---

# 麦门告解室 · McDonald's Confessional

> “孩子，坐。让本席看看你这一年都在麦当劳犯了些什么事。”

一个基于麦当劳 MCP 的整活 Skill：把历史订单翻译成教廷术语，生成《年度罪状报告》
（Markdown）和一张适合截图传教的《告解证书》（HTML）。

## 触发场景

- “生成我的麦当劳年度罪状报告”
- “看看我在麦当劳犯了多少罪”
- “麦门告解室” / “告解证书”

## 前置条件

1. 已申请麦当劳 MCP Token（mcp.mcd.cn 控制台）。
2. 已配置 MCP 连接器（参考仓库内 `mcp-config.example.json`，Token 用环境变量
   `MCD_MCP_TOKEN`，切勿硬编码）。

## 执行方式

### 方式 A：命令行（推荐，完整报告）

```bash
# 演示模式（无需 Token，内置虚构档案，先看效果）
python -m src.cli demo

# 正式模式（调用 MCP，对真实订单宣判）
MCD_MCP_TOKEN=xxxx python -m src.cli confess
```

输出：

- `examples/sin-report.md` —— 年度罪状报告（案情录 + 量刑 + 判决 + 神父批注）
- `examples/confession-certificate.html` —— 告解证书（浏览器打开后截图即传教）

### 方式 B：在 WorkBuddy 对话中（无需本地环境）

按以下步骤操作：

1. 调用 MCP 工具 `order-list` 拉取历史订单；
2. 调用 MCP 工具 `list-nutrition-foods` 获取热量圣经（若本地已有
   `data/nutrition_baseline.txt` 可跳过）；
3. 调用 MCP 工具 `query-my-coupons` 获取卡包赦免凭证；
4. 调用 MCP 工具 `now-time-info` 获取判决时间；
5. 按 `src/sin_ledger.py` 的罪律逐单判罪并汇总：
   - 罪恶点 = 千卡 × 0.1
   - 深夜（22:00–05:00）×2，周五 ×1.2，实付 ≤5 元 ×0.5，实付 ≥100 元 ×1.5，
     同款 ≥3 件 ×1.3，含无糖 ×0.9
   - 罪级：<50 白衣罪徒 / 50–199 黑袍常客 / 200–499 麦门叛徒 / ≥500 逐出麦籍
   - 赎罪工时 = 千卡 × 3 分钟；每张赦免券抵 5%（上限 40%）
6. 按 `src/report.py` 的文书格式输出报告，语气保持“毒舌又慈悲的麦门告解师”。

## 注意事项

- 报告仅供娱乐，不构成营养或医疗建议；餐品信息以麦当劳官方渠道为准。
- 项目为非官方二创，“麦门”为玩家社区爱称，输出文案不得贬损品牌形象。
- 卡包券解析尽力而为（MCP 返回为文本），解析失败不影响主流程。

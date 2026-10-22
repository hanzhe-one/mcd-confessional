# 麦门告解室 · McDonald's Confessional ⛪🍟

> “孩子，坐。让本席看看你这一年都在麦当劳犯了些什么事。”

一个基于 **麦当劳 MCP** 的整活 Skill：拉取你的历史订单，把每一顿翻译成教廷术语，
生成一份《**年度罪状报告**》和一张可以截图传教的《**告解证书**》。

不是卡路里计算器——计算器只会告诉你数字，告解室会审判你。

## 玩法一览

- **罪恶账户**：每笔订单按热量计“罪恶点”，深夜下单罪加一等、单人过百暴食罪、同款三件起算贪、选无糖将功补过
- **罪级判定**：白衣罪徒 → 黑袍常客 → 麦门叛徒 → 逐出麦籍（死罪）
- **赎罪工时**：按步行消耗换算，精确到“你还欠麦当劳多少路”
- **官方赦免**：拉取你卡包里**真实的**优惠券，每张抵扣 5% 赎罪工时（上限 40%）——赦免凭证明天过期？那正好是审判日
- **神父批注**：告解师根据你的罪级附耳语，毒舌但慈悲

## 效果预览

克隆仓库后无需任何配置即可体验：

```bash
python -m src.cli demo
```

打开 `examples/confession-certificate.html`，你就能看到一张盖着“麦门告解”红印的证书：

```
┌──────────────────────────────┐
│  麦 门 告 解 室      [麦门    │
│  年度告解证书         告解]  │
│                              │
│  作案次数        7 单         │
│  累计摄入热量    6731 千卡    │
│  累计罪恶点      1251.78      │
│  罪级判定    逐出麦籍（死罪） │
│  须步行赎罪      约 13.5 天   │
│         · 官方赦免凭证 ·       │
└──────────────────────────────┘
```

`examples/sin-report.md` 则是完整文书：案情录（每一单的时间/门店/涉案物品/量刑情节）、
量刑摘要、终审判决、告解师批注。

## 快速开始

### 1. 申请 MCP Token

前往 [mcp.mcd.cn](https://mcp.mcd.cn) 用手机号登录，在控制台点击“激活”申请 MCP Token。

### 2. 配置（两种方式）

**WorkBuddy 用户**：左侧边栏【专家·技能·连接器】→【连接器】→【自定义连接器】→【配置MCP】，
填入仓库内 `mcp-config.example.json` 的内容（Token 用环境变量 `MCD_MCP_TOKEN` 占位）。

**本地命令行**：

```bash
git clone https://github.com/<你的用户名>/mcd-confessional.git
cd mcd-confessional
export MCD_MCP_TOKEN=你的Token        # Windows PowerShell: $env:MCD_MCP_TOKEN="你的Token"
python -m src.cli confess             # 对真实订单宣判
```

> 无 Token 也能玩：`python -m src.cli demo`（内置虚构罪徒档案）

### 3. 截图，传教

打开 `examples/confession-certificate.html`，截图分享。深夜犯罪率超过 50% 的朋友，
建议直接打印报告贴在冰箱门上。

## 技术要点

- **零第三方依赖**：纯 Python 标准库，`mcp_client.py` 自行实现了 MCP streamablehttp 协议（initialize / tools/call）
- **麦门热量圣经**：`data/nutrition_baseline.txt` 内置 160+ 餐品营养数据（来自 MCP `list-nutrition-foods`），订单餐品名带括号规格（如“可乐(中杯)”）也能模糊匹配
- **罪律引擎**：`src/sin_ledger.py`，全部量刑规则透明可改——不同意本席的判决？提 PR
- **文书生成**：`src/report.py`，Markdown 报告 + HTML 证书

## 目录结构

```
mcd-confessional/
├── SKILL.md                    # WorkBuddy Skill 定义
├── src/
│   ├── cli.py                  # 命令行入口（demo / confess）
│   ├── mcp_client.py           # 麦当劳 MCP 最小客户端（标准库实现）
│   ├── nutrition_table.py      # 热量圣经解析与模糊匹配
│   ├── sin_ledger.py           # 罪律引擎
│   ├── report.py               # 罪状报告 / 告解证书生成
│   └── demo_data.py            # 虚构演示档案
├── data/
│   └── nutrition_baseline.txt  # 内置营养数据
├── examples/
│   ├── sin-report.md           # 报告示例
│   └── confession-certificate.html  # 证书示例
├── MCP_INTEGRATION.md          # MCP 集成说明
├── mcp-config.example.json     # 脱敏配置示例
└── CONTEST_DECLARATION.md      # 参赛声明
```

## 免责声明

本项目为麦当劳程序员创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
项目输出仅供娱乐，不构成医疗、营养或其他专业建议；餐品信息、价格及供应状态以麦当劳
官方渠道的实时结果为准。“麦门”为玩家社区爱称，本项目不贬损任何品牌形象。

---

*以代码之名，行审判之实。*

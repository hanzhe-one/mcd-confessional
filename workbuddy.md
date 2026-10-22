# WorkBuddy 开发记录

> 本文件用于参加“麦当劳程序员创意开发大赛”WorkBuddy 专项奖励核验，
> 记录本项目在腾讯 WorkBuddy 中的开发过程与对话上下文。

## 项目在 WorkBuddy 中的开发方式

本项目全程在 **腾讯 WorkBuddy** 中开发，典型工作流：

1. **选题与规则确认**：在 WorkBuddy 对话中读取比赛仓库 `activityGuidelines.md`
   与 `README.md`，确认参赛要求（必须文件、MCP 真实性要求、排名规则）。
2. **MCP 联调**：WorkBuddy 已通过自定义连接器接入麦当劳 MCP（mcd-mcp），
   在对话中直接调用 `order-list`、`list-nutrition-foods`、`query-my-coupons`、
   `now-time-info` 等工具，验证返回数据结构后编写解析代码。
3. **代码生成与调试**：由 WorkBuddy 生成 `src/` 全部代码（mcp_client、
   nutrition_table、sin_ledger、report、cli、demo_data），在本地运行
   `python -m src.cli demo` 验证，根据报错迭代修复（如格式串占位符不匹配、
   餐品名括号规格匹配失败等）。
4. **产物打磨**：罪状报告 Markdown 模板、告解证书 HTML 样式、神父批注文案
   均在对话中迭代完成。

## 使用的 WorkBuddy 能力

- **自定义连接器 / MCP 配置**：接入麦当劳 MCP Server 并真实调用其工具
- **对话式开发**：需求描述 → 代码生成 → 报错修复 → 文档产出的完整闭环
- **Skill 沉淀**：项目同时以 WorkBuddy Skill（`SKILL.md`）形态发布，
  其他 WorkBuddy 用户安装后可在对话中直接生成麦当劳年度罪状报告

## 联动说明

- Skill 安装路径：将本仓库作为 Skill 目录加载（或复制 `SKILL.md` 与 `src/`
  至 WorkBuddy 技能目录），即可在对话框中触发“麦门告解室”。
- 真实使用麦当劳 MCP + 真实使用腾讯 WorkBuddy 两项条件均已满足，
  特此提交本文件供核验。

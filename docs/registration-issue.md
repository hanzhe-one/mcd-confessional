# 报名 Issue 文案（草稿）

> 提交位置：活动仓库 https://github.com/M-China/mcd-developer-innovation-challenge 的 Issues
> ⚠️ 官方提醒：报名 Issue 的【标题】和【正文】之间暂不要使用换行符；
> 【项目简介】和【项目简介内容】之间也不要换行；项目地址链接不要用 Markdown 格式。

---

## 复制以下内容发布 Issue

**标题：**

```
【参赛申请】麦门告解室：基于麦当劳 MCP 的年度罪状报告生成器
```

**正文：**

```
【参赛申请】
项目名称：麦门告解室 · McDonald's Confessional
项目地址：https://github.com/你的GitHub用户名/mcd-confessional
项目简介：拉取麦当劳历史订单，按热量与量刑规则逐单判罪：深夜下单罪加一等、单人过百暴食罪、同款三件起算贪、选无糖将功补过，累计罪恶点判定罪级（白衣罪徒到逐出麦籍），并换算步行赎罪工时；卡包内真实优惠券作为"官方赦免"抵扣赎罪工时，赦免券过期即赦免失效。一键生成《年度罪状报告》与可截图分享的《告解证书》。零第三方依赖，标准库实现麦当劳 MCP streamablehttp 客户端，同时以 WorkBuddy Skill 形态发布。
```

---

## 提交前检查清单

- [ ] 仓库已 push 到 GitHub 且为 **Public**
- [ ] 仓库创建时间在 2025-12-25 ~ 2026-10-25 之间（今天新建即满足）
- [ ] `CONTEST_DECLARATION.md` 与官方原文完全一致（未改动）
- [ ] `README.md` / `MCP_INTEGRATION.md` / `mcp-config.example.json` / `workbuddy.md` 均在
- [ ] `mcp-config.example.json` 中只有环境变量占位符，无真实 Token
- [ ] 已在 2026-10-25 23:59（北京时间）前提交报名 Issue
- [ ] 报名后查看 Issue 回复确认"报名成功"

## Push 命令参考（在仓库目录执行）

```bash
cd /c/Users/Administrator/Desktop/Fork/mcd-confessional
git remote add origin https://github.com/你的GitHub用户名/mcd-confessional.git
git push -u origin main
```

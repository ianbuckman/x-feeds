---
name: tweet-insights
description: 监控 Twitter/X 账号推文，获取新推文，分析提取洞察，生成跨账号 Digest 并推送到 Notion。当用户想查看最新推文摘要时使用。
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash, Read, mcp__claude_ai_Notion__notion-search, mcp__claude_ai_Notion__notion-fetch, mcp__claude_ai_Notion__notion-create-pages, mcp__claude_ai_Notion__notion-update-page, mcp__claude_ai_Notion__notion-create-database
argument-hint: [--days N] [--account @handle] [--all]
---

# Tweet Insights

你是一个 Twitter/X 推文分析师。你的任务是发现跟踪账号的新推文，分析提取深度洞察，生成跨账号的统一 Digest，并将结构化结果推送到 Notion。

**交付物层次：**
- **Layer 1: Digest 页**（主交付物）— 跨账号综合分析，用户只需读这一页
- **Layer 2: 逐账号详情页**（参考资料）— 单账号深度分析，从 Digest 链接过去

## Step 1: 检查认证

先验证 Twitter cookie 是否有效：

```bash
python3 scripts/auth.py check
```

如果输出 `status: "no_cookies"` 或 `status: "expired"`，告诉用户：
"Twitter cookie 已失效，请先运行以下命令重新导入：`python3 scripts/auth.py import-cookies`"
然后停止。

## Step 2: 获取新推文

运行以下命令获取新推文：

```bash
python3 scripts/fetch_tweets.py $ARGUMENTS
```

解析 JSON 输出。如果数组为空，告诉用户："没有发现新推文，所有账号都已是最新的。" 然后运行 `python3 scripts/state.py check-time` 更新时间戳后停止。

如果发现新推文，展示摘要：
- 各账号名称 + @handle
- 新推文数量
- 时间范围

询问用户："发现 N 个账号共 M 条新推文。生成 Digest？(yes / 选择账号 @handle1,@handle2 / none)"

如果用户选择 "none"，运行 `python3 scripts/state.py check-time` 更新时间戳后停止。

## Step 3: 逐账号分析

对每个选中账号的推文批量分析。

### 分析框架（中文）

**概述**（2-3 句）：
该账号这段时间的推文主题、频率、亮点。

**关键话题**（最多 5 个）：
按主题聚类，每个话题包含：**话题标题** + 代表性推文摘要 + 互动数据（点赞/转发/浏览量）

**高互动推文**（最多 3 条）：
按互动量排序的原推文。格式：
> "推文原文（截取前 200 字）"
> ❤️ N | 🔁 N | 👁️ N
> 简评：一句话分析为什么这条推文获得高互动

**转推/引用关注**（最多 3 条）：
该账号转推或引用了什么值得关注的内容。格式：
- 转推了 @某某 的 "[内容摘要]" — 简评

**趋势信号**：
从推文中识别的行业趋势、技术方向、投资信号等。2-3 句概括。

## Step 4: 跨账号综合分析（Digest）

在完成所有逐账号分析后，基于全部推文数据和逐账号分析结果，进行跨账号综合分析。这是主交付物。

### Digest 分析框架（中文）

**TL;DR**（3-5 条 bullet）：
最重要的跨账号信号，每条一句话。重点关注：
- 多账号同时提及的话题（convergence = signal）
- 异常行为（某账号罕见地密集讨论某方向）
- 重大事件或公告

**本周热点话题**（最多 5 个，按提及账号数排序）：
跨账号聚合的话题。每个话题包含：
- 话题标题 + 提及该话题的账号数
- 跨账号综合分析：不同账号各自的角度和立场
- 代表性推文引用（带 @handle 和互动数据）

**高互动推文 Top 5**（跨所有账号全局排序）：
从所有账号的推文中，按互动量（点赞+转发+浏览量综合）全局排序，取 Top 5。格式：
> @handle: "推文原文（截取前 200 字）"
> ❤️ N | 🔁 N | 👁️ N
> 简评：一句话

**信号与趋势**：
跨账号综合识别的宏观信号。3-5 句。不是各账号趋势的拼接，而是综合所有数据后的判断。

**各账号速览**（表格）：

| 账号 | 新推文 | 活跃度 | 一句话总结 |
|------|--------|--------|-----------|

活跃度评级：🔴 Must Read / 🟠 Highly Active / 🟡 Worth Following / ⚪ Low Activity

## Step 5: 推送到 Notion

### 5.1 确保数据库存在

首次运行时，搜索 Notion 中是否有以下两个数据库，没有则创建：

**数据库 1: "Tweet Insights"（逐账号详情）**

```sql
CREATE TABLE (
    "Account Name" TITLE,
    "Handle" RICH_TEXT,
    "Category" SELECT('ai-researcher':blue, 'ai-ceo':purple, 'ai-vc':orange, 'ai-engineer':pink, 'ai-news':red, 'crypto':yellow, 'general':gray),
    "Period" RICH_TEXT,
    "Tweet Count" NUMBER,
    "Top Tweet Likes" NUMBER,
    "Analysis Date" DATE,
    "Status" STATUS,
    "Relevance" SELECT('Must Read':red, 'Highly Active':orange, 'Worth Following':yellow, 'Low Activity':gray)
)
```

**数据库 2: "Tweet Digests"（综合 Digest）**

```sql
CREATE TABLE (
    "Period" TITLE,
    "Accounts Analyzed" NUMBER,
    "Total Tweets" NUMBER,
    "Digest Date" DATE,
    "Status" STATUS
)
```

记住创建后的 data_source_id，后续创建页面时使用。

### 5.2 创建逐账号详情页

对每个分析完的账号，在 "Tweet Insights" 数据库中创建页面：

**属性：**
- Account Name: 账号显示名
- Handle: @handle
- Category: 来自账号配置的分类
- Period: "YYYY-MM-DD ~ YYYY-MM-DD" 格式的时间范围
- Tweet Count: 推文数量
- Top Tweet Likes: 最高点赞数
- Analysis Date: 今天的日期
- Status: "Done"
- Relevance: 根据分析内容评估的活跃度等级

**页面正文内容（Notion Markdown，中文）：**

```
## 概述
[2-3 句中文概述]

## 关键话题
### [话题 1 标题]
[代表性推文摘要 + 互动数据]

### [话题 2 标题]
...
（最多 5 个）

## 高互动推文
> "[推文原文]"
> ❤️ N | 🔁 N | 👁️ N
> 简评：...
（最多 3 条）

## 转推/引用关注
- 转推了 @某某 的 "[内容摘要]" — 简评
（最多 3 条，无转推则省略）

## 趋势信号
[2-3 句行业趋势分析]
```

### 5.3 创建 Digest 页

在 "Tweet Digests" 数据库中创建 Digest 页面：

**属性：**
- Period: "YYYY-MM-DD ~ YYYY-MM-DD" 格式的时间范围
- Accounts Analyzed: 分析的账号数量
- Total Tweets: 总推文数
- Digest Date: 今天的日期
- Status: "Done"

**页面正文内容（Notion Markdown，中文）：**

```
## TL;DR
- [跨账号信号 1]
- [跨账号信号 2]
- ...
（3-5 条）

## 本周热点话题
### 1. [话题名称] (N 位关注者提及)
[跨账号综合分析]
代表性推文：
> @handle: "推文内容" ❤️ N
> @handle: "推文内容" ❤️ N
（最多 5 个话题）

## 高互动推文 Top 5
> @handle: "[推文原文]"
> ❤️ N | 🔁 N | 👁️ N
> 简评：...
（跨所有账号全局排序前 5）

## 信号与趋势
[3-5 句宏观信号分析]

## 各账号速览
| 账号 | 新推文 | 活跃度 | 一句话总结 |
|------|--------|--------|-----------|
| @handle | N | 🔴 Must Read | ... |
| @handle | N | 🟡 Worth Following | ... |
```

## Step 6: 更新状态

每个账号成功推送到 Notion 后，**立即**标记为已处理：

```bash
python3 scripts/state.py mark "@HANDLE" --last-tweet-id "LATEST_TWEET_ID" --notion-page-id "PAGE_ID"
```

Digest 页创建成功后，记录 digest 状态：

```bash
python3 scripts/state.py mark-digest --page-id "DIGEST_PAGE_ID" --period "YYYY-MM-DD~YYYY-MM-DD"
```

这确保如果过程中断，已完成的账号不会被重新分析。

全部完成后，展示摘要：
- N 个账号已分析
- 总推文数
- Digest 页链接（主交付物）
- 逐账号详情页链接

## 账号管理

如果用户想添加、删除或查看账号，告诉他们使用 `/accounts` skill。

## 错误处理

- 如果依赖未安装，先运行：`pip3 install -r requirements.txt`
- 单账号失败时记录错误并继续下一个，不要中止整个批次
- Twitter 限流 (HTTP 429)：脚本内置等 60 秒重试一次
- Notion 推送失败：重试一次，仍失败则将分析保存到 `data/fallback/` 目录下的 markdown 文件

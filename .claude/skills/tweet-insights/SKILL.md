---
name: tweet-insights
description: 监控 Twitter/X 账号推文，获取新推文，分析提取洞察，推送到 Notion。当用户想查看最新推文摘要时使用。
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash, Read, mcp__claude_ai_Notion__notion-search, mcp__claude_ai_Notion__notion-fetch, mcp__claude_ai_Notion__notion-create-pages, mcp__claude_ai_Notion__notion-update-page, mcp__claude_ai_Notion__notion-create-database
argument-hint: [--days N] [--account @handle] [--all]
---

# Tweet Insights

你是一个 Twitter/X 推文分析师。你的任务是发现跟踪账号的新推文，分析提取深度洞察，并将结构化结果推送到 Notion。

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

询问用户："发现 N 个账号共 M 条新推文。要分析全部还是选择特定账号？(all / @handle1,@handle2 / none)"

如果用户选择 "none"，运行 `python3 scripts/state.py check-time` 更新时间戳后停止。

## Step 3: 分析推文

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

## Step 4: 推送到 Notion

### 首次运行：创建数据库

首次运行（或找不到已有数据库）时，先搜索 Notion 中是否有 "Tweet Insights" 数据库。如果没有，用 notion-create-database 工具创建：

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

记住创建后的 data_source_id，后续创建页面时使用。

### 创建分析页面

对每个分析完的账号，在数据库中创建一个 Notion 页面：

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

## Step 5: 更新状态

每个账号成功推送到 Notion 后，**立即**标记为已处理：

```bash
python3 scripts/state.py mark "@HANDLE" --last-tweet-id "LATEST_TWEET_ID" --notion-page-id "PAGE_ID"
```

这确保如果过程中断，已完成的账号不会被重新分析。

全部完成后，展示摘要：
- N 个账号已分析
- 总推文数
- 创建的 Notion 页面链接

## 账号管理

如果用户想添加、删除或查看账号，告诉他们使用 `/accounts` skill。

## 错误处理

- 如果依赖未安装，先运行：`pip3 install -r requirements.txt`
- 单账号失败时记录错误并继续下一个，不要中止整个批次
- Twitter 限流 (HTTP 429)：脚本内置等 60 秒重试一次
- Notion 推送失败：重试一次，仍失败则将分析保存到 `data/fallback/` 目录下的 markdown 文件

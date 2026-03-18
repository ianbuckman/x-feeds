# Tweet Insights

Monitor Twitter/X accounts, fetch tweets, analyze with Claude, push insights to Notion.

## Quick Start

```bash
pip3 install -r requirements.txt
# 在浏览器中登录 Twitter/X，然后导入 cookie
python3 scripts/auth.py import-cookies --browser arc
# 运行 /tweet-insights 触发完整工作流
```

## Troubleshooting

### 2026-03-18 首次运行问题记录

本次执行过程中遇到了三个连锁问题，根因都与 twikit 库的维护停滞有关：

#### 1. Cookie 提取：默认浏览器不对

**现象**：`import-cookies` 不指定浏览器时默认从 Chrome 提取，只拿到 4 个 cookie，缺少关键的 `auth_token` 和 `ct0`。

**原因**：用户实际使用 Arc 浏览器登录 Twitter，Chrome 中没有有效的 Twitter session。

**修复**：指定浏览器参数 `--browser arc`，成功提取 26 个 cookie。

**预防**：始终使用 `--browser <你的浏览器>` 显式指定。支持的浏览器：chrome, arc, brave, edge, safari, chromium, opera, vivaldi。

#### 2. twikit "Couldn't get KEY_BYTE indices" 错误

**现象**：cookie 提取正确后，`auth.py check` 仍然报 `Couldn't get KEY_BYTE indices`。

**原因**：twikit 最后一次发布是 2025 年 2 月（v2.3.3），之后 X.com 改变了前端 webpack 打包格式：
- **旧格式**：`"ondemand.s": "HASH"` — twikit 的正则 `ON_DEMAND_FILE_REGEX` 能匹配
- **新格式**：`20113:"ondemand.s"` — chunk name 变成了 value 而非 key，hash 在另一个映射表里

twikit 解析 X.com 首页 HTML 找不到 `ondemand.s` 的 JS 文件 hash，无法生成 `X-Client-Transaction-Id` header，所有 API 请求都会失败。

**修复**：在 `scripts/auth.py` 中 monkey-patch 了 `ClientTransaction.get_indices`：
1. 先尝试 twikit 原始逻辑（兼容未来 twikit 修复后自动恢复）
2. 失败后用新正则 `(\d+):"ondemand\.s"` 找 chunk ID，再用 `CHUNK_ID:"([a-f0-9]{6,12})"` 找 hash
3. 拼接 URL 获取 JS 文件，用原始 `INDICES_REGEX` 提取 key byte indices
4. 网络请求加了 3 次重试（abs.twimg.com 连接有时不稳定）

**预防**：这个 patch 已经内置在 `auth.py` 中，所有通过 `from auth import get_client` 使用 twikit 的脚本都会自动应用。如果 X.com 再次改变格式，需要更新 `_patched_get_indices` 中的正则。

#### 3. 网络间歇性 ConnectError

**现象**：获取 `abs.twimg.com` 上的 JS 文件时偶发 `httpx.ConnectError`。

**原因**：X.com/twimg.com 的反爬机制或网络波动，短时间内多次请求可能被临时阻断。

**修复**：在 patch 中加入了最多 3 次重试，每次间隔 2 秒。

### twikit 库现状（截至 2026-03）

twikit 目前面临多个已知问题：
- 最后一次 PyPI 发布：2025-02-06 (v2.3.3)
- GitHub 有 125+ open issues
- Cloudflare 403 拦截和 Castle.io 反 bot 指纹识别影响部分用户
- 维护者活跃度下降

如果 twikit 未来彻底不可用，可考虑替代方案：
- [twscrape](https://github.com/vladkens/twscrape) — 积极维护的 Twitter scraper
- [twitter-openapi-python](https://github.com/trevorhobenshield/twitter-api-client) — 基于逆向 API

# Tweet Insights

盯着一堆 Twitter 账号看太累了。这个项目让 Claude 帮你看，然后把分析结果推到 Notion。

## 怎么用

在 Claude Code 里跑 `/tweet-insights` 就行。它会自动抓推文、分析、推 Notion。

第一次用之前装个依赖、导一下浏览器 cookie：

```bash
pip3 install -r requirements.txt
python3 scripts/auth.py import-cookies --browser arc
```

管理关注的账号用 `/accounts`。

## 踩过的坑

twikit 这个库已经快一年没更新了（最后一版 2025-02），但 X.com 前端一直在改，所以坑不少。

### Cookie 导入要指定浏览器

不加 `--browser` 会默认试 Chrome。如果你平时用 Arc / Brave / Edge 登的 Twitter，Chrome 里根本没有有效 cookie，导入完看着成功其实缺关键字段。**永远显式指定你的浏览器**。

### "Couldn't get KEY_BYTE indices"

这是目前最常见的报错。twikit 需要从 X.com 首页 HTML 里找一个 JS 文件来生成请求签名，但 X.com 改了 webpack 打包格式，twikit 的正则匹配不上了。

已经在 `scripts/auth.py` 里打了 monkey-patch 绕过去了，正常跑不会再遇到。如果哪天 X.com 又改格式导致这个错误复现，需要去更新 `_patched_get_indices` 里的正则。

### 偶发的网络超时

抓 X.com 的 JS 文件时偶尔会断连，patch 里已经加了自动重试，一般不用管。

### 如果 twikit 彻底挂了

考虑换到 [twscrape](https://github.com/vladkens/twscrape) 或 [twitter-openapi-python](https://github.com/trevorhobenshield/twitter-api-client)。

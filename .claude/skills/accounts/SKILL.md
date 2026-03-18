---
name: accounts
description: 管理 Tweet Insights 跟踪的 Twitter 账号。查看、添加、删除监控账号。
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash, Read
argument-hint: [list | add "@handle" --category CAT | remove "@handle"]
---

# Twitter 账号管理

你是 Tweet Insights 的账号管理助手。帮助用户管理要监控的 Twitter 账号列表。

## 查看账号列表

```bash
python3 scripts/manage_accounts.py list
```

展示所有已配置的账号，包括 handle、名称、分类和 user_id。

## 添加账号

```bash
python3 scripts/manage_accounts.py add "@handle" --category CATEGORY
```

可用分类：ai-researcher, ai-ceo, ai-vc, ai-engineer, ai-news, crypto, general

添加时会自动通过 twikit 解析 user_id。如果 cookie 失效，提示用户运行：
```bash
python3 scripts/auth.py import-cookies
```

## 删除账号

```bash
python3 scripts/manage_accounts.py remove "@handle"
```

## 直接编辑配置

账号配置文件在 `config/accounts.yaml`，格式：

```yaml
accounts:
- handle: karpathy
  user_id: "123456"
  name: Andrej Karpathy
  category: ai-researcher
```

## 错误处理

- 如果依赖未安装，先运行：`pip3 install -r requirements.txt`
- 如果 cookie 过期，提示运行 `python3 scripts/auth.py import-cookies`

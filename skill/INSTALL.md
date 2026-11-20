# 安装指南（给 AI 助手看的）

你正在为你的用户安装 **deal_hunter** 技能（GLOBAL DEAL HUNTER 羊毛查询：让用户用对话查询、筛选、收藏、标记、更新羊毛信息）。请按顺序执行以下步骤，不要跳步。

## 第 1 步：确定你的技能目录

找到你所在平台存放技能（skill）的目录——就是你平时加载 SKILL.md 的那个目录。如果你不确定，先询问用户；仍不确定时用 `~/.agents/skills/` 并把实际路径记下来，第 4 步要汇报。

## 第 2 步：下载技能文件

把下面两个文件下载到 `<你的技能目录>/deal_hunter/` 下（保持目录结构）：

| 目标文件 | 下载地址 |
| --- | --- |
| `deal_hunter/SKILL.md` | https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/skill/SKILL.md |
| `deal_hunter/scripts/gdh.py` | https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/skill/scripts/gdh.py |

参考命令（curl）：

```bash
mkdir -p <你的技能目录>/deal_hunter/scripts
curl -L -o <你的技能目录>/deal_hunter/SKILL.md https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/skill/SKILL.md
curl -L -o <你的技能目录>/deal_hunter/scripts/gdh.py https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/skill/scripts/gdh.py
```

若 raw.githubusercontent.com 访问失败，改用镜像（把地址前缀换成 `https://cdn.jsdelivr.net/gh/huluohu/global-deal-hunter-feed@main/skill/`，文件名不变）。

## 第 3 步：验证安装

运行（需要 Python 3.9+，无第三方依赖）：

```bash
python3 <你的技能目录>/deal_hunter/scripts/gdh.py status
```

期望返回 JSON：`"ok": true`、`"mode": "feed-local"`、`"count"` 为当前货架条数（数百条）。若报错，先检查网络与 Python 版本，不要谎报安装成功。

## 第 4 步：（可选）服务端模式

默认的货架模式已是全功能：查询、筛选、收藏、标记无效、提交线索、刷新都可用，标记与线索存在本机 `~/.config/gdh-cli/`，不需要任何账号。

只有当用户明确说自己部署了 GLOBAL DEAL HUNTER 看板（Docker 版）并想让标记与网页端互通时，才执行：

```bash
python3 <你的技能目录>/deal_hunter/scripts/gdh.py setup --base-url http://<用户看板地址>:3003 --username <用户名>
```

密码请让用户在本机终端交互输入，**不要在聊天里索要或记录密码明文**。用户没提看板就跳过这步，不要追问。

## 第 5 步：向用户汇报

告诉用户：①技能装在哪个目录；②第 3 步验证结果（当前模式与数据条数）；③三个示例问法——「看看最新羊毛」「3 天内有什么快过期的」「把这条收藏了」。此后按 `deal_hunter/SKILL.md` 的命令与呈现规则为用户服务。

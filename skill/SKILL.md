# GLOBAL DEAL HUNTER 智能查询（deal_hunter）

让用户通过对话让 agent 查询、筛选、标记、更新「GLOBAL DEAL HUNTER｜全球羊毛情报中心」的羊毛信息：找羊毛、按分类/地区/免费类型/价值/到期时间筛选、收藏、标记无效、提交新线索、触发数据更新。

底层工具是本技能自带的 `scripts/gdh.py`（纯 Python 标准库，无需安装任何依赖，Python 3.9+ 可运行）。所有命令输出 JSON（`--table` 为人类可读格式），agent 读 JSON 后组织成自然语言答复。

## 两种模式

- **服务端模式（完整功能）**：连接用户自托管的 Docker 版 GLOBAL DEAL HUNTER。支持查询、筛选、收藏、标记无效、提交线索、触发拉取更新。标记是「当前登录账号」的个人标记，与网页端实时互通。
- **货架模式（只读）**：未配置服务端时，自动读取公开数据货架（GitHub 仓库 `huluohu/global-deal-hunter-feed` 的 deals.json，缓存 10 分钟），只能查询与筛选；用户要求标记/提交/更新时，说明需要先配置服务端并给出 setup 方法，不要假装已标记。

## 配置（一次性）

```bash
python3 scripts/gdh.py setup --base-url http://<服务器地址>:3003 --username <用户名>
# 密码交互输入（不回显）；也可全程走环境变量 GDH_BASE_URL / GDH_USERNAME / GDH_PASSWORD
python3 scripts/gdh.py status   # 验证连接：返回 mode/appVersion/total/stats
```

配置与会话存 `~/.config/gdh-cli/`（0600）。会话过期（默认 12 小时、勾选过 30 天则 30 天）时 CLI 会自动重新登录一次，无需打扰用户。密码只存本机配置文件或环境变量，**不要把密码写进聊天、日志或任何输出**。

## 命令速查

```bash
# 查询 / 筛选
python3 scripts/gdh.py search "Notion" [--limit 10]
python3 scripts/gdh.py list [--category ai] [--region cn] [--market asia] \
  [--free-type free] [--verified-only] [--saved-only] [--expiring 3] \
  [--min-value 50] [--sort value|newest|collected|ending] [--limit 20] [--offset 20]
python3 scripts/gdh.py show <id>          # 一条的完整字段（条件、步骤、风险、双语）
python3 scripts/gdh.py categories        # 分类 key/中英名/在架数量

# 标记（幂等：重复执行不会反复翻转；--off 取消）
python3 scripts/gdh.py save <id> [--off]
python3 scripts/gdh.py invalid <id> [--off]

# 更新
python3 scripts/gdh.py refresh           # 触发服务端从货架拉取最新数据，返回新增/更新数
python3 scripts/gdh.py submit --title "…" --url "https://…" [--category x] [--offer "…"] [--regions "全球"]
```

筛选默认口径与网页端一致：只看在架（active）且未被当前用户标记无效的条目；`--include-invalid` 包含无效条目，`--all` 连归档一起看。地区代码用 regionCodes（如 cn/hk/tw/us/sg/jp/kr/gb/de/au/global 等）。

## 用户问法 → 命令

- 「今天有什么新羊毛 / 最新羊毛」→ 先 `refresh`（服务端模式），再 `list --sort collected --limit 10`
- 「快过期的羊毛」→ `list --expiring 3 --sort ending`
- 「免费的 AI 工具 / 某分类有什么」→ `search <关键词>` 或 `list --category <key> --free-type free`
- 「我收藏的」→ `list --saved-only`
- 「把第 N 条 / 这条收藏 / 标记无效」→ 先用 `show` 或上一轮结果确认 id，再 `save` / `invalid`
- 「我发现一个羊毛：标题+链接」→ `submit`，并提醒这是未核实线索
- 「现在库里多少条 / 数据新不新」→ `status`

## 答复呈现规则

- 用用户的语言答复（默认中文）；每条给：标题、一句优惠要点、价值/免费类型、截止时间（有则给）、链接。
- 链接给条目的 accessUrl（官方链接优先、为空时是来源页，linkType 会标明），单独成行方便复制。
- 明确标注核实状态：verified=false 的条目要说「待核实」；提交类条目提醒「未核实线索，不要据此付款或充值」。
- 列表默认转述前 10 条左右并报总数，用户要更多再翻页（--offset）。
- 标记类操作完成后明确回报最终状态（如「已收藏」/「已标记无效」）与条目标题，不要只说「好的」。
- 查不到就直说查不到，并给出放宽筛选的建议（如去掉 --verified-only 或换关键词），不要编造条目。

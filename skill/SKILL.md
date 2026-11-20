# GLOBAL DEAL HUNTER 智能查询（deal_hunter）

让用户通过对话让 agent 查询、筛选、标记、更新「GLOBAL DEAL HUNTER｜全球羊毛情报中心」的羊毛信息：找羊毛、按分类/地区/免费类型/价值/到期时间筛选、收藏、标记无效、提交新线索、更新数据。

底层工具是本技能自带的 `scripts/gdh.py`（纯 Python 标准库，无需安装任何依赖，Python 3.9+ 可运行）。所有命令输出 JSON（`--table` 为人类可读格式），agent 读 JSON 后组织成自然语言答复。

## 两种模式（标记都能持久化，区别只在存哪）

- **货架模式（默认，零配置）**：直接读公开数据货架（GitHub 仓库 `huluohu/global-deal-hunter-feed` 的 deals.json，缓存 10 分钟）。**收藏/无效标记存在 agent 本机** `~/.config/gdh-cli/marks.json`，以条目的有效链接为键，跨会话持久有效；自己提交的线索存 `local-deals.json` 并合并进本地列表。本地标记只对这台 agent 有效，不同步到任何服务端。
- **服务端模式（配了自托管看板时）**：连接用户自托管的 Docker 版 GLOBAL DEAL HUNTER。标记存服务端账号下，与网页端实时互通、多设备同步；提交进服务端库、refresh 触发服务端从货架拉取。

两种模式的查询、筛选、标记、提交、更新命令完全一致，agent 不需要为模式差异改说法；`status` 会返回当前 mode（`feed-local` 或 `server`）。

## 配置（可选，一次性）

```bash
# 只有想用服务端模式时才需要：
python3 scripts/gdh.py setup --base-url http://<服务器地址>:3003 --username <用户名>
# 密码交互输入（不回显）；也可全程走环境变量 GDH_BASE_URL / GDH_USERNAME / GDH_PASSWORD
python3 scripts/gdh.py status   # 验证：返回 mode / 数据量 / 本地标记数
```

配置与会话存 `~/.config/gdh-cli/`（0600）。服务端会话过期时 CLI 会自动重新登录一次，无需打扰用户。密码只存本机配置文件或环境变量，**不要把密码写进聊天、日志或任何输出**。

## 命令速查

```bash
# 查询 / 筛选
python3 scripts/gdh.py search "Notion" [--limit 10]
python3 scripts/gdh.py list [--category ai] [--region cn] [--market asia] \
  [--free-type free] [--verified-only] [--saved-only] [--expiring 3] \
  [--min-value 50] [--sort value|newest|collected|ending] [--limit 20] [--offset 20]
python3 scripts/gdh.py show <引用>        # 完整字段（条件、步骤、风险、双语）
python3 scripts/gdh.py categories        # 分类 key/中英名/在架数量

# 标记（幂等：重复执行不会反复翻转；--off 取消）
# 引用 = list 输出里的 id（服务端模式）或 key（条目链接，两种模式通用）
python3 scripts/gdh.py save <引用> [--off]
python3 scripts/gdh.py invalid <引用> [--off]
python3 scripts/gdh.py marks             # 查看本地标记清单（货架模式）

# 更新
python3 scripts/gdh.py refresh           # 服务端：触发拉取；货架：强制刷新货架缓存
python3 scripts/gdh.py submit --title "…" --url "https://…" [--category x] [--offer "…"] [--regions "全球"]
```

筛选默认口径与网页端一致：只看在架（active）且未被标记无效的条目；`--include-invalid` 包含无效条目，`--all` 连归档一起看。地区代码用 regionCodes（如 cn/hk/tw/us/sg/jp/kr/gb/de/au/global 等）。

## 用户问法 → 命令

- 「今天有什么新羊毛 / 最新羊毛」→ 先 `refresh`，再 `list --sort collected --limit 10`
- 「快过期的羊毛」→ `list --expiring 3 --sort ending`
- 「免费的 AI 工具 / 某分类有什么」→ `search <关键词>` 或 `list --category <key> --free-type free`
- 「我收藏的」→ `list --saved-only`
- 「把这条收藏 / 标记无效」→ 用上一轮结果里的 id 或 key 作为引用执行 `save` / `invalid`
- 「我发现一个羊毛：标题+链接」→ `submit`，并提醒这是未核实线索
- 「现在库里多少条 / 数据新不新」→ `status`

## 答复呈现规则

- 用用户的语言答复（默认中文）；每条给：标题、一句优惠要点、价值/免费类型、截止时间（有则给）、链接。
- 链接给条目的 accessUrl（官方链接优先、为空时是来源页，linkType 会标明），单独成行方便复制。
- 明确标注核实状态：verified=false 的条目要说「待核实」；提交类条目提醒「未核实线索，不要据此付款或充值」。
- 列表默认转述前 10 条左右并报总数，用户要更多再翻页（--offset）。
- 标记类操作完成后明确回报最终状态与条目标题（如「已收藏《…》」），并在货架模式下说明标记存在本地；不要只说「好的」。
- 查不到就直说查不到，并给出放宽筛选的建议（如去掉 --verified-only 或换关键词），不要编造条目。

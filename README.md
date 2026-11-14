# GLOBAL DEAL HUNTER｜全球羊毛情报中心 · 数据货架

这个仓库是「GLOBAL DEAL HUNTER｜全球羊毛情报中心」的**公开数据货架**：只存放一份数据文件 `deals.json`，供自托管的 Docker 看板**拉取式同步**使用。

## 它是怎么工作的

```
上游情报系统（每 2 小时检索全球公开来源，结构化提取并交叉核实）
    │  刷新后自动发布快照
    ▼
本仓库 deals.json  ← 你在这里
    │  Docker 启动时 + 每 2 小时主动拉取（raw 地址）
    ▼
Docker 看板（邀请制多用户，自托管，偏好与收藏只存在本地）
```

- 发布与拉取都全自动，不需要任何人值守。
- Docker 端不需要为同步暴露接口，可以躲在内网 / NAT 后面。
- 货架上只有公开优惠信息；使用者的收藏、账号设置永远不会出现在这里。

## 数据文件

最新快照（永久地址，Docker 的 `FEED_URL` 就填这个）：

https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/deals.json

备用镜像（内容相同，CDN 更新可能略有延迟）：

https://cdn.jsdelivr.net/gh/huluohu/global-deal-hunter-feed@main/deals.json

### 格式

快照是单个 JSON 文件。顶层结构：

```json
{
  "generatedAt": "2026-11-14T09:54:34Z",
  "source": "GLOBAL DEAL HUNTER 情报中心",
  "version": 1,
  "count": 341,
  "categories": [
    { "key": "ai", "zh": "AI 工具", "en": "AI tools", "tab": "ai" }
  ],
  "deals": []
}
```

- `categories` 是分类定义表，每项含 `key`、`zh`、`en`、`tab` 四个字段；下游看板据此动态渲染分类页签，不写死清单。
- `deals` 是条目数组。单条结构如下（真实条目节选，字段名与取值均为实际格式）：

```json
{
  "title": "N26, your everyday bank",
  "titleZh": "N26，您的日常银行",
  "titleEn": "N26, your everyday bank",
  "category": "bank",
  "vendor": "N26",
  "offer": "N26 gives you €20 welcome bonus.",
  "offerZh": "N26 提供 20 欧元迎新奖励。",
  "offerEn": "N26 gives you €20 welcome bonus.",
  "conditions": "来源未注明",
  "conditionsZh": "来源未注明",
  "conditionsEn": "Not specified in the source",
  "steps": ["Open the official link", "Register / log in to N26", "Follow the on-page instructions to claim the €20 welcome bonus"],
  "stepsZh": ["打开官方链接", "注册/登录 N26", "按页面指引领取 20 欧元迎新奖励"],
  "stepsEn": ["Open the official link", "Register / log in to N26", "Follow the on-page instructions to claim the €20 welcome bonus"],
  "regions": "西班牙",
  "regionsZh": "西班牙",
  "regionsEn": "Spain",
  "valueText": "€20",
  "valueTextZh": "20 欧元",
  "valueTextEn": "€20",
  "valueUsd": null,
  "freeType": "真正免费",
  "officialUrl": "https://n26.com/en-es/affiliate-casilistaycasiguapa",
  "sourceUrl": "https://n26.com/en-es/affiliate-casilistaycasiguapa",
  "sourceName": "N26",
  "accessUrl": "https://n26.com/en-es/affiliate-casilistaycasiguapa",
  "linkType": "official",
  "verified": true,
  "status": "active",
  "market": "western",
  "startsAt": null,
  "endsAt": null,
  "firstSeenAt": "2026-11-10T13:32:58.575Z",
  "lastVerifiedAt": "2026-11-11T19:32:40.215Z",
  "riskNote": "",
  "riskZh": "奖金资格与发放条件以页面条款为准；开户需要完成身份验证。",
  "riskEn": "Bonus eligibility and payout conditions are subject to the terms on the page; identity verification is required to open the account."
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `title` / `titleZh` / `titleEn` | 名称：原文 + 中英双语 |
| `category` | 类别 key，对应顶层 `categories` |
| `vendor` | 厂商 / 平台名 |
| `offer` / `offerZh` / `offerEn` | 优惠内容 |
| `conditions` / `conditionsZh` / `conditionsEn` | 参与条件 |
| `steps` / `stepsZh` / `stepsEn` | 参与步骤（字符串数组） |
| `regions` / `regionsZh` / `regionsEn` | 适用地区 |
| `valueText` / `valueTextZh` / `valueTextEn` | 价值的原文表述，如「€20」「省 $35/月」 |
| `valueUsd` | 折算美元估值（数字或 null；奖池类为总奖池金额） |
| `freeType` | 真正免费 / 免费试用 / 需要充值 / 需要交易量 / 需要邀请 / 混合优惠 / 折扣优惠 / 返现优惠 |
| `officialUrl` | 官方活动页；为空表示暂无官方页，按来源页条目处理（见「链接口径」） |
| `sourceUrl` / `sourceName` | 信息来源页与来源名 |
| `accessUrl` | 实际打开链接：有官方页时为官方页，否则为来源页 |
| `linkType` | `official`（官方页）或 `source`（来源页） |
| `verified` | 是否已在官方页核实；`false` 即「待核实」 |
| `status` | `active`（进行中）或 `expired`（已过期归档） |
| `market` | `asia` / `global` / `western` / `other` |
| `startsAt` / `endsAt` | 开始 / 截止时间（ISO 8601，未知为 null） |
| `firstSeenAt` / `lastVerifiedAt` | 首次收录 / 最后核实时间 |
| `riskNote` / `riskZh` / `riskEn` | 风险提示（原文 + 中英双语） |

### 数据口径

- 覆盖类目（17 类）：AI 工具、Crypto、海外银行、VPS 及云服务、VPS/云、电商购物、会员订阅、中国平台、U 卡、软件服务、旅行出行、美食外卖、教育课程、影音娱乐、通信/eSIM、生活服务、其他。其中电商、旅行、外卖、教育、娱乐、通信、生活 7 类为常驻核心类目，全球英文＋亚洲英文＋亚洲中文三路检索；亚洲来源单独加强采集。
- 会员订阅专盯 11 个品牌官方会员页（爱奇艺、腾讯视频、优酷、QQ 音乐、网易云音乐、Apple、YouTube、Google One、Spotify、Microsoft、Adobe）：每轮直接抓官方页，只收页面原文写明的试用、首月价、年付折扣、学生价等常驻优惠。
- 中国平台专盯京东、阿里系（淘宝、天猫、闲鱼、支付宝）与拼多多：每轮常驻采集，分五层挖掘——平台活动、商家活动（旗舰店品牌日/店铺券）、商品好价（具体单品带到手价）、捡漏（清仓/神价/叠券玩法）、0day（标错价/券 bug，一律待核实并注明可能砍单）；闲鱼只收平台官方活动，个人卖家的二手挂单不算优惠、不收录。
- 链接口径：`officialUrl` 只放活动主办方官网的真实活动页。追溯不到官方页的，不冒充、不剔除，降级为来源页条目：`officialUrl` 为空、`linkType` 为 `source`、`accessUrl` 指向来源资讯页、`verified` 为 false。有官方链接时 `linkType` 为 `official`、`accessUrl` 即官方页。发布前另有程序化链接审计逐条复核，失效（404/410）、停放域名、新闻/聚合页冒充官方链接的会被剔除或改指。
- 不编造活动、金额与截止时间：官方页没写明的金额不估算；只能在 App 内领取、需登录才可见的，标「待核实」并在条件里注明。
- 奖池类数字（如交易所瓜分活动）是总奖池金额，不是每人可得金额，看板与数据里均有风险提示。
- 灰产不收：代充、拼车、共享账号、刷单、薅羊毛脚本/外挂、黄牛囤货类一律过滤。
- 已过期的条目会被标为 expired 并进入档案，不会继续当作有效优惠展示。

## Docker 看板

镜像（双架构 amd64 + arm64）：

https://hub.docker.com/r/fooololo/global-deal-hunter

当前镜像特性：邀请制多用户（设置/收藏/通知订阅按账号隔离）、双语界面（默认跟随浏览器）、分类动态渲染、通知推送（Telegram / Bark / Server酱 / Webhook / 企业微信，命中新增合并为一条汇总）、PWA（HTTPS 下可安装到桌面）、管理员看板（账号状态、在线会话、登录记录）。

一键部署文件就在本仓库根目录的 `docker-compose.yml`：下载后只改 `ADMIN_PASSWORD` 和 `SECRET_KEY` 两处，执行 `docker compose up -d` 即可。更新镜像：`docker compose pull && docker compose up -d`（只用 latest 标签）。

## 更新节奏

每 2 小时一轮：采集刷新完成后约 25 分钟内发布新快照，每次发布都是一个 git 提交，历史版本可查；另有独立的链接自检每 6 小时复核线上数据。

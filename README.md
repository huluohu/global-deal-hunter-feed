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

```json
{
  "generatedAt": "2026-11-12T01:54:47Z",
  "source": "GLOBAL DEAL HUNTER 情报中心",
  "version": 1,
  "count": 379,
  "categories": [ { "key": "...", "zh": "...", "en": "...", "tab": "..." } ],
  "deals": [ { "..." : "每条优惠的完整字段" } ]
}
```

快照顶层带 `categories` 分类定义表（key/中英名/页签），下游看板据此动态渲染分类，不写死清单。

每条优惠包含 14 个内容字段：名称、类别、厂商、优惠内容、实际价值、参与条件、适用地区、开始及截止时间、参与步骤、官方链接、信息来源、最后验证时间、风险提示，均有中英双语版本。另带机器字段：`market`（asia / global / western / other）、`freeType`（真正免费 / 免费试用 / 需要充值 / 需要交易量 / 需要邀请 / 混合优惠 / 折扣优惠 / 返现优惠）、`valueUsd`、`verified`（是否已在官方页核实，未核实的即「待核实」）、`status`（active / expired），以及打开链接字段 `accessUrl` 与 `linkType`（见下「链接口径」）。

### 数据口径

- 覆盖类目（17 类）：AI 工具、Crypto、海外银行、VPS 及云服务、云服务、电商购物、会员订阅、中国平台、U 卡、软件、旅行出行、美食外卖、教育课程、影音娱乐、通信、生活服务、其他。其中电商、旅行、外卖、教育、娱乐、通信、生活 7 类为常驻核心类目，全球英文＋亚洲英文＋亚洲中文三路检索；亚洲来源单独加强采集。
- 会员订阅专盯 11 个品牌官方会员页（爱奇艺、腾讯视频、优酷、QQ 音乐、网易云音乐、Apple、YouTube、Google One、Spotify、Microsoft、Adobe）：每轮直接抓官方页，只收页面原文写明的试用、首月价、年付折扣、学生价等常驻优惠。
- 中国平台专盯京东、阿里系（淘宝、天猫、闲鱼、支付宝）与拼多多的官方活动：每轮常驻采集；闲鱼只收平台官方活动，个人卖家的二手挂单不算优惠、不收录。
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

# GLOBAL DEAL HUNTER｜全球羊毛情报中心 · 数据货架

这个仓库是「GLOBAL DEAL HUNTER｜全球羊毛情报中心」的**公开数据货架**：只存放一份数据文件 `deals.json`，供自托管的 Docker 看板**拉取式同步**使用。

## 它是怎么工作的

```
Muse（每 2 小时 AI 检索 + 提取，吃 Muse 额度）
    │  刷新后自动发布快照
    ▼
本仓库 deals.json  ← 你在这里
    │  Docker 启动时 + 每 2 小时主动拉取（raw 地址）
    ▼
Docker 看板（单用户登录，自托管，偏好与收藏只存在本地）
```

- 发布与拉取都全自动，不需要任何人值守。
- Docker 端不需要为同步暴露接口，可以躲在内网 / NAT 后面。
- 货架上只有公开优惠信息；使用者的收藏、本地线索、账号设置永远不会出现在这里。

## 数据文件

最新快照（永久地址，Docker 的 `FEED_URL` 就填这个）：

https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/deals.json

备用镜像（内容相同，CDN 更新可能略有延迟）：

https://cdn.jsdelivr.net/gh/huluohu/global-deal-hunter-feed@main/deals.json

### 格式

```json
{
  "generatedAt": "2026-11-10T06:23:47Z",
  "source": "GLOBAL DEAL HUNTER · Muse Space",
  "version": 1,
  "count": 79,
  "deals": [ { "..." : "每条优惠的完整字段" } ]
}
```

每条优惠包含 12 个字段：名称、类别、优惠内容、实际价值、参与条件、适用地区、开始及截止时间、参与步骤、官方链接、信息来源、最后验证时间、风险提示。另带机器字段：`market`（asia / global / western / other）、`freeType`（真正免费 / 免费试用 / 需要充值 / 需要交易量 / 需要邀请 等）、`valueUsd`、`verified`（是否已验证，未验证的即「待核实」）、`status`（active / expired）。

### 数据口径

- 覆盖类目：AI 订阅、Crypto 空投与活动、U 卡、海外银行、VPS 与云服务、软件与数字产品、其他优惠；亚洲来源单独加强采集。
- 只收录能找到来源页面的优惠，查不到官方出处的标「待核实」，不编造活动与链接。
- 奖池类数字（如交易所瓜分活动）是总奖池金额，不是每人可得金额，看板与数据里均有风险提示。
- 已过期的条目会被标为 expired 并进入档案，不会继续当作有效优惠展示。

## Docker 看板

镜像（双架构 amd64 + arm64，含 v1.3 页面重构与个人定制）：

https://hub.docker.com/r/fooololo/global-deal-hunter

部署时在 compose 里配置即可自动跟上本货架的更新：

```yaml
environment:
  FEED_URL: "https://raw.githubusercontent.com/huluohu/global-deal-hunter-feed/main/deals.json"
  FEED_PULL_INTERVAL_HOURS: "2"
```

## 更新节奏

每 2 小时一轮：采集刷新完成后约 25 分钟内发布新快照，每次发布都是一个 git 提交，历史版本可查。

# 广佛大学生雷达 · 完整数据源清单

最新更新：**v6 (2026-06-05)** — **33 个数据源**, 覆盖广州/佛山/深圳/珠海/东莞/香港 6 城市，
单次抓取 ~950+ 条结构化活动信息。

---

## 📊 当前已接入 (33 个)

### 🎫 综合活动 / 优惠 / 美食 / 教育（本地宝双城）
| # | 站点 | 根 URL | 数据量 | 状态 |
|---|---|---|---|---|
| 1 | 广州本地宝 | https://gz.bendibao.com | ~240 | ✅ 8 频道（休闲/优惠/旅游/美食/教育/培训/招聘/生活）|
| 2 | 佛山本地宝 | https://fs.bendibao.com | ~220 | ✅ **自动绕过拼图验证** |
| 3 | 豆瓣同城·广州 | https://guangzhou.douban.com | ~68 | ✅ 10 个类别并行抓取 |
| 4 | 活动行 | https://www.huodongxing.com | ~37 | ✅ 广州+佛山 city |
| 5 | 互动吧 | https://www.hudongba.com | ~40 | ✅ 4 路数据叠加（API + JSON-LD + JS 变量 + DOM）|

### 📚 图书馆 / 文化馆 / 美术馆 / 博物馆 (10)
| # | 站点 | 根 URL | 数据量 | 状态 |
|---|---|---|---|---|
| 6 | 广州图书馆 | https://action.gzlib.org.cn | ~48 | ✅ 月历 API |
| 7 | 越秀公共数字文化云 | https://www.iwhyun.com | ~9 | ✅ 删除 Accept-Language 头取完整数据 |
| 8 | 顺德图书馆 | https://www.sdlib.com.cn | ~30 | ✅ |
| 9 | 南海图书馆 | http://www.nhlib.cn | ~17 | ✅ |
| 10 | 广东美术馆 | https://www.gdmoa.org | ~78 | ✅ 展览/讲座/活动 |
| 11 | **广东时代美术馆** 🆕 | https://www.timesmuseum.org | ~3 | ✅ **Playwright 渲染** |
| 12 | **何香凝美术馆** 🆕 | http://www.hxnart.com | ~8 | ✅ 深圳艺术联动 |
| 13 | 广州博物馆 | https://www.guangzhoumuseum.cn | 0 | ⚠️ 主域跳转脚本 |
| 14 | 广州群文网 | https://www.gz-arts.com | 0 | ❌ HTTP 420 WAF |
| 15 | 佛山文化云 | https://wh.fs.cn | 0 | ❌ 非粤 ISP 不可达 |
| 16 | 佛山市图书馆 | http://www.fslib.com.cn | 0 | ❌ TLS 握手超时 |
| 17 | 佛山+ | https://foshanplus.com | 0 | ⚠️ 整站 Vue SPA |

### 🎭 演出 / Livehouse
| # | 站点 | 根 URL | 数据量 | 状态 |
|---|---|---|---|---|
| 18 | 秀动 ShowStart | https://www.showstart.com | ~33 | ✅ Node.js eval `__NUXT__` IIFE |
| 19 | 大麦网 | https://search.damai.cn | 0 | ❌ x5sec 风控 |
| 20 | 爱LiveHouse | http://www.ilivehouse.com | 0 | ⚠️ 51.la 反扒 |

### 💼 校园招聘 / 宣讲会 / 双选会
| # | 站点 | 根 URL | 数据量 | 状态 |
|---|---|---|---|---|
| 21 | 中山大学就业网 | https://career.sysu.edu.cn | ~18 | ✅ |
| 22 | 广东工业大学就业网 | https://career.gdut.edu.cn | ~30 | ✅ |
| 23 | 广州大学就业网 | https://jy.gzhu.edu.cn | ~20 | ✅ |
| 24 | 广州软件学院就业网 | https://job.seig.edu.cn | ~6 | ✅ bibibi 模板 |
| 25 | 暨南大学就业网 | https://career.jnu.edu.cn | ~0 | ✅（数据稀疏）|
| 26 | 应届生·广州宣讲会 | https://my.yingjiesheng.com | ~9 | ✅ GB2312 编码 |

### 💻 Tech Meetup / 大学生分享 🆕 (重点扩展)
| # | 站点 | 根 URL | 数据量 | 状态 |
|---|---|---|---|---|
| 27 | 思否·广州技术活动 | https://segmentfault.com | ~16 | ✅ Next.js JSON |
| 28 | **GDG·Google开发者社区** 🆕 | https://gdg.community.dev | **~21** | ✅ **5 城市：广州/深圳/珠海/东莞/香港** |
| 29 | **Meetup.com·珠三角** 🆕 | https://www.meetup.com | **~34** | ✅ **5 城市：广州/深圳/珠海/东莞/佛山** |
| 30 | **Eventbrite·珠三角** 🆕 | https://www.eventbrite.com | **~38** | ✅ **3 城市：广州/深圳/珠海** (schema.org JSON-LD) |
| 31 | **SOFAStack·蚂蚁云原生** 🆕 | https://www.sofastack.tech | ~10 | ✅ 蚂蚁开源技术沙龙 |

### 🎓 学术 / 哲学
| # | 站点 | 根 URL | 数据量 | 状态 |
|---|---|---|---|---|
| 32 | **中山大学哲学系** 🆕 | https://philosophy.sysu.edu.cn | ~7 | ✅ 哲学前沿讲座 |

---

## 🔍 已侦察但暂不接入（详细原因）

### ❌ 域名解析失败（多次尝试 .gov.cn/.com/.cn 各变体均失败）
- **区文化馆**：天河 / 海珠 / 黄埔 / 番禺 / 荔湾 / 增城 文化馆 — 官方网址多为不存在
- **区图书馆**：天河 / 白云 / 番禺 / 荔湾 / 南沙 / 禅城 / 高明 / 三水 / 增城 / 从化
- 注：部分区图书馆官方域名为 **微信公众号 + 小程序**（无独立 web 入口）
- **高校就业网**：华南理工 / 华南农业 / 广东药科 / 广州医科 / 广州中医药 / 广东金融 / 广东第二师范 等都无可直接抓的 web 入口（多用 SSO 登录）

### ❌ 反爬严重（需登录态 / Cookie / 浏览器指纹）
- **大众点评广州** (`dianping.com/guangzhou`) — 验证码 + 滑块
- **小红书** — 必须登录
- **大麦网** — x5sec 风控
- **票牛 / 永乐 / 演出网 / 票星球** — 反爬严重 SPA

### ⚠️ SPA / 需要 Playwright（已实现基础设施，可逐个启用）
- **InfoQ 极客邦** (`infoq.cn/event/list`) — Vue SPA
- **掘金大会** (`conf.juejin.cn`) — Next.js SPA 但只有"年度大会"
- **CSDN 活动** (`huiyi.csdn.net/activity/lists`) — Vue SPA
- **活动家** (`huodongjia.com`) — SPA
- **K11 广州**、**摩登天空**、**腾讯创业** — SPA
- **百格活动** (`bagevent.com`) — 需 cityName 参数 + SPA
- **OSCHINA 源创会** (`oschina.net/event`) — 单条活动页可抓但无统一列表
- **IT 大咖说** (`itdks.com`) — Ajax 加载，需逆向 API

### 🌍 海外平台（已部分接入）
- **GDG 社区** ✅ 已接入
- **Meetup.com** ✅ 已接入
- **Eventbrite** ✅ 已接入
- **KKTIX** — Cloudflare 403 跳过
- **Luma** — Anonymous 浏览受限
- **Hacker News / Lobsters / Reddit** — 不针对广佛

### 📨 微信公众号生态（无法纳入 HTTP 爬虫）
99% 的本地企业 / 协会 / 园区活动都通过**微信公众号**发布：
- 广州青年报 / 广州团市委 / 各区文旅局
- 南海 AI 协会 / 佛山软件行业协会
- TIT 创意园 / 红专厂 / 太古汇 / 正佳广场 等商场活动
- 黑客松 Weekly / 黑客周

**建议**：用 [WechatSogou](https://github.com/Chyroc/WechatSogou) 或第三方公众号代理网关单独爬，不在本爬虫范围。

### 🟡 已侦察过但当前数据为空（不是 bug）
- **GDG 广州/珠海/东莞/香港** upcoming 都为 0 — 仅 GDG 深圳有 1 个 upcoming
- **TechParty** (`techparty.org`) — 是博客形态，无活动列表 URL 结构
- **DevOps 社区广州** (`devopschina.org/event-organizer/guangzhou/`) — 账号已悬挂

---

## 📈 实测统计 (v6, 2026-06-05)

```
✅ 952 条 / 含时间 940 (99%) / 含海报 ~640 / 抓取 130 秒
✅ 0 个价格 bug
✅ 6 个城市：广州 (566) / 佛山 (313) / 深圳 (51) / 珠海 (14) / 东莞 (4) / 香港 (4)
✅ 11 个清晰互斥的分类
```

### 分类分布
```
讲座沙龙  166 ⭐ Tech Meetup 主战场（GDG/Meetup.com/Eventbrite/思否/SOFAStack/中大哲学）
教育升学  122
招聘求职  107
其他       98
优惠羊毛   98
展览       88
公益课/工作坊 86
演出       61
美食探店   51
节庆赛事   45
社交聚会   30
```

---

## 🛠️ 如何快速添加新源

```python
# crawler/adapters/my_meetup.py
from ..base import BaseAdapter, Event

class MyMeetup(BaseAdapter):
    source = "my_meetup"
    source_name = "我的 Meetup"
    base_url = "https://example.com"

    def fetch(self):
        html = self.http.text(self.base_url + "/events")
        # ... 解析 ...
        yield Event(...)
```

注册到 `crawler/adapters/__init__.py` 的 `ALL_ADAPTERS` 列表即可。

**自动获得**:
- ✅ 全局时间兜底解析（raw_time/description/title 三路）
- ✅ 城市归一化（"广州市" → "广州"）
- ✅ 分类归一化（11 个互斥大类，关键字 + 规则）
- ✅ 状态分类（today/upcoming/archived/unknown）
- ✅ 并发抓取调度
- ✅ Playwright 可选支持（设 `needs_browser = True`）

---

## 📝 用户自助检索建议（社区版）

对于本爬虫**暂未/无法接入**的源，推荐用户：

### 1. 通用活动平台（手动定期搜索）
```
活动行  https://www.huodongxing.com   → 已接入
互动吧  https://www.hudongba.com      → 已接入
百格活动 https://www.bagevent.com     → SPA, 手动浏览
CSDN活动 https://huiyi.csdn.net       → 手动
```

### 2. 大厂云开发者社区（关注公众号 + 官网订阅）
```
阿里云  https://developer.aliyun.com/event
腾讯云  https://cloud.tencent.com/developer/salon
华为云  https://developer.huaweicloud.com/events
火山引擎 https://volcengine.huodongxing.com  → 可被本爬虫的"活动行"间接覆盖
```

### 3. 开源项目活动（关注 GitHub Releases 或邮件列表）
```
Apache Flink https://flink-learning.org.cn
OceanBase    https://open.oceanbase.com
KubeSphere   https://kubesphere.io/events
Apache Pulsar https://pulsar.apache.org/events
```

### 4. 站内检索模板（Google/Bing）
```
site:huodongxing.com 广州 技术沙龙
site:gdg.community.dev Guangzhou
site:meetup.com cn--guangzhou
site:eventbrite.com 广州
site:segmentfault.com 广州 活动
site:huiyi.csdn.net 广州
```

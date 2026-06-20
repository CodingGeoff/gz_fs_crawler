# 广佛大学生「羊毛 & 周末雷达」聚合爬虫 v3

广州/佛山（含高明、南海、顺德）大学生群体的 **活动 / 优惠 / 招聘 / 美食 / 演出 / 展览 / 招聘会 / 宣讲会 / 公益讲座** 聚合采集框架。
单次运行可从 **22 个数据源**抓取 **750+ 条**结构化活动信息（实测 **~1 分钟**抓取 + ~3 分钟下载海报）。

## ✨ 特性

### 数据抓取
- **🚀 全并发**：21 个 adapter 并行，每个 adapter 内部详情页同源并发 6~8，提速 **12x**（之前 13 分钟 → 现在 ~1 分钟）
- **🛡️ 智能反爬**：本地宝拼图验证自动绕过（解析 `targetX/targetY` 直接 GET 提交，无需 OCR/浏览器）
- **🧩 Node.js eval SSR 数据**：秀动 ShowStart 的 Nuxt `window.__NUXT__` IIFE 自动 eval 取出结构化数据
- **🔄 多源叠加抗破坏**：互动吧 4 路数据源（JSON-LD + API + JS 变量 + 正文 DOM）保证海报/价格/地址都拿全
- **🕐 强大时间解析**：8+ 种中文格式（"今天/明天 14:00"、"2026年5月1-2日"、"2026年5月1日（周五）10:00-11:30" 等）
- **📅 时间状态分类**：自动标记 `today` / `upcoming` / `archived` / `unknown`
  - 已归档活动**不删除**，按时间倒序保留
  - 海报下载优先给未过期活动
- **🏙️ 城市归一化**：广州市→广州；南海/顺德/禅城/高明→佛山
- **📦 多格式输出**：JSON / CSV / SQLite 三件套 + 按 分类/来源/状态 拆分子文件
- **🧹 强容错**：单站挂了不影响其他站；详情页 WAF/拼图/超时/移动端模板差异 均有对应分支

### 🎨 UI 看板 (v3)
- **📱 移动端友好**：顶部仅显示 "筛选" 按钮，点击展开/收起；筛选/搜索一应俱全
- **♾️ 滚动惰性加载**：首屏只渲染 30 张卡片，IntersectionObserver 监听滚动到底再加载下一批
- **⚡ 首屏快**：HTML 约 520KB（含 752 条数据），首屏渲染 <100ms
- **🌗 暗黑/浅色自适应**：根据系统主题
- **🏷️ 状态分组渲染**：🔥 今天 → ⏰ 即将 → ❓ 未知 → 📦 归档（归档半透明）
- **🔍 多维筛选**：状态 × 分类 × 城市 × 站点 × 搜索关键词，200ms 防抖
- **🚀 数据内联**：可在沙箱 iframe / file:// 直接打开，无需 web server
- **⬆️ 回到顶部 FAB**

## 📦 安装

```bash
pip install -r requirements.txt
```

## 🚀 使用

```bash
# 一键全跑（默认下载海报）
python run.py

# 不下载海报（更快）
python run.py --no-poster

# 只跑指定数据源
python run.py -s douban_gz -s bendibao_gz

# 多页抓取（每个支持分页的站点抓 N 页）
python run.py --max-pages 3

# 自定义输出目录
python run.py --out /path/to/output
```

## 📂 输出结构

```
data/
├── events.json            # 主结果：全部活动 JSON 数组
├── events.csv             # CSV（utf-8-sig，Excel 可直接打开）
├── events.sqlite          # SQLite DB, 表名 events, 主键 uid
├── summary.md             # 人类可读概况（数量统计 + 示例）
├── by_category/           # 按 活动/优惠/展览/演出/讲座/公益课/美食 拆分
│   ├── 活动.json
│   ├── 演出.json
│   └── ...
├── by_source/             # 按数据源拆分
│   ├── douban_gz.json
│   └── ...
└── posters/               # 下载的海报图片
    ├── douban_gz_xxxx.jpg
    └── ...
```

## 🗂️ 数据模型（Event）

| 字段 | 说明 |
|---|---|
| `source` / `source_name` | 数据源标识 / 中文名 |
| `category` | 归一化大类：活动 / 展览 / 演出 / 讲座 / 公益课 / 优惠 / 美食 / 资讯 |
| `title` | 活动标题 |
| `url` | 详情页链接 |
| `city` / `district` | 城市 / 区 |
| `venue` / `address` | 场馆 / 详细地址 |
| `start_time` / `end_time` | ISO 格式时间，可能为空 |
| `raw_time` | 原文时间字符串（保真） |
| `price` / `price_min` / `price_max` / `is_free` | 价格原文 + 解析数字 + 免费标记 |
| `poster` / `poster_local` | 海报 URL + 本地路径 |
| `organizer` | 主办方 |
| `description` | 摘要描述 |
| `tags` | 标签数组 |
| `extra` | 站点特有字段（JSON 对象） |
| `crawled_at` | 抓取时间 |
| `uid` | md5(url+title)，去重主键 |

## 🌐 已接入数据源（22 个）

### 🟢 活动 / 优惠 / 美食 / 教育类 (5)
| Source | 站点 | 状态 | 备注 |
|---|---|---|---|
| `douban_gz` | 豆瓣同城·广州 | ✅ 稳定 (100% 时间) | 10 个类别并行，每类 8 条 |
| `bendibao_gz` | 广州本地宝 | ✅ 稳定 (97%) | 休闲/优惠/旅游/美食/教育 5 频道 |
| `bendibao_fs` | 佛山本地宝 | ✅ **WAF 绕过** (99%) | 自动破解拼图验证 |
| `huodongxing` | 活动行 | ✅ 稳定 (100%) | 广州/佛山 city |
| `hudongba` | 互动吧 | ✅ 稳定 (100%) | 4 路数据叠加 |

### 🔵 图书馆 / 文化馆 / 美术馆 / 博物馆 (9)
| Source | 站点 | 状态 | 备注 |
|---|---|---|---|
| `gzlib` | 广州图书馆 | ✅ 稳定 (100%) | 直接调用月历 API |
| `iwhyun` | 越秀公共数字文化云 | ✅ 稳定 (100%) | 移除 Accept-Language 头才能拿完整日期 |
| `sdlib` | 顺德图书馆 | ✅ 稳定 (100%) | |
| `nanhai_lib` | 南海图书馆 | ✅ 稳定 (100%) | 详情页结构化抽取 |
| `gdmoa` | 广东美术馆 | ✅ **新** (96%) | 展览/讲座/主题活动 3 频道 |
| `gz_museum` | 广州博物馆 | ⚠️ 部分 | 主域是跳转脚本 |
| `gz_arts` | 广州群文网 | ❌ WAF | HTTP 420 风控；需 Playwright |
| `foshan_culture_cloud` | 佛山文化云 | ❌ 不可达 | `wh.fs.cn` 非粤 ISP TCP 握手挂起 |
| `foshan_lib` | 佛山市图书馆 | ❌ 不可达 | TLS 握手超时 |
| `foshanplus` | 佛山+ | ❌ SPA | 整站 Vue SPA |

### 🟡 校园招聘 / 双选会 / 宣讲会 (4) 🆕
| Source | 站点 | 状态 | 备注 |
|---|---|---|---|
| `sysu_career` | 中山大学就业网 | ✅ 稳定 | 招聘会 + 宣讲会，含详细时间地点 |
| `gdut_career` | 广东工业大学就业网 | ✅ 稳定 | 同上模板 |
| `gzhu_career` | 广州大学就业网 | ✅ 稳定 | 广州职迅模板 |
| `yingjiesheng_gz` | 应届生·广州宣讲会 | ✅ 稳定 | 横跨广州所有高校的宣讲日历 |

### 🎫 演出 / Livehouse (3)
| Source | 站点 | 状态 | 备注 |
|---|---|---|---|
| `showstart` | 秀动 ShowStart | ✅ **新** (100%) | Node.js eval `window.__NUXT__` IIFE 拿数据；广州 191 / 佛山 14 场演出 |
| `damai` | 大麦网 | ❌ WAF | x5sec 风控；需真实浏览器 cookie |
| `ilivehouse` | 爱LiveHouse | ⚠️ 占位 | 51.la 反扒，需 Playwright |

## 🛡️ 反爬绕过

### 佛山本地宝拼图验证（已实现 ✅）

本地宝家族站点（广州本地宝/佛山本地宝/等）使用拼图滑块验证。原始页面：

```html
<title>请完成拼图验证以继续访问</title>
<script>
  window.CHALLENGE_CONFIG = {
    challengeId: "xxx",
    targetX: 263,        // ← 答案就在 HTML 里！
    targetY: 113,
    host: "fs.bendibao.com",
    ...
  };
</script>
```

`crawler/bypass.py` 自动识别此页面，从 `window.CHALLENGE_CONFIG` 提取
`targetX/targetY/challengeId`，直接 `GET /verify_puzzle?...` 获取
`antibot_challenge` cookie，之后所有请求即可正常访问。

**完全无需 OCR、无需 Playwright、无需浏览器**，几十毫秒完成。
本绕过已经融入 `HTTPClient.get()`，对其他 adapter 透明。

### 其它反爬站点的可选方案

- **OCR 滑块验证**（其它真随机位置）：用 `ddddocr` 或自训 YOLO
- **JS 加密签名**（大麦/秀动）：`PyExecJS` 直接执行 hash 算法
- **WAF / 风控页**：`curl_cffi` / `tls-client` 模拟 TLS 指纹

## ⏱️ 时间状态分类

每条 Event 落盘时自动计算 `status` 字段：

| 状态 | 判定规则 | 用途 |
|---|---|---|
| `today` | 开始日 == 今天 或 当前时间在 [start,end] 之间 | 🔥 当天进行中 |
| `upcoming` | start_time > now | ⏰ 即将开始（按时间正序）|
| `archived` | end_time < now 且不是今天 | 📦 已归档（按时间倒序）|
| `unknown` | 没有有效时间字段 | ❓ 榜单/常青文章 |

排序策略：`today → upcoming → unknown → archived`

`data/by_status/{today,upcoming,archived,unknown}.json` 已自动按状态拆分。

## 🛠️ Playwright 升级方案（可选）

对于 `gz_arts` / `foshanplus` / `damai`，最佳方案是引入 Playwright 走真实浏览器：

```bash
pip install playwright
playwright install chromium
```

然后在对应 adapter 的 `fetch()` 中替换 `self.http.text(url)` 为：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
    browser.close()
```

代码里已经把这些站点的 `needs_browser` 标志位预留好，可以加分支判断按需启用。

## 🔌 扩展新数据源

```python
# crawler/adapters/myhood.py
from ..base import BaseAdapter, Event
from datetime import datetime

class MyHood(BaseAdapter):
    source = "myhood"
    source_name = "我家小区活动"
    base_url = "https://example.com"

    def fetch(self):
        html = self.http.text(self.base_url + "/list")
        # ... 解析 ...
        yield Event(
            source=self.source, source_name=self.source_name,
            category="活动", title="xxx", url="...",
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )
```

然后在 `crawler/adapters/__init__.py` 的 `ALL_ADAPTERS` 列表里加上即可。

## 📊 实测结果（最新一次运行）

```
总计 752 条 / 含时间 743 (99%) / 含海报 ~370 / 抓取 57s + 海报 3min

按状态：
🔥 今天/进行中: 52
⏰ 即将开始: 119
📦 已归档:    376    (按时间倒序，搜索时排后)
❓ 未知:      20

按来源 TOP：
- 广州本地宝: 150
- 佛山本地宝: 142  ← 拼图绕过后从 3 → 142
- 豆瓣同城·广州: 57
- 互动吧: 40
- 活动行: 38
- 广东工业大学就业网: 30  🆕
- 顺德图书馆: 30
- 广州大学就业网: 20      🆕
- 中山大学就业网: 18      🆕
- 南海图书馆: 17
- 越秀公共数字文化云: 9
- 应届生·广州宣讲会: 9    🆕
- 广州图书馆: 7

按分类：活动 232 / 优惠 100 / 展览 63 / 宣讲会 43 / 招聘会 19 / 公益课 41 / ...
按城市：广州 ~400 / 佛山 ~170
免费活动占比：59%
```

## ⚠️ 合规提示

本项目仅用于学习交流、个人收集本地活动信息，请：
- 设置合理的 sleep（默认 0.15-0.45 秒/请求）
- 不要并发滥用
- 遵守目标站点 robots.txt
- 不要将抓取数据用于商业目的

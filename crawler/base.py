"""通用模型 / HTTP 客户端 / 适配器基类。

每个站点写一个继承 BaseAdapter 的子类，实现 `fetch()` 返回 Event 列表。
框架负责重试、限速、去重、归一化、落盘。
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Iterable, Iterator, Optional
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type
)

log = logging.getLogger("crawler")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class Event:
    """统一活动 / 优惠 / 美食条目模型。"""

    # 必填
    source: str                    # 数据源标识，如 douban_gz
    source_name: str               # 中文站点名，方便展示
    category: str                  # 归一化大类: 活动 / 展览 / 演出 / 讲座 / 公益课 / 优惠 / 美食 / 资讯 / 其他
    title: str
    url: str                       # 详情页链接
    # 选填
    city: str = ""                 # 广州 / 佛山 / 高明 / 顺德 / 南海 / ...
    district: str = ""             # 区
    venue: str = ""                # 场馆 / 商家
    address: str = ""              # 详细地址
    start_time: str = ""           # ISO 或原始字符串均可
    end_time: str = ""
    raw_time: str = ""             # 站点原文时间，避免解析丢真值
    price: str = ""                # 原文价格描述，如 "免费"、"120 元起"、"50-380"
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    is_free: Optional[bool] = None
    poster: str = ""               # 海报/封面绝对 URL
    poster_local: str = ""         # 本地路径（下载后）
    tags: list[str] = field(default_factory=list)
    organizer: str = ""
    description: str = ""
    extra: dict = field(default_factory=dict)
    crawled_at: str = ""

    # 派生字段（落盘时自动填充）
    status: str = ""               # upcoming | today | archived | unknown
    sort_key: str = ""             # 用于排序的 ISO 时间（archived 也会有反向 key）

    @property
    def uid(self) -> str:
        """去重主键：url + title 双因子 hash。"""
        key = (self.url or "") + "|" + (self.title or "")
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    def classify_status(self, now=None) -> None:
        """根据 start_time / end_time 判断活动状态。

        - upcoming  : 开始时间 > 当前时间
        - today     : 开始时间是今天 或 当前时间在 [start, end] 之间
        - archived  : 结束时间已过 (或只有 start 且早于今天)
        - unknown   : 没有任何时间信息（榜单/常青文章）
        """
        from datetime import datetime as _dt
        now = now or _dt.now()
        today_str = now.strftime("%Y-%m-%d")
        # 同时分析两个时间，end 缺则用 start
        s = self.start_time
        e = self.end_time or self.start_time
        if not s:
            self.status = "unknown"
            self.sort_key = "9999-99-99"        # 排到最后
            return
        try:
            s_dt = _dt.strptime(s[:16], "%Y-%m-%d %H:%M") if len(s) >= 16 \
                   else _dt.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            self.status = "unknown"
            self.sort_key = "9999-99-99"
            return
        try:
            e_dt = _dt.strptime(e[:16], "%Y-%m-%d %H:%M") if len(e) >= 16 \
                   else _dt.strptime(e[:10], "%Y-%m-%d 23:59"[:16]) \
                        if len(e) >= 10 else s_dt
        except ValueError:
            e_dt = s_dt

        if e_dt < now and s[:10] != today_str:
            self.status = "archived"
            # 倒序排列归档：越近的越靠前 → key 取负数效果
            # 我们用 "5" 前缀，再用 (9999-9999) - year-month-day 做倒置
            self.sort_key = "9_" + (s[:10] if s else "")  # 9_ 排在 1_ 后面
        elif s[:10] == today_str or (s_dt <= now <= e_dt):
            self.status = "today"
            self.sort_key = "1_" + s[:16]
        else:
            self.status = "upcoming"
            self.sort_key = "2_" + s[:16]


# ---------------------------------------------------------------------------
# HTTP 客户端
# ---------------------------------------------------------------------------
class HTTPClient:
    """带重试、随机延迟、UA 池、可选 verify=False 的 httpx 封装。"""

    def __init__(
        self,
        timeout: float = 12.0,
        verify: bool = True,
        proxy: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        sleep_range: tuple[float, float] = (0.15, 0.45),
    ):
        headers = {
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if extra_headers:
            # 支持显式删除：value=None 时移除该 header
            for k, v in extra_headers.items():
                if v is None:
                    headers.pop(k, None)
                else:
                    headers[k] = v
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            verify=verify,
            headers=headers,
            proxy=proxy,
            http2=False,
        )
        self.sleep_range = sleep_range

    def close(self):
        self.client.close()

    def _sleep(self):
        time.sleep(random.uniform(*self.sleep_range))

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),  # 5xx 至多重试一次，避免长尾
        wait=wait_exponential(multiplier=1.0, min=1.0, max=4),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def get(self, url: str, *, headers: Optional[dict] = None,
            params: Optional[dict] = None) -> httpx.Response:
        self._sleep()
        r = self.client.get(url, headers=headers, params=params)
        # 仅对 500/503 真正"忙"的错误码退避；502/504 通常是后端挂了，重试无用
        if r.status_code in (500, 503):
            raise httpx.HTTPStatusError(
                f"server {r.status_code}", request=r.request, response=r
            )
        # 自动绕过本地宝拼图验证（透明、对调用方无感知）
        if r.status_code == 200 and "请完成拼图验证" in r.text[:2000]:
            from .bypass import bendibao_puzzle_bypass
            if bendibao_puzzle_bypass(self.client, url, r.text):
                # 携带新 cookie 重试一次
                self._sleep()
                r = self.client.get(url, headers=headers, params=params)
        return r

    def text(self, url: str, **kw) -> str:
        r = self.get(url, **kw)
        # httpx 在 charset 缺失时会按 latin-1 解码，对中文站需要兜底
        enc = (r.encoding or "").lower()
        if not enc or enc in ("iso-8859-1", "ascii"):
            r.encoding = r.apparent_encoding or "utf-8"
        return r.text


# ---------------------------------------------------------------------------
# 适配器基类
# ---------------------------------------------------------------------------
class BaseAdapter:
    source: str = ""           # 唯一标识
    source_name: str = ""      # 中文名
    base_url: str = ""
    enabled: bool = True
    needs_browser: bool = False  # 标记需要 Playwright 才能拿数据

    # HTTP 配置
    verify_ssl: bool = True
    extra_headers: dict | None = None

    def __init__(self, max_pages: int = 2):
        self.max_pages = max_pages
        self.http = HTTPClient(
            verify=self.verify_ssl,
            extra_headers=self.extra_headers,
        )
        self.logger = logging.getLogger(f"crawler.{self.source}")

    # 子类实现
    def fetch(self) -> Iterator[Event]:
        raise NotImplementedError

    # 辅助
    def absolute(self, url: str, *, base: Optional[str] = None) -> str:
        if not url:
            return ""
        return urljoin(base or self.base_url, url)

    def close(self):
        self.http.close()


# ---------------------------------------------------------------------------
# Playwright 辅助：用于 SPA 站点 (时代美术馆/K11/InfoQ 等)
# ---------------------------------------------------------------------------
_PW_AVAILABLE = None


def _check_playwright():
    """检测 Playwright 是否可用，懒加载，缓存结果。"""
    global _PW_AVAILABLE
    if _PW_AVAILABLE is not None:
        return _PW_AVAILABLE
    try:
        from playwright.sync_api import sync_playwright   # noqa: F401
        _PW_AVAILABLE = True
    except ImportError:
        _PW_AVAILABLE = False
    return _PW_AVAILABLE


def fetch_with_browser(url: str, *, wait: int = 1500,
                       wait_until: str = "domcontentloaded",
                       timeout: int = 15000) -> str:
    """用 Playwright 拿一个 SPA 页的渲染后 HTML。"""
    if not _check_playwright():
        return ""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, wait_until=wait_until, timeout=timeout)
            page.wait_for_timeout(wait)
            return page.content()
        finally:
            browser.close()


def safe_iter(adapter: BaseAdapter) -> list[Event]:
    """运行单个 adapter，捕获所有异常，返回事件列表。

    对每条 Event 做最终兜底：
      - 若 start_time 为空，尝试从 raw_time / title / description / address
        中再解析一次，提高完整性。
      - 城市归一化（"广州市" → "广州"）
    """
    from .utils import (find_time_in_text, parse_time_range,
                        normalize_city, normalize_category)

    out: list[Event] = []
    try:
        for ev in adapter.fetch():
            if not ev.title or not ev.url:
                continue
            # ---- 全局兜底时间解析 ----
            if not ev.start_time:
                # 1. raw_time 重解析
                if ev.raw_time:
                    s, e = parse_time_range(ev.raw_time)
                    if s:
                        ev.start_time, ev.end_time = s, ev.end_time or e
                # 2. description 兜底
                if not ev.start_time and ev.description:
                    raw, s, e = find_time_in_text(ev.description)
                    if s:
                        ev.start_time = s
                        ev.end_time = ev.end_time or e
                        ev.raw_time = ev.raw_time or raw
                # 3. title 里直接写明的日期
                if not ev.start_time and ev.title:
                    raw, s, e = find_time_in_text(ev.title)
                    if s:
                        ev.start_time = s
                        ev.end_time = ev.end_time or e
                        ev.raw_time = ev.raw_time or raw
            # 城市归一化
            ev.city = normalize_city(ev.city)
            # 分类归一化（合并 招聘会/宣讲会/招聘、解决 标签 overlap）
            ev.category = normalize_category(ev.category, ev.title, ev.url)
            # 计算状态 + 排序键
            ev.classify_status()
            out.append(ev)
    except Exception as e:
        log.exception("[%s] adapter failed: %s", adapter.source, e)
    finally:
        adapter.close()
    return out

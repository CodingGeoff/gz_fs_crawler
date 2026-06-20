"""大麦网搜索 search.damai.cn

实测：直接访问 search.damai.cn/searchajax.html 触发风控 x5secdata，
返回一个跳转 punish 页面（HTML ~1KB）。要绕过需要：
  - 真实浏览器拿 cookie；或
  - 使用 search.damai.cn 提供的官方 JSONP 接口 + 滑块；或
  - 走 m.damai.cn 移动端（更稳定）。

当前 adapter：尝试 m 端搜索页，若拿到 HTML > 5KB 才解析；否则跳过。
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Iterator
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_price, parse_time_range


class Damai(BaseAdapter):
    source = "damai"
    source_name = "大麦网"
    base_url = "https://search.damai.cn"
    extra_headers = {
        "Referer": "https://www.damai.cn/",
    }

    def fetch(self) -> Iterator[Event]:
        import httpx as _h
        for city in ["广州", "佛山"]:
            url = f"https://m.damai.cn/damai/minilist/index.html?city={quote(city)}"
            try:
                r = _h.get(url, timeout=6.0, headers={"User-Agent": "Mozilla/5.0"})
                html = r.text
            except Exception as e:
                self.logger.info("damai %s fail: %s", city, e)
                continue
            if len(html) < 5000 or "x5secdata" in html or "punish" in html:
                self.logger.info(
                    "Damai %s blocked by x5sec WAF (HTML %d B) — skip; "
                    "请在本机带浏览器 cookie 重试.", city, len(html)
                )
                continue
            soup = BeautifulSoup(html, "lxml")
            # m 端列表卡片 selector 视频面而定，下方为通用兜底
            for a in soup.select("a[href*='/items/']"):
                title = clean(a.get_text())
                href = a["href"]
                if not title:
                    continue
                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="演出",
                    title=title,
                    url=href if href.startswith("http") else "https:" + href,
                    city=city,
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

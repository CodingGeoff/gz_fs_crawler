"""佛山市图书馆 www.fslib.com.cn

实测：HTTPS 握手超时（站点 TLS 配置异常 / 区域限制）。
当前实现：尝试 HTTP 端口；失败则跳过。
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Iterator
from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range


class FoshanLib(BaseAdapter):
    source = "foshan_lib"
    source_name = "佛山市图书馆"
    base_url = "http://www.fslib.com.cn"
    verify_ssl = False

    def fetch(self) -> Iterator[Event]:
        import httpx as _h
        try:
            r = _h.get(self.base_url + "/", timeout=4.0, verify=False,
                       headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            self.logger.info("fslib unreachable: %s (will skip)", e)
            return
        if r.status_code != 200:
            return
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href]"):
            href = a["href"]
            txt = clean(a.get_text())
            if not txt or len(txt) < 4:
                continue
            if any(k in txt for k in ["活动", "讲座", "电影", "展览", "沙龙"]):
                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="公益课",
                    title=txt[:80],
                    url=self.absolute(href),
                    city="佛山",
                    venue="佛山市图书馆",
                    price="免费",
                    price_min=0, price_max=0, is_free=True,
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

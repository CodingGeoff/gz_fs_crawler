"""广州博物馆 www.guangzhoumuseum.cn

主域 200 但仅返回一个跳转脚本到 /main/。需要去 /main/ 抓真实页面。
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Iterator
from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range


CANDIDATE_LIST_PATHS = [
    "/main/zlxx/",      # 展览信息
    "/main/news/",
    "/main/zlxxlist.html",
    "/main/news.html",
    "/cn/Exhibition/",
]


class GuangzhouMuseum(BaseAdapter):
    source = "gz_museum"
    source_name = "广州博物馆"
    base_url = "https://www.guangzhoumuseum.cn"

    def fetch(self) -> Iterator[Event]:
        # 嗅探可用列表页
        list_url = None
        for p in CANDIDATE_LIST_PATHS:
            try:
                r = self.http.get(self.base_url + p)
                if r.status_code == 200 and len(r.text) > 3000:
                    list_url = self.base_url + p
                    break
            except Exception:
                continue
        if not list_url:
            try:
                r = self.http.get(self.base_url + "/")
                m = re.search(r'location\.href\s*=\s*[\'"]([^\'"]+)[\'"]', r.text)
                if m:
                    list_url = self.absolute(m.group(1))
            except Exception:
                pass
        if not list_url:
            self.logger.info("gz_museum: 未探测到可用列表 URL，跳过")
            return

        try:
            html = self.http.text(list_url)
        except Exception as e:
            self.logger.warning("gz_museum list fail: %s", e)
            return
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            txt = clean(a.get_text())
            if not txt or len(txt) < 5:
                continue
            url = self.absolute(href, base=list_url)
            if url in seen:
                continue
            seen.add(url)
            if any(k in txt for k in ["展", "展览", "活动", "讲座"]):
                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="展览",
                    title=txt[:80],
                    url=url,
                    city="广州",
                    venue="广州博物馆",
                    price="免费",
                    price_min=0, price_max=0, is_free=True,
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

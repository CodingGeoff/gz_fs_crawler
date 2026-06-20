"""何香凝美术馆 hxnart.com (深圳，但常和广东艺术圈联动)。

入口：/  首页有展览列表
详情链接为 .aspx 路径
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


class HXNArt(BaseAdapter):
    source = "hxn_art"
    source_name = "何香凝美术馆"
    base_url = "http://www.hxnart.com"

    def fetch(self) -> Iterator[Event]:
        try:
            html = self.http.text(self.base_url + "/")
        except Exception as e:
            self.logger.warning("home: %s", e)
            return

        soup = BeautifulSoup(html, "lxml")
        # 找展览节点 - title 含展览相关字段
        seen = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            t = clean(a.get_text())
            if not t or len(t) < 6 or len(t) > 100:
                continue
            # 过滤导航
            if t in seen or any(x in t for x in ["更多", "首页", "关于", "联系"]):
                continue
            # 必须含艺术相关词
            if not any(k in t for k in ["展", "Exhibition", "Lecture",
                                          "讲座", "教育", "工作坊"]):
                continue
            seen.add(t)
            full = href if href.startswith("http") else self.base_url + (
                href if href.startswith("/") else "/" + href)
            # 时间从 title 推（无详情页结构稳定）
            _, start, end = find_time_in_text(t)
            yield Event(
                source=self.source,
                source_name=self.source_name,
                category="展览",
                title=t,
                url=full,
                city="深圳",
                venue="何香凝美术馆",
                address="深圳市南山区华侨城深南大道9013号",
                start_time=start,
                end_time=end,
                price="免费",
                price_min=0.0, price_max=0.0, is_free=True,
                description=t,
                crawled_at=datetime.now().isoformat(timespec="seconds"),
            )

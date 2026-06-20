"""活动行 - 城市=广州 / 佛山。

列表页服务端渲染，包含标题/海报/时间/地址/主办方。
详情页内容 JS 加载，但 og:meta 已有 title/description/image，足够补充海报。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import parse_time_range, parse_price, clean, extract_city


CITIES = ["广州", "佛山"]


class HuoDongXing(BaseAdapter):
    source = "huodongxing"
    source_name = "活动行"
    base_url = "https://www.huodongxing.com"

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        for city in CITIES:
            for page in range(1, self.max_pages + 1):
                url = f"{self.base_url}/events?city={quote(city)}&page={page}"
                try:
                    html = self.http.text(url)
                except Exception as e:
                    self.logger.warning("list %s p%d: %s", city, page, e)
                    continue
                soup = BeautifulSoup(html, "lxml")
                cards = soup.select(".search-tab-content-list-check .search-tab-content-item-mesh")
                if not cards:
                    cards = soup.select(".search-tab-content-item-mesh")
                self.logger.info("HDX city=%s page=%d cards=%d", city, page, len(cards))
                for card in cards:
                    ev = self._parse_card(card, city)
                    if not ev:
                        continue
                    if ev.url in seen:
                        continue
                    seen.add(ev.url)
                    yield ev

    def _parse_card(self, card, city_default: str) -> Event | None:
        title_a = card.select_one("a.item-title") or card.select_one("a[href*='/event/']")
        if not title_a:
            return None
        title_span = title_a.select_one("span")
        title = clean(title_span.get_text(" ", strip=True)) if title_span else clean(title_a.get_text(" ", strip=True))
        if not title:
            return None
        href = self.absolute(title_a.get("href", "").split("?")[0])

        # 海报
        img = card.select_one("img.item-logo")
        poster = img.get("src") if img else ""

        # 时间 & 地址
        dress = card.select_one(".item-dress")
        raw_time = ""
        addr = ""
        if dress:
            ps = dress.select("p")
            if ps:
                raw_time = clean(ps[0].get_text(" ", strip=True))
            addr_node = dress.select_one(".item-dress-pp")
            if addr_node:
                addr = clean(addr_node.get_text(" ", strip=True))

        start, end = parse_time_range(raw_time)

        # 主办方
        org = ""
        un = card.select_one(".user-name")
        if un:
            org = clean(un.get_text(strip=True))

        # 价格：列表页一般没有，标记未知
        price = ""
        category = self._classify(title)
        city = extract_city(addr or title) or city_default
        return Event(
            source=self.source,
            source_name=self.source_name,
            category=category,
            title=title,
            url=href,
            city=city,
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price=price,
            poster=poster,
            organizer=org,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

    @staticmethod
    def _classify(title: str) -> str:
        if any(k in title for k in ["展览会", "展", "博览会"]):
            return "展览"
        if any(k in title for k in ["论坛", "峰会", "大会", "沙龙", "分享会"]):
            return "讲座"
        if any(k in title for k in ["演唱会", "音乐节", "Live", "脱口秀"]):
            return "演出"
        if any(k in title for k in ["培训", "课程", "训练营", "workshop", "工作坊"]):
            return "公益课"
        return "活动"

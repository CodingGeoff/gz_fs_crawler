"""SOFAStack 蚂蚁云原生 - 技术活动 / 社区分享。

入口: https://www.sofastack.tech/activities/
详情: https://www.sofastack.tech/activities/<slug>/

页面是静态 SSG，HTML 中直接含 10+ 活动卡片。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


class SOFAStack(BaseAdapter):
    source = "sofastack"
    source_name = "SOFAStack·蚂蚁云原生"
    base_url = "https://www.sofastack.tech"

    def fetch(self) -> Iterator[Event]:
        try:
            html = self.http.text(f"{self.base_url}/activities/")
        except Exception as e:
            self.logger.warning("list: %s", e)
            return

        slugs = list(dict.fromkeys(re.findall(r'/activities/([\w\-]+)/?', html)))
        slugs = [s for s in slugs if len(s) > 5][:15]
        self.logger.info("SOFAStack: %d activities", len(slugs))

        for slug in slugs:
            try:
                ev = self._parse(slug)
                if ev:
                    yield ev
            except Exception as e:
                self.logger.warning("detail %s: %s", slug, e)

    def _parse(self, slug: str) -> Event | None:
        url = f"{self.base_url}/activities/{slug}/"
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")

        t = soup.select_one("title")
        title = clean(t.get_text()) if t else ""
        title = re.sub(r"\s*·\s*蚂蚁云原生架构SOFAStack.*$", "", title)
        title = re.sub(r"\s+", " ", title)
        if not title:
            return None

        text = clean(soup.get_text("\n", strip=True))

        raw_time = ""
        for k in ("活动时间", "直播时间", "时间", "日期"):
            m = re.search(rf"{k}\s*[：:]\s*([^\n。]{{4,80}})", text)
            if m:
                raw_time = clean(m.group(1))
                break
        start, end = parse_time_range(raw_time) if raw_time else ("", "")
        if not start:
            _, start, end = find_time_in_text(text[:2000])

        # 地点（多为线上）
        addr = "线上"
        m = re.search(r"地\s*点\s*[:：]\s*([^\n。]{2,60})", text)
        if m:
            addr = clean(m.group(1))

        # 海报
        poster = ""
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if src and not src.startswith("data:") and "logo" not in src.lower():
                poster = src if src.startswith("http") else \
                         f"{self.base_url}{src}"
                break

        return Event(
            source=self.source,
            source_name=self.source_name,
            category="讲座沙龙",
            title=title,
            url=url,
            city="线上",
            venue="SOFA Channel",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0.0, price_max=0.0, is_free=True,
            poster=poster,
            organizer="蚂蚁集团",
            description=text[:300],
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

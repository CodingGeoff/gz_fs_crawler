"""GDG 社区 - Google Developer Groups (广佛/香港/深圳 tech meetup)。

数据源：https://gdg.community.dev/<slug>/
  广州: gdg-guangzhou
  深圳: gdg-shenzhen
  香港: gdg-hong-kong

Next.js SSR 站点，window.__NEXT_DATA__ 中含 prerenderData.upcomingEvents 和 pastEvents。
每个 event 对象有：title / description / start_date / event_type_title / url / cropped_picture_url

技术活动 100% 免费 / 免门票（GDG 性质）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterator

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range


CHAPTERS = [
    ("gdg-guangzhou", "广州"),
    ("gdg-shenzhen",  "深圳"),
    ("gdg-zhuhai",    "珠海"),
    ("gdg-dongguan",  "东莞"),
    ("gdg-hong-kong", "香港"),
]
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', re.S)


class GDGCommunity(BaseAdapter):
    source = "gdg_community"
    source_name = "GDG·Google开发者社区"
    base_url = "https://gdg.community.dev"

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        for slug, city in CHAPTERS:
            try:
                html = self.http.text(f"{self.base_url}/{slug}/")
            except Exception as e:
                self.logger.warning("chapter %s: %s", slug, e)
                continue
            m = _NEXT_RE.search(html)
            if not m:
                continue
            try:
                j = json.loads(m.group(1))
                pre = j["props"]["pageProps"]["prerenderData"]
            except (KeyError, json.JSONDecodeError):
                continue

            up = pre.get("upcomingEvents", {}).get("results", []) or []
            past = pre.get("pastEvents", {}).get("results", []) or []
            # 拿 upcoming + 最近 15 个 past
            items = up + past[:15]
            self.logger.info("GDG %s: %d upcoming + %d past",
                             slug, len(up), len(past[:15]))

            for it in items:
                url = it.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                title = clean(it.get("title", ""))
                if not title:
                    continue
                # start_date: "2026-06-13T05:30:00Z"
                start_raw = it.get("start_date", "")
                start, end = "", ""
                if start_raw:
                    # 转 ISO → "yyyy-mm-dd HH:MM"
                    try:
                        dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                        # GDG 用 UTC，转中国时间 (+8)
                        from datetime import timedelta
                        dt = dt + timedelta(hours=8)
                        start = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass

                poster = it.get("cropped_picture_url") or \
                         it.get("cropped_banner_url") or ""
                kind = it.get("event_type_title", "")
                desc = clean(it.get("description_short") or it.get("description") or "")[:300]

                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="讲座沙龙",
                    title=title,
                    url=url,
                    city=city,
                    venue="GDG " + city,
                    address=city,
                    start_time=start,
                    end_time=end,
                    raw_time=start_raw,
                    price="免费",
                    price_min=0.0, price_max=0.0, is_free=True,
                    poster=poster,
                    organizer=f"GDG {city}",
                    description=desc,
                    tags=[kind] if kind else [],
                    extra={"chapter": slug, "event_type": kind},
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

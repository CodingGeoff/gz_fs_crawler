"""Meetup.com 国际版 - 广州/深圳/珠海/东莞/佛山。

数据源：https://www.meetup.com/find/cn--<city-en>/
  广州 cn--guangzhou
  深圳 cn--shenzhen
  珠海 cn--zhuhai
  东莞 cn--dongguan
  佛山 cn--foshan

Next.js SSR：`__NEXT_DATA__` 含
  pageProps.eventsInLocation / thisWeekendEvents / todayEvents /
  topicalEventsMusic / Social / Outdoor / Sports / ...

每个 event 对象有完整字段：title / dateTime / endTime / eventUrl /
featuredEventPhoto.highResUrl / group.name / venue / eventType (PHYSICAL/ONLINE)
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterator

from ..base import BaseAdapter, Event
from ..utils import clean


CITIES = [
    ("cn--guangzhou", "广州"),
    ("cn--shenzhen",  "深圳"),
    ("cn--zhuhai",    "珠海"),
    ("cn--dongguan",  "东莞"),
    ("cn--foshan",    "佛山"),
]
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', re.S)


class MeetupCom(BaseAdapter):
    source = "meetup_com"
    source_name = "Meetup.com·珠三角"
    base_url = "https://www.meetup.com"

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        for slug, city in CITIES:
            url = f"{self.base_url}/find/{slug}/"
            try:
                html = self.http.text(url)
            except Exception as e:
                self.logger.warning("%s: %s", slug, e)
                continue
            m = _NEXT_RE.search(html)
            if not m:
                continue
            try:
                j = json.loads(m.group(1))
                pp = j["props"]["pageProps"]
            except (KeyError, json.JSONDecodeError):
                continue

            evs = []
            for k, v in pp.items():
                if isinstance(v, list) and v and isinstance(v[0], dict) \
                        and v[0].get("__typename") == "Event":
                    evs.extend(v)
            # 去重 by id
            seen_id = set()
            unique = []
            for e in evs:
                if e.get("id") in seen_id:
                    continue
                seen_id.add(e.get("id"))
                unique.append(e)
            self.logger.info("Meetup.com %s: %d events", city, len(unique))

            for e in unique:
                url = e.get("eventUrl", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                title = clean(e.get("title", ""))
                if not title:
                    continue

                # 时间 (ISO 含 +08:00)
                start = self._iso_to_local(e.get("dateTime", ""))
                end = self._iso_to_local(e.get("endTime", ""))

                # 海报
                poster = ""
                fp = e.get("featuredEventPhoto") or e.get("displayPhoto") or {}
                if fp:
                    poster = fp.get("highResUrl", "") or fp.get("source", "")

                # 主办方 / 群组
                grp = e.get("group") or {}
                org = clean(grp.get("name", ""))

                # 在线/线下
                is_online = e.get("isOnline") or e.get("eventType") == "ONLINE"
                addr = "线上活动" if is_online else city

                # 费用：fee_settings
                fee = e.get("feeSettings")
                if fee:
                    amt = fee.get("amount", 0)
                    if amt and amt > 0:
                        price = f"¥{amt} (Meetup)"
                        is_free, pmin, pmax = False, amt, amt
                    else:
                        price = "免费"; is_free = True; pmin = pmax = 0.0
                else:
                    price = "免费"; is_free = True; pmin = pmax = 0.0

                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="社交聚会" if grp and any(k in grp.get("name","").lower()
                            for k in ("run","sport","party","social","language")) else "讲座沙龙",
                    title=title,
                    url=url,
                    city=city,
                    venue=org,
                    address=addr,
                    start_time=start,
                    end_time=end,
                    raw_time=e.get("dateTime", ""),
                    price=price,
                    price_min=pmin, price_max=pmax, is_free=is_free,
                    poster=poster,
                    organizer=org,
                    description=f"{org} 在 {city} 组织的 Meetup 活动" if org else "",
                    extra={
                        "going": e.get("going", {}).get("totalCount"),
                        "is_online": is_online,
                        "event_type": e.get("eventType"),
                    },
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

    @staticmethod
    def _iso_to_local(s: str) -> str:
        """2026-06-10T18:00:00+08:00 → 2026-06-10 18:00"""
        if not s:
            return ""
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return s[:16]

"""思否 SegmentFault - 广州技术活动 / 大学生友好的技术沙龙。

入口: https://segmentfault.com/events?city=guangzhou
详情: https://segmentfault.com/e/<id>

✅ 优势：Next.js SSR，`__NEXT_DATA__` 中含完整 event 对象
  字段: name / start (unix ts) / end / city_name / address / banner_url /
        sign_url / category / parsed_text / sponsors_list
"""
from __future__ import annotations

import concurrent.futures as _cf
import json
import re
from datetime import datetime
from typing import Iterator, Optional

from ..base import BaseAdapter, Event
from ..utils import clean


_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', re.S)


class SegmentFaultGZ(BaseAdapter):
    source = "segmentfault_gz"
    source_name = "思否·广州技术活动"
    base_url = "https://segmentfault.com"
    parallel_workers = 5

    def fetch(self) -> Iterator[Event]:
        # 拿列表
        try:
            html = self.http.text(f"{self.base_url}/events?city=guangzhou")
        except Exception as e:
            self.logger.warning("list fail: %s", e)
            return

        ids = list(dict.fromkeys(re.findall(r'/e/(\d+)', html)))[:30]
        self.logger.info("segmentfault: queue %d events", len(ids))

        def _one(eid):
            try:
                return self._parse(f"{self.base_url}/e/{eid}")
            except Exception as e:
                self.logger.warning("detail %s: %s", eid, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, ids):
                if ev:
                    yield ev

    def _parse(self, url: str) -> Optional[Event]:
        html = self.http.text(url)
        m = _NEXT_RE.search(html)
        if not m:
            return None
        try:
            j = json.loads(m.group(1))
            ev = j["props"]["pageProps"]["initialState"]["activityDetail"]["detailData"]["event"]
        except (KeyError, json.JSONDecodeError):
            return None

        title = clean(ev.get("name", ""))
        if not title:
            return None

        # 时间：start/end 是 unix 秒
        start_ts = ev.get("start") or 0
        end_ts = ev.get("end") or 0
        start = (datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M")
                 if start_ts else "")
        end = (datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d %H:%M")
               if end_ts else "")
        raw_time = f"{start} - {end}" if end else start

        city = clean(ev.get("city_name", "")) or "广州"
        addr = clean(ev.get("address", "")) or city
        poster = ev.get("banner_url", "")
        if poster and not poster.startswith("http"):
            poster = "https:" + poster if poster.startswith("//") else \
                     "https://segmentfault.com" + poster

        # 主办方
        org = ""
        spons = ev.get("sponsors_list") or []
        if spons:
            org = " / ".join(s.get("name", "") for s in spons if s.get("name"))

        # 描述（去 HTML 标签）
        desc = ev.get("parsed_text", "")
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = clean(desc)[:300]

        # 报名链接
        sign_url = ev.get("sign_url", "")

        return Event(
            source=self.source,
            source_name=self.source_name,
            category="讲座",     # 多为技术分享/沙龙
            title=title,
            url=url,
            city=city,
            address=addr,
            venue=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0.0, price_max=0.0, is_free=True,
            poster=poster,
            organizer=org,
            description=desc,
            extra={
                "sign_url": sign_url,
                "category_id": ev.get("category"),
            },
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

"""广州图书馆 - 活动月历。

发现真实数据接口 (JSON)：
   POST https://action.gzlib.org.cn/action/mb/mobileApi
   data: cmd=getMonthActions / getDateActions, libcode=GT, date=YYYY-MM-DD

详情页：weixin.do?cmd=viewAction&isWL=0&id=<id>
海报：/action/presentpic/<play_bill_pic>
"""
from __future__ import annotations

import re
import json
from datetime import datetime, timedelta
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import parse_time_range, clean


API = "https://action.gzlib.org.cn/action/mb/mobileApi"
DETAIL = "https://action.gzlib.org.cn/action/mb/weixin.do?cmd=viewAction&isWL=0&id={}"
POSTER = "https://action.gzlib.org.cn/action/presentpic/{}"


class GuangzhouLib(BaseAdapter):
    source = "gzlib"
    source_name = "广州图书馆"
    base_url = "https://action.gzlib.org.cn"

    def fetch(self) -> Iterator[Event]:
        # 抓接下来 14 天；带 Referer + 15s timeout + 单点重试一次
        seen: set[str] = set()
        today = datetime.now()
        fail_streak = 0
        headers = {
            "Referer": "https://action.gzlib.org.cn/action/mb/monthactions.jsp?mid=&isWL=0",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://action.gzlib.org.cn",
        }
        for offset in range(0, 14):
            if fail_streak >= 5:
                self.logger.info("gzlib API 连续超时 5 次, 放弃后续日期")
                break
            d = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
            arr = []
            for attempt in range(2):
                try:
                    r = self.http.client.post(
                        API, data={"cmd": "getDateActions",
                                   "libcode": "GT", "date": d},
                        headers=headers,
                        timeout=15.0,
                    )
                    arr = r.json() if r.text and r.text.strip() else []
                    fail_streak = 0
                    break
                except Exception as e:
                    if attempt == 1:
                        fail_streak += 1
                        self.logger.warning("gzlib %s: %s", d, e)
            for it in arr:
                aid = str(it.get("id") or "")
                if not aid or aid in seen:
                    continue
                seen.add(aid)
                title = clean(it.get("title", ""))
                if not title:
                    continue
                raw_time = clean(it.get("act_time", "")) or d
                addr = clean(it.get("act_site", ""))
                pic = it.get("play_bill_pic") or ""
                poster = POSTER.format(pic) if pic and pic != "null" else ""
                start, end = parse_time_range(raw_time)
                if not start:
                    start = d
                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="讲座" if "讲座" in title else "公益课",
                    title=title,
                    url=DETAIL.format(aid),
                    city="广州",
                    venue="广州图书馆",
                    address=addr or "广州市广州图书馆",
                    start_time=start,
                    end_time=end,
                    raw_time=raw_time,
                    price="免费",
                    price_min=0, price_max=0, is_free=True,
                    poster=poster,
                    extra={"state": it.get("state_name", "")},
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

"""Eventbrite 国际版 - 广州 / 深圳 / 珠海。

数据源: https://www.eventbrite.com/d/china--<city>/events/
内嵌 window.__SERVER_DATA__ 含 jsonld[0].itemListElement，
每个 item 是 schema.org Event 对象，字段：
  name / startDate / endDate / url / image / description /
  location.name / location.address / eventAttendanceMode
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterator

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, detect_hk_macau


CITIES = [
    ("guangzhou", "广州"),
    ("shenzhen",  "深圳"),
    ("zhuhai",    "珠海"),
]
_SERVER_DATA_RE = re.compile(r'window\.__SERVER_DATA__\s*=\s*(\{.+)', re.S)


def _extract_json_obj(src: str) -> str:
    """从 src 第一个 { 开始，根据括号配对找出完整 JSON 字符串。"""
    in_str = False
    esc = False
    depth = 0
    for i, c in enumerate(src):
        if esc:
            esc = False
            continue
        if c == '\\':
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[:i + 1]
    return ""


class EventbriteGZ(BaseAdapter):
    source = "eventbrite"
    source_name = "Eventbrite·珠三角"
    base_url = "https://www.eventbrite.com"

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        for slug, city in CITIES:
            url = f"{self.base_url}/d/china--{slug}/events/"
            try:
                html = self.http.text(url)
            except Exception as e:
                self.logger.warning("%s: %s", city, e)
                continue
            m = _SERVER_DATA_RE.search(html)
            if not m:
                continue
            js = _extract_json_obj(m.group(1))
            if not js:
                continue
            try:
                j = json.loads(js)
                jl = j.get("jsonld", [])
                items = []
                for b in jl:
                    items.extend(b.get("itemListElement", []) or [])
            except Exception:
                continue

            self.logger.info("Eventbrite %s: %d events", city, len(items))
            for it in items:
                e = it.get("item") if "item" in it else it
                if not isinstance(e, dict):
                    continue
                url = e.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                title = clean(e.get("name", ""))
                if not title:
                    continue

                start_raw = e.get("startDate", "")
                end_raw = e.get("endDate", "")
                start, end = self._parse_iso(start_raw), self._parse_iso(end_raw)
                if not start:
                    start, _ = parse_time_range(start_raw)
                if not end:
                    end, _ = parse_time_range(end_raw)

                # 地址
                loc = e.get("location", {})
                if isinstance(loc, dict):
                    venue = clean(loc.get("name", ""))
                    addr_part = loc.get("address", {})
                    addr_str = ""
                    if isinstance(addr_part, dict):
                        addr_str = " ".join(
                            filter(None, [
                                addr_part.get("streetAddress", ""),
                                addr_part.get("addressLocality", ""),
                            ])
                        )
                    addr = clean(addr_str) or venue
                else:
                    venue, addr = "", ""

                # 在线/线下
                mode = e.get("eventAttendanceMode", "")
                is_online = "Online" in mode

                # 校验实际举办地：Eventbrite 的 china--shenzhen/zhuhai 列表
                # 会混入大量香港/澳门活动，按 venue+address 修正 city
                real_city = detect_hk_macau(venue + " " + addr)
                if real_city:
                    city = real_city

                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="讲座沙龙",  # Eventbrite 多为商务/技术活动
                    title=title,
                    url=url,
                    city=city,
                    venue=venue or "",
                    address=addr or ("线上活动" if is_online else city),
                    start_time=start,
                    end_time=end,
                    raw_time=start_raw,
                    price="",                     # Eventbrite JSON-LD 没价格
                    is_free=None,
                    poster=e.get("image", ""),
                    description=clean(e.get("description", ""))[:300],
                    extra={"mode": mode},
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )

    @staticmethod
    def _parse_iso(s: str) -> str:
        if not s:
            return ""
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M") if dt.hour or dt.minute \
                   else dt.strftime("%Y-%m-%d")
        except Exception:
            return s[:16] if len(s) >= 16 else s[:10] if len(s) >= 10 else ""

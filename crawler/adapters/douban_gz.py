"""豆瓣同城 - 广州。

入口列表页（按一周维度，按类别拆开抓全）:
  https://guangzhou.douban.com/events/week-all
  https://guangzhou.douban.com/events/week-music
  https://guangzhou.douban.com/events/week-exhibition
  ...

详情页：https://www.douban.com/event/{id}/
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import parse_time_range, parse_price, clean, extract_city


# 注意：先抓有明确类别的，再抓 all 兜底，确保事件分类是更具体的那个
CATEGORIES = {
    "music":       "演出",
    "drama":       "演出",
    "exhibition":  "展览",
    "salon":       "讲座",
    "film":        "活动",
    "commonweal":  "公益课",
    "party":       "活动",
    "sports":      "活动",
    "travel":      "活动",
    "all":         "活动",
}


class DoubanGZ(BaseAdapter):
    source = "douban_gz"
    source_name = "豆瓣同城·广州"
    base_url = "https://guangzhou.douban.com"

    parallel_workers = 6   # 豆瓣对并发敏感，6 已经够快

    def fetch(self) -> Iterator[Event]:
        # 1. 各分类抓出 url+期望类别
        queue: list[tuple[str, str]] = []
        seen_eid: set[str] = set()
        for cat, cat_zh in CATEGORIES.items():
            url = f"{self.base_url}/events/week-{cat}"
            try:
                html = self.http.text(url)
            except Exception as e:
                self.logger.warning("list page failed %s: %s", url, e)
                continue
            links = {a["href"] for a in BeautifulSoup(html, "lxml")
                     .select("a[href*='/event/']")
                     if re.search(r"/event/\d+/?$", a["href"])}
            count = 0
            for href in links:
                eid_match = re.search(r"/event/(\d+)", href)
                if not eid_match: continue
                eid = eid_match.group(1)
                if eid in seen_eid: continue
                seen_eid.add(eid)
                queue.append((href, cat_zh))
                count += 1
                # travel/sports/party 多抓些（这些类目活动多但单条少）
                limit = 15 if cat in ("travel", "party", "sports", "all") else 10
                if count >= limit: break
            self.logger.info("category=%s queued %d events", cat, count)

        self.logger.info("douban: parallel fetch %d events", len(queue))

        def _one(args):
            url, cat = args
            try:
                return self._parse_detail(url, cat)
            except Exception as e:
                self.logger.warning("event detail failed %s: %s", url, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, queue):
                if ev:
                    yield ev

    def _parse_detail(self, url: str, category: str) -> Event | None:
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.select_one("h1")
        if not h1:
            return None
        title = clean(h1.get_text(" ", strip=True))
        # 去掉「即将开始」等状态尾巴
        title = re.sub(r"\s+(即将开始|进行中|已结束).*$", "", title)

        info = soup.select_one(".event-info")
        info_text = clean(info.get_text(" | ", strip=True)) if info else ""

        # 时间
        raw_time = ""
        time_node = soup.select_one(".event-info li[class*='time'], .event-info time")
        if time_node:
            raw_time = clean(time_node.get_text(" ", strip=True))
        if not raw_time:
            m = re.search(r"时间:?\s*\|?\s*([^|]+(?:\|[^|]+){0,3})", info_text)
            if m:
                raw_time = clean(m.group(1))[:200]
        start, end = parse_time_range(raw_time or info_text)

        # 地点 — 使用 itemprop=address 锁定，避免吞下后续字段
        addr = ""
        addr_span = soup.select_one("span[itemprop='address']")
        if addr_span:
            addr = clean(addr_span.get_text(" ", strip=True))
        if not addr:
            loc_li = soup.select(".event-info li")
            for li in loc_li:
                t = li.get_text(" ", strip=True)
                if t.startswith("地点"):
                    addr = clean(t.replace("地点:", "").replace("地点", ""))
                    break
        # 去掉拼到末尾的"费用"等噪音
        addr = re.split(r"\s*\|\s*费用|\s*费用[:：]", addr)[0].strip(" |·")
        loc_li = soup.select(".event-info li")

        # 价格
        price = ""
        for li in loc_li:
            t = li.get_text(" ", strip=True)
            if "费用" in t:
                price = clean(t.replace("费用:", "").replace("费用", ""))
                break
        if not price:
            m = re.search(r"费用[:：]?\s*\|?\s*([^|]+)", info_text)
            if m:
                price = clean(m.group(1))[:80]
        pmin, pmax, is_free = parse_price(price)

        # 海报：取 event_poster 域名的图
        poster = ""
        for img in soup.select("img"):
            src = img.get("src") or img.get("data-src") or ""
            if "event_poster" in src:
                poster = src
                break
        if not poster:
            # 第二优先：og:image
            og = soup.select_one("meta[property='og:image']")
            if og:
                poster = og.get("content", "")

        # 主办
        organizer = ""
        for li in loc_li:
            t = li.get_text(" ", strip=True)
            if "信息提供者" in t or "主办" in t:
                organizer = clean(re.sub(r"^[^:：]+[:：]", "", t))[:80]
                break

        # 描述
        desc_node = soup.select_one("#link-report, .event-detail")
        description = clean(desc_node.get_text(" ", strip=True))[:600] if desc_node else ""

        city = extract_city(addr) or "广州"
        return Event(
            source=self.source,
            source_name=self.source_name,
            category=category,
            title=title,
            url=url,
            city=city,
            venue="",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price=price,
            price_min=pmin,
            price_max=pmax,
            is_free=is_free,
            poster=poster,
            organizer=organizer,
            description=description,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

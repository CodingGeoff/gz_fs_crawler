"""中山大学哲学系 - 哲学讲座 / 学术活动。

入口：https://philosophy.sysu.edu.cn/  (首页直接列出最新 event)
     /ae/lecture    讲座
     /ae/meeting    会议
详情：/event/<id>

详情页字段在正文中： "时间：xxx 地点：锡昌堂xxx 主讲：xxx"
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


class SYSUPhilosophy(BaseAdapter):
    source = "sysu_philosophy"
    source_name = "中山大学哲学系"
    base_url = "https://philosophy.sysu.edu.cn"
    parallel_workers = 5

    def fetch(self) -> Iterator[Event]:
        # 首页 + 学术讲座/会议子页都收集
        ids: set[str] = set()
        for path in ["/", "/ae/lecture", "/ae/meeting", "/ae/visit-lf"]:
            try:
                html = self.http.text(self.base_url + path)
            except Exception as e:
                self.logger.warning("page %s: %s", path, e)
                continue
            for eid in re.findall(r'/event/(\d+)', html):
                ids.add(eid)
        ids = list(ids)[:30]
        self.logger.info("SYSU 哲学系: %d events", len(ids))

        def _one(eid):
            try:
                return self._parse(f"{self.base_url}/event/{eid}")
            except Exception as e:
                self.logger.warning("detail %s: %s", eid, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, ids):
                if ev:
                    yield ev

    def _parse(self, url: str) -> Event | None:
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")
        # title
        t = soup.select_one("title")
        title = clean(t.get_text()) if t else ""
        title = re.sub(r"\s*\|\s*中山大学哲学系.*$", "", title)
        if not title:
            return None

        # 提取时间/地点/主讲
        text = soup.get_text(" ", strip=True)
        # 时间
        raw_time = ""
        for k in ("讲座时间", "会议时间", "时间"):
            m = re.search(rf"{k}\s*[:：]\s*([^\s地主主持讲嘉]{{4,80}})", text)
            if m:
                raw_time = clean(m.group(1))
                break
        start, end = parse_time_range(raw_time) if raw_time else ("", "")
        if not start:
            _, start, end = find_time_in_text(text[:2000])

        # 地点
        addr = ""
        for k in ("讲座地点", "会议地点", "地点", "地址"):
            m = re.search(rf"{k}\s*[:：]\s*([^\s时主讲嘉]{{2,80}})", text)
            if m:
                addr = clean(m.group(1))
                break
        # 兜底 - 中大常用场馆
        if not addr:
            for venue in ("锡昌堂", "马丁堂", "怀士堂", "梁銶琚", "怀士堂", "中大"):
                m = re.search(rf"({venue}[\u4e00-\u9fff\d]{{0,20}})", text)
                if m:
                    addr = m.group(1)
                    break

        # 主讲 (主办方)
        org = ""
        m = re.search(r"主讲\s*[:：]\s*([^\s。\n]{2,40})", text)
        if m:
            org = clean(m.group(1))

        # 海报
        poster = ""
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src and not src.startswith("data:") and "logo" not in src.lower():
                if src.startswith("/"):
                    src = self.base_url + src
                poster = src
                break

        # 描述
        body_node = soup.select_one(".article-content, .content, .article, main")
        desc = ""
        if body_node:
            desc = clean(body_node.get_text(" ", strip=True))[:400]

        return Event(
            source=self.source,
            source_name=self.source_name,
            category="讲座沙龙",
            title=title,
            url=url,
            city="广州",
            district="海珠",
            venue=addr or "中山大学哲学系",
            address=addr or "广州市海珠区中山大学",
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0.0, price_max=0.0, is_free=True,
            poster=poster,
            organizer=org,
            description=desc,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

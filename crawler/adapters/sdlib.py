"""顺德图书馆 - 活动 / 公益电影 / 阅读活动。

入口：
  https://www.sdlib.com.cn/                       (首页直接列了 20+ 活动)
  https://www.sdlib.com.cn/home/index/activity.html (汇总 hub)
详情:
  https://www.sdlib.com.cn/home/article/detail/id/<id>.html

详情页结构：
  h4.text-center           标题
  p.text-center            "加入时间：YYYY-MM-DD HH:MM   访问量：N   信息来源:"
  div.thumbnail            正文（含图片 + "5月17日下午..." 这类时间）
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


class ShundeLib(BaseAdapter):
    source = "sdlib"
    source_name = "顺德图书馆"
    base_url = "https://www.sdlib.com.cn"

    HUB_URLS = [
        "/",
        "/home/index/activity.html",
    ]
    parallel_workers = 6

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        queue: list[str] = []
        for hub in self.HUB_URLS:
            try:
                html = self.http.text(self.base_url + hub)
            except Exception as e:
                self.logger.warning("hub %s: %s", hub, e)
                continue
            soup = BeautifulSoup(html, "lxml")
            hrefs = [self.absolute(a["href"])
                     for a in soup.select("a[href*='/home/article/detail/id/']")]
            hrefs = list(dict.fromkeys(hrefs))[:30]
            for href in hrefs:
                if href in seen:
                    continue
                seen.add(href)
                queue.append(href)

        if not queue:
            return

        def _one(href):
            try:
                return self._parse_detail(href)
            except Exception as e:
                self.logger.warning("detail %s: %s", href, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, queue):
                if ev:
                    yield ev

    def _parse_detail(self, url: str) -> Event | None:
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")

        # ---- 标题：h4.text-center 是页面正题 ----
        h4 = soup.select_one("h4.text-center") or soup.select_one("h4")
        if h4:
            title = clean(h4.get_text(" ", strip=True))
        else:
            t = soup.select_one("title")
            title = clean(t.get_text()) if t else ""
        title = re.sub(r"\s*-\s*顺德图书馆.*$", "", title)
        title = re.sub(r"^顺德图书馆[_\-:：]+\s*", "", title)
        if not title:
            return None

        # ---- 发布时间（兜底用） ----
        published = ""
        for p in soup.select("p.text-center"):
            txt = clean(p.get_text(" ", strip=True))
            m = re.search(r"加入时间[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2})?)",
                          txt)
            if m:
                published = m.group(1)
                break

        # ---- 正文 ----
        content = (soup.select_one(".thumbnail") or
                   soup.select_one(".article") or
                   soup.select_one("#content"))
        body_text = clean(content.get_text(" ", strip=True)) if content else ""

        # ---- 海报：正文里第一张非 logo 图 ----
        poster = ""
        if content:
            for img in content.select("img"):
                src = img.get("src") or img.get("data-src") or ""
                if not src or any(k in src.lower() for k in ("logo", "icon")):
                    continue
                poster = self.absolute(src)
                break

        # ---- 时间：优先从正文找，否则用 published（写作日期） ----
        raw_time, start, end = find_time_in_text(body_text + "\n" + title)
        if not start and published:
            raw_time = published
            start, end = parse_time_range(published)

        # ---- 地址 ----
        addr = ""
        m = re.search(
            r"(?:活动地点|地点|地址|场地)\s*[:：]\s*([^\n。；;]{2,60})", body_text)
        if m:
            addr = clean(m.group(1))
        addr = addr or "佛山市顺德区顺德图书馆"

        # ---- 分类 ----
        category = "公益课"
        if "电影" in title:
            category = "活动"
        elif "讲座" in title or "沙龙" in title:
            category = "讲座"
        elif "展" in title:
            category = "展览"
        elif "演出" in title or "音乐" in title:
            category = "演出"

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=category,
            title=title,
            url=url,
            city="佛山",
            district="顺德",
            venue="顺德图书馆",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0, price_max=0, is_free=True,
            poster=poster,
            description=body_text[:500],
            extra={"published": published},
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

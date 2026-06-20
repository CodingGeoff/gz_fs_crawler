"""越秀公共数字文化云 (壹点云)。

主活动入口 /whhd/index 服务端直接渲染了卡片列表，包含：
  - 标题 (h3.aui-ellipsis-1)
  - 海报 (img.lazy 的 data-original)
  - 日期/时间/地点 (3 个 <p>)
  - 详情链接 content0.jsp?id=xxxx
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import parse_time_range, clean


HUBS = [
    # 顺序很重要：先抓信息最完整的 hub
    "/whhd/hdyy",       # 活动预约（含完整日期 yyyy-mm-dd HH:MM）
    "/whhd/pphd.jsp",   # 品牌活动
    "/gwgk/szzg.jsp",   # 展览
    "/whhd/index",      # 文化活动主页（首屏 20+ 张卡片；日期简略，仅 HH:MM）
]


class IwhYun(BaseAdapter):
    source = "iwhyun"
    source_name = "越秀公共数字文化云"
    base_url = "https://www.iwhyun.com"
    verify_ssl = False  # 站点偶发证书问题
    # ⚠ 重要：壹点云会根据 Accept-Language 头返回不同模板。
    # 带任何 Accept-Language → 返回只有 HH:MM 的精简版（疑似适配国际访问）
    # 不带 Accept-Language → 返回完整 yyyy-mm-dd HH:MM
    # 因此 value=None 显式删除该 header。
    extra_headers = {"Accept-Language": None}

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        for hub in HUBS:
            try:
                html = self.http.text(self.base_url + hub)
            except Exception as e:
                self.logger.warning("hub %s failed: %s", hub, e)
                continue
            soup = BeautifulSoup(html, "lxml")
            cards = soup.select("li:has(.kuang), li:has(a.all_tri4s)")
            for card in cards:
                ev = self._parse_card(card, hub)
                if ev and ev.url not in seen:
                    seen.add(ev.url)
                    yield ev

    def _parse_card(self, card, hub: str) -> Event | None:
        a = card.select_one("a[href*='content0.jsp'], a[href*='detail'], a[href*='content.jsp']")
        if not a:
            return None
        href = self.absolute(a.get("href"))
        h3 = card.select_one("h3")
        title = clean(h3.get_text(" ", strip=True)) if h3 else ""
        if not title:
            return None

        img = card.select_one("img.lazy, img")
        poster = ""
        if img:
            poster = img.get("data-original") or img.get("src") or ""
            if poster and "error-img" in poster:
                poster = img.get("data-original") or ""
            poster = self.absolute(poster)

        # 收集所有 p 段，按字段名分桶；优先级：活动时间 > 活动日期 > 报名截止
        addr = ""
        bucket = {}  # key -> value
        for p in card.select("p"):
            txt = clean(p.get_text(" ", strip=True))
            m = re.match(r"^(活动时间|活动日期|报名截止时间|时间|日期|活动地点|地点)\s*[：:]\s*(.*)$", txt)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            bucket[key] = val
            if key in ("活动地点", "地点") and val and val != "暂无":
                addr = val

        raw_time = (bucket.get("活动时间") or bucket.get("活动日期")
                    or bucket.get("时间") or bucket.get("日期")
                    or bucket.get("报名截止时间") or "")
        start, end = parse_time_range(raw_time)
        cat = "讲座" if "讲座" in title or "讲堂" in title else (
              "展览" if "展" in title and "展览" in hub else
              "公益课" if "培训" in title or "课" in title else
              "演出" if any(k in title for k in ["音乐会","音乐季","演出","歌剧","音乐节","萨克斯","舞剧"]) else
              "活动")

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=cat,
            title=title,
            url=href,
            city="广州",
            district="越秀",
            venue="",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0, price_max=0, is_free=True,
            poster=poster,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

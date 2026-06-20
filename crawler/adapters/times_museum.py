"""广东时代美术馆 timesmuseum.org

整站是 Vue SPA。需要 Playwright 渲染。
入口：/cn/program  (项目/展览/讲座列表)
详情：/cn/program/<slug>

每个项目对象有：标题 / 时间范围 / 类型(展览/讲座/公教) / 门票 / 策展人 / 艺术家
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event, fetch_with_browser, _check_playwright
from ..utils import clean, parse_time_range, parse_price


class TimesMuseum(BaseAdapter):
    source = "times_museum"
    source_name = "广东时代美术馆"
    base_url = "https://www.timesmuseum.org"
    needs_browser = True

    def fetch(self) -> Iterator[Event]:
        if not _check_playwright():
            self.logger.warning(
                "TimesMuseum 需要 Playwright。请 `pip install playwright` "
                "并 `python -m playwright install chromium`")
            return

        # 1. 拿首页找所有 /cn/program/<slug> 详情链接
        try:
            html = fetch_with_browser(self.base_url + "/cn/")
        except Exception as e:
            self.logger.warning("home: %s", e)
            return

        slugs = list(set(re.findall(r'/cn/program/([\w\-]+)', html)))
        self.logger.info("times_museum: %d programs found", len(slugs))

        for slug in slugs[:20]:
            try:
                ev = self._parse_detail(slug)
                if ev:
                    yield ev
            except Exception as e:
                self.logger.warning("detail %s: %s", slug, e)

    def _parse_detail(self, slug: str) -> Event | None:
        url = f"{self.base_url}/cn/program/{slug}"
        html = fetch_with_browser(url, wait=1200)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")

        # 标题
        h1 = soup.select_one("h1") or soup.select_one("title")
        title = clean(h1.get_text(" ", strip=True)) if h1 else ""
        title = re.sub(r"\s*\|\s*时代美术馆.*$", "", title)
        # 去掉"项目进行中"等前缀
        title = re.sub(r"^(?:项目|展览|讲座|进行中|预告)+", "", title).strip()
        if not title:
            return None

        text = clean(soup.get_text("\n", strip=True))

        # 时间：常见 "2026-03-28 → 2026-07-26"
        raw_time = ""
        m = re.search(r"(\d{4}-\d{1,2}-\d{1,2}\s*[→\-~至到]\s*\d{4}-\d{1,2}-\d{1,2})",
                      text)
        if m:
            raw_time = m.group(1).replace("→", "-")
        start, end = parse_time_range(raw_time)
        # 开放时间补充
        m = re.search(r"开放时间\s*([^\n。]{4,80})", text)
        open_time = m.group(1).strip() if m else ""

        # 门票（只取首段数字或"免费"）
        price = ""
        m = re.search(r"门票\s*[：:]?\s*(?:¥|￥)?\s*(\d+(?:\.\d+)?\s*元?|免费|免门票|免票)",
                      text)
        if m:
            price = clean(m.group(1))
            # 数字+空 → 加"元"
            if re.fullmatch(r"\d+(?:\.\d+)?", price):
                price = price + "元"
        pmin, pmax, is_free = parse_price(price)

        # 类型: 展览/讲座/公教
        cat_inline = ""
        for k in ("展览", "讲座", "公教", "工作坊", "放映", "驻地"):
            if re.search(rf"\b{k}\b", text[:500]):
                cat_inline = k
                break

        # 策展人
        org = ""
        m = re.search(r"策展人\s*([^\n。]{2,40})", text)
        if m:
            org = clean(m.group(1))

        # 海报
        poster = ""
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src and len(src) > 30 and not src.startswith("data:"):
                if "logo" in src.lower() or "icon" in src.lower():
                    continue
                poster = src if src.startswith("http") else self.base_url + src
                break

        cat_final = ("展览" if cat_inline == "展览" else
                     "讲座沙龙" if cat_inline in ("讲座", "公教", "工作坊") else
                     "展览")  # 默认归展览

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=cat_final,
            title=title,
            url=url,
            city="广州",
            district="白云",
            venue="广东时代美术馆",
            address="广州市白云区黄边北路时代玫瑰园三期",
            start_time=start,
            end_time=end,
            raw_time=raw_time or open_time,
            price=price,
            price_min=pmin, price_max=pmax, is_free=is_free,
            poster=poster,
            organizer=org,
            description=text[:500],
            extra={"open_time": open_time, "type": cat_inline},
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

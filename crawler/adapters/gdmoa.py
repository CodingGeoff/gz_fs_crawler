"""广东美术馆 www.gdmoa.org — 展览 / 公共教育（讲座/活动/工作坊）。

入口列表：
  /Exhibition/                  正在展览汇总
  /Exhibition/Current/          当前展览
  /Exhibition/Exhibitions/      历史展览
  /Public_Education/            公共教育（活动主页）
  /Public_Education/Lecture/    讲座
  /Public_Education/Theme_Activity/  主题活动

详情页 selector （已实测稳定）：
  h1.detail-title       标题
  div.detail-time       "2026-05-30——2026-09-06" 时间
  div.detail-address    "广东美术馆新馆... 9、11、12、13号厅" 地点
  img (.article 内第一张)  海报
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


class GDMoA(BaseAdapter):
    source = "gdmoa"
    source_name = "广东美术馆"
    base_url = "https://www.gdmoa.org"
    parallel_workers = 5

    LIST_PATHS = [
        ("/Exhibition/", "展览"),
        ("/Public_Education/Lecture/", "讲座"),
        ("/Public_Education/Theme_Activity/", "活动"),
    ]
    # 支持绝对路径 / 相对路径
    DETAIL_RE = re.compile(r'href=["\'](\.?/?[\w\-./]*?t\d+_\d+\.shtml)["\']')

    def fetch(self) -> Iterator[Event]:
        queue: list[tuple[str, str]] = []
        seen: set[str] = set()
        for path, cat in self.LIST_PATHS:
            url = self.base_url + path
            try:
                html = self.http.text(url)
            except Exception as e:
                self.logger.warning("list %s: %s", url, e)
                continue
            cands = []
            for m in self.DETAIL_RE.finditer(html):
                href = m.group(1)
                # 相对路径 ./Current/xxx 需要基于 list URL 解析
                full = self.absolute(href, base=url)
                if full not in seen:
                    seen.add(full)
                    cands.append(full)
                if len(cands) >= 30: break
            self.logger.info("gdmoa %s -> %d items", path, len(cands))
            for u in cands:
                queue.append((u, cat))

        if not queue: return

        def _one(args):
            u, cat = args
            try: return self._parse_detail(u, cat)
            except Exception as e:
                self.logger.warning("detail %s: %s", u, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, queue):
                if ev: yield ev

    # ------------------------------------------------------------------
    def _parse_detail(self, url: str, category: str) -> Event | None:
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")

        # 标题
        title_node = soup.select_one("h1.detail-title") or \
                     soup.select_one("h1") or soup.select_one("title")
        if not title_node:
            return None
        title = clean(title_node.get_text(" ", strip=True))
        title = re.sub(r"\s*-\s*广东美术馆.*$", "", title)
        if not title or len(title) < 3:
            return None

        # 时间
        raw_time = ""
        t_node = soup.select_one(".detail-time") or \
                 soup.select_one(".time") or soup.select_one(".det-time")
        if t_node:
            raw_time = clean(t_node.get_text(" ", strip=True)) \
                       .replace("——", " - ").replace("—", "-")
        # 解析
        start, end = parse_time_range(raw_time) if raw_time else ("", "")
        # 兜底：从正文找
        if not start:
            body_text = clean(soup.get_text("\n", strip=True))[:3000]
            raw2, s2, e2 = find_time_in_text(body_text)
            if s2:
                start, end = s2, e2
                if not raw_time:
                    raw_time = raw2

        # 地点
        addr = ""
        a_node = soup.select_one(".detail-address") or \
                 soup.select_one(".address")
        if a_node:
            addr = clean(a_node.get_text(" ", strip=True))
        if not addr:
            m = re.search(r"地\s*点[：:]\s*([^\n。]{4,80})",
                          soup.get_text("\n", strip=True))
            if m: addr = clean(m.group(1))
        addr = addr or "广东美术馆"

        # 海报
        poster = ""
        # 详情页正文区域第一张大图
        for img in soup.select(".article img, .article_content img, "
                                "#zoom img, .news_box img, .main img"):
            src = img.get("src") or img.get("data-src") or ""
            if not src or src.startswith("data:") or "logo" in src.lower():
                continue
            poster = self.absolute(src, base=url)
            break
        if not poster:
            # 兜底全文找
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if not src or src.startswith("data:"): continue
                if any(k in src.lower() for k in ("logo", "icon", "/img/", "/css/")):
                    continue
                poster = self.absolute(src, base=url)
                break

        # 描述
        desc_node = soup.select_one(".article, .article_content, .news_box, .main")
        description = clean(desc_node.get_text(" ", strip=True))[:500] \
                      if desc_node else ""

        # 分类细化
        cat_final = category
        if "讲座" in title or "讲座" in url:
            cat_final = "讲座"
        elif "展" in title and category == "展览":
            cat_final = "展览"

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=cat_final,
            title=title,
            url=url,
            city="广州",
            district="荔湾",
            venue="广东美术馆",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0.0, price_max=0.0, is_free=True,
            poster=poster,
            description=description,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

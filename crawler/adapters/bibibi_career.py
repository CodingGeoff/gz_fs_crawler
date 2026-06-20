"""广东 bibibi.net 通用招聘模板（广州软件学院 / 暨南大学等多校）。

URL 模式：
  list: <base>/   (首页就是 list)
  detail: /detail/jobfair?id=<id>
          /detail/news?id=<id>
          /detail/preach?id=<id>
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


class _BibibiBase(BaseAdapter):
    parallel_workers = 4

    # 子类设置
    DETAIL_PATTERNS = [
        (r"/detail/jobfair\?id=(\d+)", "招聘会"),
        (r"/detail/preach\?id=(\d+)", "宣讲会"),
        (r"/detail/teachin\?id=(\d+)", "宣讲会"),
    ]

    def fetch(self) -> Iterator[Event]:
        try:
            html = self.http.text(self.base_url + "/")
        except Exception as e:
            self.logger.warning("home fail: %s", e)
            return

        queue: list[tuple[str, str]] = []
        seen: set[str] = set()
        for pat, kind in self.DETAIL_PATTERNS:
            ids = list(dict.fromkeys(re.findall(pat, html)))[:20]
            self.logger.info("%s %s -> %d", self.source_name, kind, len(ids))
            for i in ids:
                u = f"{self.base_url}/detail/{kind_path(kind)}?id={i}"
                if u in seen:
                    continue
                seen.add(u)
                queue.append((u, kind))

        if not queue:
            return

        def _one(args):
            u, k = args
            try:
                return self._parse_detail(u, k)
            except Exception as e:
                self.logger.warning("detail %s: %s", u, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, queue):
                if ev:
                    yield ev

    def _parse_detail(self, url: str, kind: str) -> Event | None:
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")

        # title - 在 <h1> 或正文 <h2 class="title"> 
        title = ""
        for sel in ["h1.title", ".detail-title", ".title h1", "h1", ".bt"]:
            n = soup.select_one(sel)
            if n:
                t = clean(n.get_text(" ", strip=True))
                if t and len(t) > 4 and "详情" not in t:
                    title = t
                    break
        if not title:
            # 从 meta og:title
            og = soup.select_one("meta[property='og:title']")
            if og:
                title = clean(og.get("content", "")).split(" - ")[0]
        # 兜底从全文找招聘标题
        if not title or "详情" in title:
            body_text = clean(soup.get_text(" ", strip=True))
            # 看是否含"邀请函"/"专场"/"招聘会"等
            m = re.search(r"[^\s]{4,60}(?:招聘会|宣讲会|双选会|邀请函|专场)", body_text[:2000])
            if m:
                title = clean(m.group(0))[:80]
        if not title:
            return None

        body_text = clean(soup.get_text(" ", strip=True))

        # 时间
        raw_time = ""
        for k in ("举办时间", "活动时间", "时间", "宣讲时间"):
            m = re.search(rf"{k}\s*[:：]\s*([^\n。举主组]{{4,80}})", body_text)
            if m:
                raw_time = clean(m.group(1))
                break
        start, end = parse_time_range(raw_time) if raw_time else ("", "")
        if not start:
            _, start, end = find_time_in_text(body_text[:2000])

        # 地点
        addr = ""
        for k in ("举办地址", "举办地点", "宣讲地点", "地点"):
            m = re.search(rf"{k}\s*[:：]\s*([^\n。举主组承]{{4,120}})", body_text)
            if m:
                v = clean(m.group(1))
                # 截掉同段后续"主办单位"等
                v = re.split(r"\s*(?:二、|三、|主办|承办|组织|招聘单位|联系)", v)[0]
                addr = v.strip()
                break

        # 主办
        org = ""
        m = re.search(r"主办单位\s*[:：]\s*([^\n。承]{2,60})", body_text)
        if m:
            org = clean(m.group(1))

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=kind,
            title=title,
            url=url,
            city=self.city_default,
            venue=self.source_name.replace("就业网", "").replace("·", ""),
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0, price_max=0, is_free=True,
            organizer=org,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )


def kind_path(kind: str) -> str:
    return {"招聘会": "jobfair", "宣讲会": "preach"}.get(kind, "jobfair")


class SEIGCareer(_BibibiBase):
    source = "seig_career"
    source_name = "广州软件学院就业网"
    base_url = "https://job.seig.edu.cn"
    city_default = "广州"


class JNUCareer(_BibibiBase):
    source = "jnu_career"
    source_name = "暨南大学就业网"
    base_url = "https://career.jnu.edu.cn"
    city_default = "广州"

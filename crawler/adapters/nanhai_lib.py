"""南海图书馆 www.nhlib.cn

站点结构：
  导航入口：
    /about/newlist/10707.html       —— 活动预告（最新通知）
    /activities/lists/10697.html    —— 活动报道（已办）
    /activities/index.html          —— 活动中心首页
    /exhibitions/index.html         —— 展览
  详情页：
    /about/View/<id>.html
    /activities/View/<id>.html
  详情页结构：
    div.tit       -> 标题 + 发布时间
    div.con       -> 正文（含 "活动时间：" "活动地点：" 等字段）
    div.con img   -> 海报，路径形如 /public/UserFiles/image/...
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


HUBS = [
    "/about/newlist/10707.html",
    "/activities/lists/10697.html",
    "/activities/index.html",
    "/exhibitions/index.html",
]


class NanhaiLib(BaseAdapter):
    source = "nanhai_lib"
    source_name = "南海图书馆"
    base_url = "http://www.nhlib.cn"
    verify_ssl = False

    parallel_workers = 6

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        queue: list[str] = []
        for hub in HUBS:
            url = self.base_url + hub
            try:
                html = self.http.text(url)
            except Exception as e:
                self.logger.info("nhlib hub %s: %s", hub, e)
                continue
            soup = BeautifulSoup(html, "lxml")
            hrefs = list({
                self.absolute(a["href"])
                for a in soup.select("a[href]")
                if re.search(r"/(?:about|activities|exhibitions)/View/\d+\.html",
                             a.get("href", ""))
            })[:25]
            self.logger.info("nhlib %s -> %d events", hub, len(hrefs))
            for href in hrefs:
                if href in seen: continue
                seen.add(href)
                queue.append(href)

        if not queue: return

        def _one(href):
            try:
                return self._parse_detail(href)
            except Exception as e:
                self.logger.warning("nhlib detail %s: %s", href, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, queue):
                if ev:
                    yield ev

    def _parse_detail(self, url: str) -> Event | None:
        html = self.http.text(url)
        soup = BeautifulSoup(html, "lxml")

        # ---- 标题 ----
        title = ""
        tit_node = soup.select_one(".tit")
        if tit_node:
            # tit 节点同时含发布时间 "时间：YYYY-MM-DD"，要剥掉
            raw_tit = tit_node.get_text(" ", strip=True)
            title = re.split(r"时间[:：]\s*\d", raw_tit)[0].strip()
        if not title:
            t = soup.select_one("title")
            title = clean(t.get_text()) if t else ""
            title = re.sub(r"\s*-\s*南海图书馆.*$", "", title)
        if not title:
            return None

        # ---- 正文 ----
        con = soup.select_one(".con") or soup.select_one(".activity_details")
        body_text = clean(con.get_text("\n", strip=True)) if con else ""
        # 重新以换行替代，确保 find_time_in_text 截止符生效
        body_lines = []
        if con:
            for el in con.find_all(["p", "div", "section", "li", "br"]):
                t = el.get_text(" ", strip=True)
                if t:
                    body_lines.append(t)
            body_lines.append(con.get_text("\n", strip=True))
        body_text_for_parse = "\n".join(body_lines) or body_text

        # ---- 海报 ----
        poster = ""
        if con:
            for img in con.select("img"):
                src = img.get("src") or img.get("data-src") or ""
                if not src or "logo" in src.lower():
                    continue
                if src.startswith("//"):
                    src = "http:" + src
                poster = self.absolute(src)
                break

        # ---- 时间 ----
        raw_time, start, end = find_time_in_text(body_text_for_parse)
        # 兜底用 .tit 里发布时间（不太准但有总比没有强）
        if not start:
            m = re.search(r"时间[:：]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})",
                          (tit_node.get_text(" ") if tit_node else ""))
            if m:
                raw_time = m.group(1)
                start, end = parse_time_range(raw_time)

        # ---- 地点 ----
        addr = ""
        # 截止符：换行 / 标点 / 下一个字段关键字
        STOP = (r"活动对象|活动时间|活动详情|活动主题|招募对象|活动费用|"
                r"活动名称|报名方式|报名时间|主办|协办|场次|预约方式|"
                r"活动须知|结果通知|活动咨询|联系")
        m = re.search(
            rf"(?:活动地点|活动地址|地点|地址|场地)\s*[:：]\s*"
            rf"(.+?)(?=\s*(?:{STOP})\s*[:：]|[\n\r。；;]|$)",
            body_text_for_parse)
        if m:
            addr = clean(m.group(1))[:120]
        addr = addr or "佛山市南海区南海图书馆"

        # ---- 分类 ----
        cat = "讲座" if "讲座" in title else (
              "展览" if "展" in title or "/exhibitions/" in url else
              "活动")

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=cat,
            title=title[:120],
            url=url,
            city="佛山",
            district="南海",
            venue="南海图书馆",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0, price_max=0, is_free=True,
            poster=poster,
            description=body_text[:500],
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

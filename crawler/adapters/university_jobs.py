"""高校就业网 - 校园双选会 / 招聘宣讲会聚合。

广州主要 985/211 + 普通高校都使用「云职校招 yunzhixz / 凯创御聘」类似模板，
URL 模式：
  - 中山大学:  https://career.sysu.edu.cn/jobfair                (列表)
              https://career.sysu.edu.cn/jobfair/view/id/<id>    (详情)
              https://career.sysu.edu.cn/preach                  (宣讲会列表)
              https://career.sysu.edu.cn/preach/view/id/<id>
  - 广州大学:  https://jy.gzhu.edu.cn/web/Index/jobfair-list
              https://jy.gzhu.edu.cn/web/Index/jobfair-detail?id=<id>
              https://jy.gzhu.edu.cn/web/Index/preach-list / preach-detail?id=
  - 广东工业大学: https://career.gdut.edu.cn/jobfair  (与中大同模板)

详情页结构（中大/广工同款，叫 "云职校招" 模板）：
  <title>2026届毕业生就业暨...招聘会（广州校区）</title>
  正文里有 "举办时间：2026-06-05 13:30-16:00（周五）"
              "举办地址：中山大学广州校区南校园熊德龙活动中心一楼报告厅"

广州大学是另一套（"广州职迅" 模板），用页面中的 .detail-info / 列表 td 解析。
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range, find_time_in_text


# ---------------------------------------------------------------------------
# 模板一：云职校招 (中山大学、广工)
# ---------------------------------------------------------------------------
class _YunZhiBase(BaseAdapter):
    """jobfair/view/id/{id} 和 teachin(or preach)/view/id/{id} 两个频道。

    子类可通过 `list_paths` 覆盖路径，第二项 (kind) 是中文分类标签。
    某些站列表页是 JS 渲染，需要回退到首页里抓最近的 ids。
    """
    list_paths = [("jobfair", "招聘会"), ("teachin", "宣讲会")]
    fallback_home_for_ids = True   # 列表页找不到时去首页兜底
    parallel_workers = 6

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        queue: list[tuple[str, str]] = []
        for path, kind in self.list_paths:
            list_url = f"{self.base_url}/{path}"
            ids: list[str] = []
            try:
                html = self.http.text(list_url)
                ids = list(dict.fromkeys(
                    re.findall(rf"/{path}/view/id/(\d+)", html)
                ))[:30]
            except Exception as e:
                self.logger.warning("list %s failed: %s", list_url, e)
            if not ids and self.fallback_home_for_ids:
                try:
                    home = self.http.text(self.base_url + "/")
                    ids = list(dict.fromkeys(
                        re.findall(rf"/{path}/view/id/(\d+)", home)
                    ))[:15]
                    if ids:
                        self.logger.info(
                            "%s %s list empty, fallback to home -> %d ids",
                            self.source_name, kind, len(ids))
                except Exception as e:
                    self.logger.warning("home fallback fail: %s", e)
            self.logger.info("%s %s -> %d items", self.source_name, kind, len(ids))
            for i in ids:
                u = f"{self.base_url}/{path}/view/id/{i}"
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
        t = soup.select_one("title")
        title = clean(t.get_text()) if t else ""
        title = re.sub(r"\s*-\s*[\u4e00-\u9fff]+就业(?:信息网|指导中心|网).*$", "", title)
        if not title:
            return None

        body = clean(soup.get_text(" ", strip=True))[:5000]

        # 时间 & 地址（模板里出现的关键字会因 招聘会/宣讲会 不同而变）
        raw_time = ""
        for k in ("举办时间", "宣讲时间", "宣讲会时间", "时间"):
            m = re.search(rf"{k}[：:]\s*([^\n举宣单组主时日]{{4,80}})", body)
            if m:
                raw_time = clean(m.group(1))
                break
        # 部分宣讲会模板把日期单独放在「日期：」
        date_str = ""
        m = re.search(r"日期[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", body)
        if m:
            date_str = m.group(1)
        if raw_time and date_str and re.match(r"^\d{1,2}:\d{2}", raw_time):
            raw_time = f"{date_str} {raw_time}"

        addr = ""
        for k in ("举办地址", "举办地点", "宣讲地点", "宣讲地址", "地点", "地址"):
            m = re.search(rf"{k}[：:]\s*([^\n举宣单组主时日]{{4,120}})", body)
            if m:
                addr = clean(m.group(1))
                break

        start, end = parse_time_range(raw_time)
        if not start:
            _, start, end = find_time_in_text(body[:2000])

        # 主办方
        org = ""
        m = re.search(r"(?:主办单位|主办方)[：:]\s*([^\n承]{2,60})", body)
        if m:
            org = clean(m.group(1))

        # 海报
        poster = ""
        for img in soup.select("img"):
            src = img.get("src") or ""
            if not src or "logo" in src.lower() or "icon" in src.lower():
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = self.base_url + src
            if "/attachment/" in src or "/upload" in src:
                poster = src
                break

        return Event(
            source=self.source,
            source_name=self.source_name,
            category="招聘会" if kind == "招聘会" else "宣讲会",
            title=title,
            url=url,
            city="广州",
            venue=self.source_name.replace("就业网", "").replace("·", ""),
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0, price_max=0, is_free=True,
            poster=poster,
            organizer=org,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )


class SYSUCareer(_YunZhiBase):
    source = "sysu_career"
    source_name = "中山大学就业网"
    base_url = "https://career.sysu.edu.cn"


class GDUTCareer(_YunZhiBase):
    source = "gdut_career"
    source_name = "广东工业大学就业网"
    base_url = "https://career.gdut.edu.cn"


# ---------------------------------------------------------------------------
# 模板二：广州职迅 (广州大学)
# ---------------------------------------------------------------------------
class GZHUCareer(BaseAdapter):
    source = "gzhu_career"
    source_name = "广州大学就业网"
    base_url = "https://jy.gzhu.edu.cn"

    LIST_PATHS = [
        ("jobfair", "招聘会"),
        ("preach", "宣讲会"),
    ]
    parallel_workers = 3  # 广大就业网 IIS 慢，并发高反而 timeout

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 强制更大 timeout
        self.http.client.timeout = 25.0

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        queue: list[tuple[str, str]] = []
        for path, kind in self.LIST_PATHS:
            list_url = f"{self.base_url}/web/Index/{path}-list"
            try:
                html = self.http.text(list_url)
            except Exception as e:
                self.logger.warning("list %s: %s", list_url, e)
                continue
            ids = list(dict.fromkeys(
                re.findall(rf"{path}-detail\?id=(\w+)", html)
            ))[:25]
            self.logger.info("%s %s -> %d items", self.source_name, kind, len(ids))
            for i in ids:
                u = f"{self.base_url}/web/Index/{path}-detail?id={i}"
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
        t = soup.select_one("title")
        title = clean(t.get_text()) if t else ""
        title = re.sub(r"\s*-\s*广州大学就业网\s*$", "", title)
        if not title or "找不到页面" in title:
            return None

        body = clean(soup.get_text(" ", strip=True))[:5000]

        raw_time = ""
        for k in ("举办时间", "宣讲时间", "时间"):
            m = re.search(rf"{k}[：:]\s*([^\n举宣单组]{{4,80}})", body)
            if m:
                raw_time = clean(m.group(1))
                break
        addr = ""
        for k in ("举办地点", "宣讲地点", "地点"):
            m = re.search(rf"{k}[：:]\s*([^\n举宣单组]{{4,120}})", body)
            if m:
                addr = clean(m.group(1))
                break

        start, end = parse_time_range(raw_time)
        if not start:
            _, start, end = find_time_in_text(body[:2000])

        org = ""
        m = re.search(r"(?:主办|举办单位|招聘单位)[：:]\s*([^\n承组]{2,60})", body)
        if m:
            org = clean(m.group(1))

        return Event(
            source=self.source,
            source_name=self.source_name,
            category="招聘会" if kind == "招聘会" else "宣讲会",
            title=title,
            url=url,
            city="广州",
            venue="广州大学",
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price="免费",
            price_min=0, price_max=0, is_free=True,
            organizer=org,
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

"""秀动 ShowStart - 全国 livehouse / 演出聚合 (广州 / 佛山)。

发现：列表页虽然是 Vue/Nuxt SSR，但首屏的 `window.__NUXT__` 已经包含全部
活动数据。我们直接用 Node.js 把混淆过的 IIFE eval 出 JSON 即可。

cityCode 映射（从 cityOption 表内读取）：
   广州: 20    佛山: 757    深圳: 21    东莞: 23

每页 20 条，可分页 ?pageNo=N。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Iterator

from ..base import BaseAdapter, Event
from ..utils import parse_time_range, parse_price, clean


_NODE = shutil.which("node")
_NUXT_RE = re.compile(r"window\.__NUXT__\s*=\s*(.+?);\s*</script>", re.S)


def _eval_nuxt(html: str) -> dict | None:
    """用 node 把 __NUXT__ IIFE eval 成 JSON。"""
    if not _NODE:
        return None
    m = _NUXT_RE.search(html)
    if not m:
        return None
    js = f"const o = {m.group(1)}; process.stdout.write(JSON.stringify(o));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        r = subprocess.run([_NODE, path], capture_output=True,
                           text=True, timeout=15)
        if r.returncode == 0 and r.stdout:
            return json.loads(r.stdout)
    except Exception:
        return None
    return None


class ShowStart(BaseAdapter):
    source = "showstart"
    source_name = "秀动 ShowStart"
    base_url = "https://www.showstart.com"
    CITIES = [("广州", 20), ("佛山", 757)]

    def fetch(self) -> Iterator[Event]:
        if not _NODE:
            self.logger.warning(
                "ShowStart adapter 需要 Node.js 来 eval __NUXT__；"
                "请 `apt install nodejs` 或 `brew install node` 后重试。")
            return

        seen: set[int] = set()
        for city_name, city_code in self.CITIES:
            for page in range(1, self.max_pages + 1):
                url = (f"{self.base_url}/event/list?cityCode={city_code}"
                       f"&pageNo={page}")
                try:
                    html = self.http.text(url)
                except Exception as e:
                    self.logger.warning("page %d: %s", page, e)
                    break
                nuxt = _eval_nuxt(html)
                if not nuxt:
                    self.logger.warning("city=%s page=%d 无法 eval __NUXT__",
                                        city_name, page)
                    break
                try:
                    block = nuxt["data"][0]
                except (KeyError, IndexError):
                    break
                items = block.get("listData") or []
                self.logger.info("ShowStart city=%s p=%d -> %d items (total=%s)",
                                 city_name, page, len(items),
                                 block.get("totalCount", "?"))
                for it in items:
                    eid = it.get("id")
                    if not eid or eid in seen:
                        continue
                    seen.add(eid)
                    yield self._make_event(it, city_name)
                if len(items) < 20:
                    break

    def _make_event(self, it: dict, city_default: str) -> Event:
        show_time = it.get("showTime", "")  # e.g. "2026/03/06 20:00"
        start, end = parse_time_range(show_time)
        price_raw = it.get("price", "")     # "¥49起"
        pmin, pmax, is_free = parse_price(price_raw)
        title = clean(it.get("title", ""))
        url = f"{self.base_url}/event/{it['id']}"
        return Event(
            source=self.source,
            source_name=self.source_name,
            category="演出",
            title=title,
            url=url,
            city=clean(it.get("cityName", "")) or city_default,
            venue=clean(it.get("siteName", "")),
            address=clean(it.get("siteName", "")),
            start_time=start,
            end_time=end,
            raw_time=show_time,
            price=price_raw,
            price_min=pmin,
            price_max=pmax,
            is_free=is_free,
            poster=it.get("poster", ""),
            organizer=clean(it.get("performers", "")),
            extra={
                "sold_out": bool(it.get("soldOut")),
                "is_exclusive": it.get("isExclusive"),
            },
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

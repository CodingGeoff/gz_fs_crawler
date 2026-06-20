"""应届生求职网 - 广州校园宣讲会聚合 (跨多个广州高校)。

入口:
   https://my.yingjiesheng.com/xuanjianghui_city_17.html   (广州=17)

页面是 GB2312 编码 (httpx 默认会按响应头解析，但要兜底)。
表格结构：
   城市 | 举办日期 | 具体时间 | 公司 | 学校 | 具体地点 | 查看
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import clean, parse_time_range


class YingjieshengGZ(BaseAdapter):
    source = "yingjiesheng_gz"
    source_name = "应届生·广州宣讲会"
    base_url = "https://my.yingjiesheng.com"

    def fetch(self) -> Iterator[Event]:
        # 广州 city_id = 17，可能多页
        for page in range(1, max(2, self.max_pages + 1)):
            url = (f"{self.base_url}/xuanjianghui_city_17.html"
                   if page == 1 else
                   f"{self.base_url}/xuanjianghui_city_17_{page}.html")
            try:
                # 用独立 httpx 调用，绕过 client 池（应届生站点偶发拒绝长连接）
                import httpx as _httpx
                self.http._sleep()
                r = _httpx.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,*/*",
                }, timeout=12, follow_redirects=True)
                r.encoding = "gb2312"
                html = r.text
            except Exception as e:
                self.logger.warning("page %d: %s", page, e)
                break
            if "宣讲会" not in html:
                break
            soup = BeautifulSoup(html, "lxml")
            rows = soup.select("table tr")
            cnt = 0
            for tr in rows:
                tds = tr.select("td")
                if len(tds) < 6:
                    continue
                city = clean(tds[0].get_text())
                if city != "广州":
                    continue
                # 列：[城市,举办日期,具体时间,公司,学校,具体地点,查看]
                # 实测公司/具体时间需登录才显示；空时用日期+学校组合
                date_txt = clean(tds[1].get_text())
                # 日期格式 "2026-06-09 (周二)"
                date_only = date_txt.split(" ")[0] if date_txt else ""
                time_txt = clean(tds[2].get_text())
                company = clean(tds[3].get_text())
                school = clean(tds[4].get_text())
                place = clean(tds[5].get_text())
                # 详情链接
                a = tds[-1].select_one("a[href]")
                href = a.get("href", "") if a else ""
                if href and not href.startswith("http"):
                    href = "https://my.yingjiesheng.com" + (
                        href if href.startswith("/") else "/" + href)
                raw_time = f"{date_only} {time_txt}".strip()
                start, end = parse_time_range(date_only)

                # 标题：有公司就用公司，否则 "学校 校园宣讲会 (日期)"
                title = (f"{company} 校园宣讲会 @ {school}" if company
                         else f"{school} 校园宣讲会 ({date_only})")

                yield Event(
                    source=self.source,
                    source_name=self.source_name,
                    category="宣讲会",
                    title=title,
                    url=href or url,
                    city="广州",
                    venue=school,
                    address=place,
                    start_time=start,
                    end_time=end,
                    raw_time=raw_time,
                    price="免费",
                    price_min=0, price_max=0, is_free=True,
                    organizer=company,
                    description=f"在 {school} 举办的校园宣讲会，地点：{place}",
                    extra={"company": company, "school": school,
                           "note": "公司名需登录后才显示"},
                    crawled_at=datetime.now().isoformat(timespec="seconds"),
                )
                cnt += 1
            self.logger.info("yingjiesheng page %d: %d events", page, cnt)
            if cnt == 0:
                break

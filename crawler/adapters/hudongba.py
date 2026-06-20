"""互动吧 - 广州 / 佛山。

入口分类页：
  https://www.hudongba.com/guangzhou/   (默认综合)
  https://www.hudongba.com/foshan/

详情页域名是动态子域：
  https://h5-party-<5位hash>.hudongba.com/party/<5位hash>.html

🔑 数据提取多源叠加（重要 — 单一来源不可靠）：

  (A) API: POST https://api.hudongba.com/ajax/api:51
      data: info_type=party, info_id=<hash>
      返回 JSON 含 title/posterImage/cityName/location/shopName/startDate
      —— 但 priceRange 不可信（线下付款活动 API 写"免费"，实际收费）

  (B) JSON-LD <script type="application/ld+json">
      含 title/images/pubDate（海报最权威来源）

  (C) inline JS 变量：
      locationTextFull / _publishUserName / _isPay
      （_isPay="1" 代表"收费"，是否收费的真值）

  (D) DOM 容器 #dt_content：
      真实正文 HTML，含 "四、收费标准 大小同价：118元/人" 等
      所有价格只能从这里解析

⚠ og:image 经常被错配为页面 URL 自身，**必须忽略**。
"""
from __future__ import annotations

import concurrent.futures as _cf
import json
import re
from datetime import datetime
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import (parse_time_range, parse_price, clean, extract_city,
                     find_time_in_text)


CITIES = [("广州", "guangzhou"), ("佛山", "foshan")]

API_DETAIL = "https://api.hudongba.com/ajax/api:51"
PARTY_HASH_RE = re.compile(
    r"https?://h5-party-([\w\-]+)\.hudongba\.com/party/[\w\-]+\.html")


def _extract_js_var(html: str, name: str) -> Optional[str]:
    """从 inline JS 提取 `varName : "value"` 或 `varName="value"`。"""
    m = re.search(rf'\b{name}\s*[:=]\s*"([^"]*)"', html)
    return m.group(1) if m else None


def _find_image_url(html: str) -> str:
    """从 HTML 全文找海报 URL（优先用户上传图，跳过 UI/logo/icon）。"""
    # 互动吧用户上传图域名 - 按可信度排序
    patterns = [
        # 用户上传海报（最权威，是图片本身）
        r'https?://img-user-ali\.hudongba\.com/jootun_common/[^"\'\s<>]+\.(?:jpg|jpeg|png|webp|gif)(?:@[^"\'\s<>]+)?',
        # app 子域上传图
        r'https?://img-app\.hudongba\.com/[^"\'\s<>]+\.(?:jpg|jpeg|png|webp|gif)(?:@[^"\'\s<>]+)?',
        # uc 子域 oss 上传图
        r'https?://img-uc\.hudongba\.cn/upload/[^"\'\s<>]+\.(?:jpg|jpeg|png|webp|gif)(?:@[^"\'\s<>]+)?',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html):
            u = m.group(0)
            # 跳过 logo / icon / 头像
            low = u.lower()
            if any(k in low for k in ("/logo", "/icon", "/avatar", "/static_v4",
                                       "shop-head", "share/", "/header",
                                       "user_default")):
                continue
            return u
    return ""


def _extract_price_from_content(text: str) -> str:
    """从正文里解析价格字段。

    支持模式：
      "大小同价：118元/人"
      "门票：50元 / 80元"
      "费用：99元起"
      "原价 198 元，现价 99 元"
      "成人 120 元，儿童 60 元"
      "￥50 - ￥380"
    返回原文片段（保真），用 parse_price 进一步抽数字。
    """
    if not text:
        return ""
    # 1. 关键字开头的整段
    for kw in ("收费标准", "票价", "费用", "价格", "门票", "活动费用",
               "活动票价", "活动价格", "活动收费", "活动费"):
        m = re.search(rf"{kw}[^。\n]*?\d+\s*[元¥￥][^。\n]*", text)
        if m:
            seg = clean(m.group(0))
            # 截短
            return seg[:120]
    # 2. "xxx：N 元/单位"
    m = re.search(r"[\u4e00-\u9fff]{0,12}[：:]\s*\d+\s*[元¥￥][^\n。]{0,40}", text)
    if m:
        return clean(m.group(0))[:120]
    # 3. 数字范围
    m = re.search(r"(?:¥|￥|RMB)\s*\d+(?:\s*[-~至到]\s*(?:¥|￥)?\s*\d+)?", text)
    if m:
        return clean(m.group(0))
    # 4. 单价
    m = re.search(r"\d+\s*元(?:起|/人|/位|/张|/桌)?", text)
    if m:
        return clean(m.group(0))
    return ""


class HuDongBa(BaseAdapter):
    source = "hudongba"
    source_name = "互动吧"
    base_url = "https://www.hudongba.com"

    parallel_workers = 6   # 详情含多次 API 调用，6 比较合适

    def fetch(self) -> Iterator[Event]:
        seen: set[str] = set()
        queue: list[tuple[str, str]] = []
        for city_zh, city_en in CITIES:
            for page in range(1, self.max_pages + 1):
                url = f"{self.base_url}/{city_en}/0-0-0-0-0-{page}/"
                try:
                    html = self.http.text(url)
                except Exception as e:
                    self.logger.warning("list %s p%d: %s", city_en, page, e)
                    continue
                links = list(dict.fromkeys(re.findall(
                    r'href="(https?://h5-party-[\w\-]+\.hudongba\.com/party/[\w\-]+\.html)"',
                    html)))[:20]
                self.logger.info("HDB city=%s page=%d events=%d",
                                 city_zh, page, len(links))
                for u in links:
                    if u in seen:
                        continue
                    seen.add(u)
                    queue.append((u, city_zh))

        self.logger.info("hudongba: parallel fetch %d details", len(queue))

        def _one(args):
            u, city = args
            try:
                return self._parse_detail(u, city)
            except Exception as e:
                self.logger.warning("hdb detail %s: %s", u, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, queue):
                if ev:
                    yield ev

    # ------------------------------------------------------------------
    # 详情解析（4 个数据源叠加）
    # ------------------------------------------------------------------
    def _parse_detail(self, url: str, city_default: str) -> Optional[Event]:
        html = self.http.text(url)

        # 检测"活动已下架"页 (5KB 左右)
        if "活动结束很久了" in html or len(html) < 8000:
            self.logger.info("[%s] 活动已下架/超短页, skip", url)
            return None

        soup = BeautifulSoup(html, "lxml")

        # (1) 提取 party hash
        m = PARTY_HASH_RE.search(url)
        party_hash = m.group(1) if m else ""

        # (2) 调用 API 拿权威字段
        api_data: dict = {}
        if party_hash:
            try:
                r = self.http.client.post(
                    API_DETAIL,
                    data={"info_type": "party", "info_id": party_hash},
                    headers={"Referer": url,
                             "X-Requested-With": "XMLHttpRequest"},
                    timeout=8,
                )
                j = r.json()
                if isinstance(j, dict) and j.get("state") == "0":
                    api_data = j.get("result", {}) or {}
            except Exception as e:
                self.logger.debug("api:51 fail %s: %s", party_hash, e)

        # (3) JSON-LD（含海报最权威）
        ld_data: dict = {}
        for s in soup.select("script[type='application/ld+json']"):
            try:
                j = json.loads(s.get_text() or "{}")
                if isinstance(j, dict):
                    ld_data = j
                    break
            except Exception:
                pass

        # (4) Inline JS vars
        js_location = _extract_js_var(html, "locationTextFull") or \
                      _extract_js_var(html, "_locationText")
        js_publisher = _extract_js_var(html, "_publishUserName")
        js_is_pay = _extract_js_var(html, "_isPay")  # "1"=收费 "0"=免费

        # (5) #dt_content 真实正文
        content_el = soup.select_one("#dt_content") or \
                     soup.select_one(".dt_content")
        content_text = clean(content_el.get_text("\n", strip=True)) \
                       if content_el else ""

        # ===================== 合并 =====================
        # --- title (API > meta > <title>) ---
        title = clean(api_data.get("title") or "")
        if not title:
            og_t = soup.select_one("meta[property='og:title']")
            if og_t:
                title = clean(og_t.get("content", ""))
        if not title:
            t = soup.select_one("title")
            title = clean(t.get_text()) if t else ""
        title = re.sub(r"-在线订票-互动吧\s*$", "", title).strip()
        if not title:
            return None

        # --- poster (JSON-LD images > API posterImage > DOM 扫描) ---
        poster = ""
        if ld_data.get("images"):
            v = ld_data["images"][0] if isinstance(ld_data["images"], list) \
                else ld_data["images"]
            if isinstance(v, str) and v.startswith("http"):
                poster = v
        if not poster and api_data.get("posterImageApp"):
            poster = api_data["posterImageApp"]
        if not poster and api_data.get("posterImage"):
            v = api_data["posterImage"]
            poster = v if v.startswith("http") else \
                     "https://img-user-ali.hudongba.com" + v
        if not poster:
            poster = _find_image_url(html)

        # --- 时间 (API.startDate > 正文 find_time_in_text > deadline) ---
        raw_time = ""
        start = end = ""
        # API
        api_start = api_data.get("startDate")  # "2026-06-06 09:00"
        api_date = api_data.get("date")        # "06-06 09:00 开始"
        if api_start:
            raw_time = api_start
            start, end = parse_time_range(api_start)
        if not start and content_text:
            raw_time2, s2, e2 = find_time_in_text(content_text)
            if s2:
                start, end = s2, e2
                if not raw_time:
                    raw_time = raw_time2
        if not start and api_date:
            # "06-06 09:00 开始" -> 帮它补完整日期
            raw_time = api_date
            start, end = parse_time_range(api_date)
        # description 兜底
        if not start:
            meta_desc = soup.select_one("meta[name='description']")
            desc_text = meta_desc.get("content", "") if meta_desc else ""
            m = re.search(r"报名截止(\d{1,2}-\d{1,2}\s*\d{1,2}:\d{2})", desc_text)
            if m:
                raw_time = raw_time or m.group(1)
                if not start:
                    start, _ = parse_time_range(m.group(1))

        # --- 地址 (API.location > js_location > 正文段) ---
        addr = clean(api_data.get("location") or "") or (js_location or "")
        if not addr and content_text:
            m = re.search(
                r"(?:活动地点|地点|地址)\s*[：:]\s*([^\n。]{4,80})", content_text)
            if m:
                addr = clean(m.group(1))

        # --- 价格（重头戏：正文里挖最准） ---
        price = ""
        if content_text:
            price = _extract_price_from_content(content_text)
        # 若正文没找到，看 API 是否声明
        if not price:
            pr = api_data.get("priceRange", "")
            mc = api_data.get("moneyCount", 0)
            if pr:
                price = pr
            if mc and float(mc) > 0:
                price = f"{mc}元"
        pmin, pmax, is_free = parse_price(price)
        # 用 _isPay 二次校正：API priceRange 经常错误。
        # _isPay="1" = 收费, "0" = 免费, 这是真值。
        if js_is_pay == "1":
            # 收费活动；若价格识别不到具体数字 → 给一个明确提示
            if not price or price == "免费" or is_free:
                price = "需付费（具体金额详见正文）"
                is_free = False
                pmin = pmax = None
        elif js_is_pay == "0":
            # 明确免费
            if not price:
                price = "免费"
            is_free = True
            pmin = pmax = 0.0

        # --- 主办方 ---
        organizer = clean(api_data.get("shopName") or js_publisher or "")

        # --- city ---
        city = clean(api_data.get("cityName") or extract_city(addr) or city_default)

        # --- 描述 ---
        description = content_text[:500] if content_text else ""
        if not description:
            meta_desc = soup.select_one("meta[name='description']")
            if meta_desc:
                description = clean(meta_desc.get("content", ""))[:500]

        return Event(
            source=self.source,
            source_name=self.source_name,
            category="活动",
            title=title,
            url=url,
            city=city,
            address=addr,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price=price,
            price_min=pmin, price_max=pmax, is_free=is_free,
            poster=poster,
            organizer=organizer,
            description=description,
            extra={
                "party_hash": party_hash,
                "api_state": api_data.get("infoStateDesc", ""),
                "api_join": api_data.get("join"),
                "_isPay": js_is_pay,
            },
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )

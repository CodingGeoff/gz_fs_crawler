"""广州/佛山本地宝 - 休闲活动 / 美食 / 优惠 / 教育 等多频道。

列表入口（按频道）：
  广州: /xiuxian/ 休闲  /youhui/ 优惠/羊毛  /tour/ 旅游/景点
        /meishi/ 美食   /edu/ 教育/升学
  佛山: /xiuxian/  /youhui/  /tour/  /meishi/  /edu/

详情页结构（统一模板）：
  .top-title          标题
  .top-time span      发布时间
  .leading            导语
  .article-content    正文（包含「时间：xxx / 地点：xxx / 票价：xxx」）
  img[data-echo]      lazy load 海报
"""
from __future__ import annotations

import concurrent.futures as _cf
import re
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..base import BaseAdapter, Event
from ..utils import parse_time_range, parse_price, clean, extract_city


def _classify(url: str, title: str) -> str:
    if "/meishi/" in url:
        return "美食"
    if "/youhui/" in url:
        return "优惠"
    if "/job/" in url:
        return "招聘"
    if "/edu/" in url or "/peixun/" in url:
        return "教育"
    if any(k in title for k in ["美食", "餐厅", "小吃", "粤菜"]):
        return "美食"
    if any(k in title for k in ["招聘", "校招", "双选会"]):
        return "招聘"
    if any(k in title for k in ["展", "博物馆", "展览"]):
        return "展览"
    if any(k in title for k in ["演唱会", "音乐节", "话剧", "脱口秀", "音乐会", "Livehouse"]):
        return "演出"
    if any(k in title for k in ["讲座", "沙龙", "课程", "培训", "辅导"]):
        return "讲座"
    if any(k in title for k in ["免费", "免票", "优惠", "打折", "消费券"]):
        return "优惠"
    return "活动"


_STOP_KEYS = ["地点", "时间", "费用", "票价", "价格", "地址", "活动详情",
              "活动内容", "活动安排", "报名方式", "购票方式", "温馨提示",
              "门票", "比赛项目", "活动时间", "活动地点"]
_STOP_RE = "|".join(_STOP_KEYS)


def _extract_field_lines(lines: list[str], *keys: str) -> str:
    """在已分段的文本里逐行匹配，命中即返回该段中关键字之后的部分。"""
    for k in keys:
        for line in lines:
            m = re.search(rf"{k}\s*[：:]\s*(.+)$", line)
            if m:
                v = clean(m.group(1)).rstrip("：:，,；;")
                # 单段里仍可能含多字段，使用 _extract_field 的截止符再清一次
                for sk in _STOP_KEYS:
                    if sk != k and sk + "：" in v:
                        v = v.split(sk + "：")[0].strip()
                    if sk != k and sk + ":" in v:
                        v = v.split(sk + ":")[0].strip()
                if 1 < len(v) < 200:
                    return v
    return ""


def _extract_field(text: str, *keys: str) -> str:
    """从 '时间：xxx 地点：yyy' 文本中提取字段。

    截止符： 下一个字段关键字 / 换行 / 中文句号 / 多个空格。
    """
    for k in keys:
        # 必须有「：」或「:」分隔，避免标题里命中
        pat = rf"{k}\s*[：:]\s*(.+?)(?=\s*(?:{_STOP_RE})\s*[：:]|[。\n\r]|$)"
        m = re.search(pat, text)
        if m:
            v = clean(m.group(1)).rstrip("：:，,；;")
            if v and 1 < len(v) < 200:
                return v
    return ""


class _BendibaoBase(BaseAdapter):
    city_zh = ""             # 广州 / 佛山
    list_paths = [
        "/xiuxian/",     # 休闲活动
        "/youhui/",      # 优惠
        "/tour/",        # 旅游
        "/meishi/",      # 美食
        "/edu/",         # 教育
        "/job/",         # 招聘
        "/peixun/",      # 培训/考证
        "/life/",        # 生活百科
    ]
    per_channel_limit = 40   # 每频道最多抓取的详情数
    parallel_workers = 8     # 详情页并发数（同源连接复用）

    def fetch(self) -> Iterator[Event]:
        # 1. 收集所有频道里的详情 URL
        seen_detail: set[str] = set()
        all_urls: list[str] = []
        for path in self.list_paths:
            list_url = self.base_url.rstrip("/") + path
            try:
                html = self.http.text(list_url)
            except Exception as e:
                self.logger.warning("list page failed %s: %s", list_url, e)
                continue
            cands: list[str] = []
            for href in re.findall(
                r'href="([^"]+)"', html
            ):
                if re.search(
                    r"/(?:xiuxian|tour|youhui|news|meishi|edu|peixun|life|job|"
                    r"shopping|wenhua|wlj|huodong)"
                    r"/[\w\-/]+\d+\.shtm[l]?$", href
                ):
                    url = self.absolute(href)
                    # 过滤掉跨子域的链接 (job.gz.bendibao.com 等不可达)
                    if not url.startswith(self.base_url) and \
                       not url.startswith(self.base_url.replace("https://", "http://")):
                        continue
                    if url not in seen_detail:
                        seen_detail.add(url)
                        cands.append(url)
                        if len(cands) >= self.per_channel_limit:
                            break
            self.logger.info("%s -> %d detail urls (queue)",
                             list_url, len(cands))
            all_urls.extend(cands)

        if not all_urls:
            return

        # 2. 并发抓详情（同 HTTPClient，httpx 已带连接池）
        self.logger.info("bendibao: parallel fetch %d details (workers=%d)",
                         len(all_urls), self.parallel_workers)

        def _one(url):
            try:
                return self._parse_detail(url)
            except Exception as e:
                self.logger.warning("detail failed %s: %s", url, e)
                return None

        with _cf.ThreadPoolExecutor(max_workers=self.parallel_workers) as ex:
            for ev in ex.map(_one, all_urls):
                if ev:
                    yield ev

    def _parse_detail(self, url: str) -> Event | None:
        html = self.http.text(url)
        # 反爬识别：本地宝触发拼图验证页 / 风控页
        if ("请完成拼图验证" in html or "x5secdata" in html or
            len(html) < 3000 and "本地宝" not in html[:1000]):
            self.logger.info("[%s] WAF challenge page, skip", url)
            return None
        soup = BeautifulSoup(html, "lxml")

        # 标题：PC 端 .top-title / 移动端 h1 / 兜底 <title>
        title_node = (soup.select_one(".top-title")
                      or soup.select_one("h1")
                      or soup.select_one("title"))
        if not title_node:
            return None
        title = clean(title_node.get_text(" ", strip=True))
        title = re.sub(r"\s*-\s*[广佛][州山]本地宝\s*$", "", title)
        if not title or "请完成拼图验证" in title:
            return None

        # 导语 + 正文（PC: .leading + .article-content；
        #              移动: .content / .article / #articleContent）
        leading = soup.select_one(".leading")
        article = (soup.select_one(".article-content")
                   or soup.select_one(".main-article")
                   or soup.select_one(".content")
                   or soup.select_one("#articleContent")
                   or soup.select_one("article"))
        paras: list[str] = []
        if leading:
            paras.append(clean(leading.get_text(" ", strip=True)))
        if article:
            for p in article.select("p"):
                t = clean(p.get_text(" ", strip=True))
                if t:
                    paras.append(t)
        # 用换行连接，确保 _extract_field 的换行截止符生效
        body_text = "\n".join(paras)

        # 字段抽取（基于段落级文本）
        raw_time = _extract_field_lines(paras, "时间", "活动时间", "开放时间",
                                        "举办时间", "演出时间", "展览时间",
                                        "活动日期", "展期")
        address  = _extract_field_lines(paras, "地点", "地址", "活动地点", "举办地点",
                                        "展览地点", "演出地点")
        price    = _extract_field_lines(paras, "票价", "费用", "价格", "门票")

        start, end = parse_time_range(raw_time)
        # 兜底：从导语 + 所有段落里再找一遍时间
        if not start:
            from ..utils import find_time_in_text
            raw2, s2, e2 = find_time_in_text("\n".join(paras))
            if s2:
                start, end = s2, e2
                if not raw_time:
                    raw_time = raw2
        # 仍无 -> 用发布时间兜底（攻略文）
        # 优先 .top-time span (PC) / og:release_date (移动) / .time
        pub_node = soup.select_one(".top-time span") or soup.select_one(".time")
        pub_raw = clean(pub_node.get_text(strip=True)) if pub_node else ""
        if not pub_raw:
            og = soup.select_one("meta[property='og:release_date']")
            if og:
                pub_raw = clean(og.get("content", ""))
        if not pub_raw:
            # 移动端常用 meta name="apub:time" 或 类似
            for sel in ("meta[name='pubdate']", "meta[name='publishdate']",
                        "meta[property='article:published_time']"):
                m = soup.select_one(sel)
                if m and m.get("content"):
                    pub_raw = clean(m["content"])
                    break
        if not start and pub_raw:
            s3, _ = parse_time_range(pub_raw)
            if s3:
                start = s3
                if not raw_time:
                    raw_time = pub_raw + "（发布时间）"
        # 价格解析：优先用明确的 price 字段，没有则从正文里**带关键字**搜索（不喂全文）
        if not price:
            from ..utils import find_price_in_text
            price = find_price_in_text(body_text)
        pmin, pmax, is_free = parse_price(price) if price else (None, None, None)

        # 海报：取正文里第一张 data-echo 大图
        poster = ""
        if article:
            for img in article.select("img"):
                src = img.get("data-echo") or img.get("src") or img.get("data-src")
                if not src:
                    continue
                if "/icons/" in src or "/logo" in src or "qrcode" in src.lower():
                    continue
                poster = self.absolute(src)
                break

        # 发布时间（已在上面提取过，重用）
        pub = pub_raw

        city = extract_city(address) or self.city_zh

        return Event(
            source=self.source,
            source_name=self.source_name,
            category=_classify(url, title),
            title=title,
            url=url,
            city=city,
            address=address,
            start_time=start,
            end_time=end,
            raw_time=raw_time,
            price=price,
            price_min=pmin,
            price_max=pmax,
            is_free=is_free,
            poster=poster,
            description=clean(body_text)[:500],
            extra={"published": pub},
            crawled_at=datetime.now().isoformat(timespec="seconds"),
        )


class BendibaoGZ(_BendibaoBase):
    source = "bendibao_gz"
    source_name = "广州本地宝"
    base_url = "https://gz.bendibao.com"
    city_zh = "广州"


class BendibaoFS(_BendibaoBase):
    source = "bendibao_fs"
    source_name = "佛山本地宝"
    base_url = "https://fs.bendibao.com"
    city_zh = "佛山"

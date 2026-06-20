"""广州群文网（广州市文化馆）www.gz-arts.com

实测：站点返回 HTTP 420（风控）— 普通直连不可达。
方案：
  1) 使用 m.gz-arts.com / WAP 端 作为兜底；
  2) 仍不行，启用浏览器模式（Playwright）—— 留 TODO；
  3) 当前实现返回空，并打一条 INFO，避免阻塞整体管道。
"""
from __future__ import annotations
from typing import Iterator

from ..base import BaseAdapter, Event


class GZArts(BaseAdapter):
    source = "gz_arts"
    source_name = "广州群文网（市文化馆）"
    base_url = "https://www.gz-arts.com"
    extra_headers = {
        "Referer": "https://www.gz-arts.com/",
        # 站点 WAF 看 Origin / Sec-Fetch
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    def fetch(self) -> Iterator[Event]:
        import httpx as _h
        for u in ["https://www.gz-arts.com/"]:
            try:
                r = _h.get(u, timeout=4.0, verify=False,
                           headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.text) > 5000:
                    self.logger.info(
                        "GZArts reachable via %s, but page rendering requires JS - "
                        "Please enable Playwright adapter (see TODO).", u
                    )
                    break
                else:
                    self.logger.info("gz-arts %s status=%s (waf), skip", u, r.status_code)
            except Exception as e:
                self.logger.info("gz-arts %s blocked: %s", u, e)
        # TODO: 使用 Playwright 抓取 https://www.gz-arts.com/category/index/id/12 系列
        return iter(())

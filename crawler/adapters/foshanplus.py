"""佛山+ foshanplus.com

整站是 Vue SPA，初始 HTML 只有 <div id="app"></div>。
真实数据走后端 API；当前未公开稳定 endpoint。
方案：
  - 嗅探 main.js 寻找 api 前缀，并尝试列表接口；
  - 暂未拿到接口前，本 adapter 返回空；提供 Playwright fallback 入口（TODO）。
"""
from __future__ import annotations
import re
from typing import Iterator

from ..base import BaseAdapter, Event


class FoshanPlus(BaseAdapter):
    source = "foshanplus"
    source_name = "佛山+"
    base_url = "https://foshanplus.com"

    def fetch(self) -> Iterator[Event]:
        try:
            html = self.http.text(self.base_url + "/")
            js_match = re.search(r'src="(\./assets/index-[\w-]+\.js)"', html)
            if js_match:
                self.logger.info(
                    "foshanplus SPA detected, main bundle: %s -- "
                    "Need to reverse-engineer JSON API or use Playwright (TODO).",
                    js_match.group(1),
                )
        except Exception as e:
            self.logger.info("foshanplus fetch failed: %s", e)
        return iter(())

"""爱 LiveHouse - 全国 livehouse 演出汇总。

http://www.ilivehouse.com/yanchu/list-guangzhou-all-1.html

实测页面正文被 51.la 反扒脚本动态写入（HTML 静态部分只有混淆代码），
非浏览器请求拿不到列表。需要 Playwright 渲染。
"""
from __future__ import annotations
from typing import Iterator

from ..base import BaseAdapter, Event


class ILiveHouse(BaseAdapter):
    source = "ilivehouse"
    source_name = "爱LiveHouse"
    base_url = "http://www.ilivehouse.com"
    needs_browser = True

    def fetch(self) -> Iterator[Event]:
        self.logger.info("iLivehouse adapter requires browser rendering; "
                         "enable via Playwright (see TODO).")
        return iter(())

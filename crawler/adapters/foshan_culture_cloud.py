"""佛山文化云 wh.fs.cn

实测：直连超时 / 域名不可达（公网 DNS 解析 OK，TCP 握手挂起）。
该平台对来自非粤 ISP 的访问做了限制。
方案：
  - 留 adapter 入口；返回空；
  - 用户可在 README 中按指引启用本地代理后再抓。
"""
from __future__ import annotations
from typing import Iterator

from ..base import BaseAdapter, Event


class FoshanCultureCloud(BaseAdapter):
    source = "foshan_culture_cloud"
    source_name = "佛山文化云"
    base_url = "https://wh.fs.cn"

    def fetch(self) -> Iterator[Event]:
        import httpx as _h
        try:
            r = _h.get(self.base_url + "/", timeout=4.0, verify=False)
            if r.status_code == 200:
                self.logger.info("wh.fs.cn reachable - TODO: parse activity list")
        except Exception as e:
            self.logger.info("wh.fs.cn unreachable in current network: %s", e)
        return iter(())

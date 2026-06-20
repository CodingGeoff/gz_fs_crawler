"""反爬绕过插件。

当前包含：
  bendibao_puzzle_bypass(client, url, html) -> bool
    检测页面是否为本地宝 "请完成拼图验证" 风控页。
    若是，直接读 HTML 里硬编码的 targetX/targetY，向同源 /verify_puzzle
    端点提交一次 GET，成功后会在 client.cookies 里写入 antibot_challenge
    cookie，之后后续请求即可正常返回。

  返回 True 代表已经成功绕过；调用方应该用同一个 client 再 GET 一遍 url。
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

log = logging.getLogger("crawler.bypass")


_CHALLENGE_MARKER = "请完成拼图验证"
_CFG_RE = re.compile(r"window\.CHALLENGE_CONFIG\s*=\s*\{(.*?)\}\s*;", re.S)


def _parse_challenge_config(text: str) -> Optional[dict]:
    m = _CFG_RE.search(text)
    if not m:
        return None
    cfg_text = m.group(1)
    cfg: dict = {}
    for m1 in re.finditer(r'(\w+)\s*:\s*"([^"]*)"', cfg_text):
        cfg[m1.group(1)] = m1.group(2)
    for m2 in re.finditer(r'(\w+)\s*:\s*(\d+)', cfg_text):
        cfg.setdefault(m2.group(1), int(m2.group(2)))
    return cfg


def bendibao_puzzle_bypass(client: httpx.Client, url: str, html: str) -> bool:
    """尝试绕过本地宝拼图验证。成功返回 True。"""
    if _CHALLENGE_MARKER not in html:
        return False
    cfg = _parse_challenge_config(html)
    if not cfg or "host" not in cfg or "challengeId" not in cfg:
        log.warning("[bendibao] challenge page but no CONFIG, give up")
        return False
    verify_url = f"https://{cfg['host']}/verify_puzzle"
    try:
        r = client.get(
            verify_url,
            params={
                "challenge_id": cfg["challengeId"],
                "pos_x": str(cfg.get("targetX", 0)),
                "pos_y": str(cfg.get("targetY", 0)),
            },
            headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"},
            timeout=8,
        )
        ok = (r.status_code == 200 and
              "antibot_challenge" in client.cookies)
        log.info("[bendibao] puzzle bypass on %s -> %s (status=%s)",
                 cfg["host"], "OK" if ok else "FAIL", r.status_code)
        return ok
    except Exception as e:
        log.warning("[bendibao] verify_puzzle failed: %s", e)
        return False

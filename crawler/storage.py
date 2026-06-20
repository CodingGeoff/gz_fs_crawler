"""统一输出：JSON / CSV / SQLite + 海报下载。"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import logging
from pathlib import Path
from typing import Iterable

import httpx

from .base import Event, DEFAULT_UA

log = logging.getLogger("crawler.storage")


def dump_json(events: Iterable[Event], path: str | os.PathLike):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in events], f,
                  ensure_ascii=False, indent=2)


def dump_csv(events: Iterable[Event], path: str | os.PathLike):
    rows = [e.to_dict() for e in events]
    if not rows:
        # 仍写个空表头，方便下游消费
        rows_headers = list(Event(
            source="", source_name="", category="", title="", url=""
        ).to_dict().keys())
    else:
        rows_headers = list(rows[0].keys())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows_headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                 for k, v in r.items()}
            w.writerow(r)


def dump_sqlite(events: list[Event], path: str | os.PathLike):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            uid TEXT PRIMARY KEY,
            source TEXT, source_name TEXT, category TEXT,
            title TEXT, url TEXT,
            city TEXT, district TEXT, venue TEXT, address TEXT,
            start_time TEXT, end_time TEXT, raw_time TEXT,
            price TEXT, price_min REAL, price_max REAL, is_free INTEGER,
            poster TEXT, poster_local TEXT,
            tags TEXT, organizer TEXT, description TEXT,
            extra TEXT, crawled_at TEXT,
            status TEXT, sort_key TEXT
        );
    """)
    # 老库迁移
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    for col in ("status", "sort_key"):
        if col not in cols:
            conn.execute(f"ALTER TABLE events ADD COLUMN {col} TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status_sort ON events(status, sort_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_city_cat ON events(city, category)")

    for e in events:
        d = e.to_dict()
        conn.execute("""
            INSERT OR REPLACE INTO events VALUES (
                :uid,:source,:source_name,:category,
                :title,:url,
                :city,:district,:venue,:address,
                :start_time,:end_time,:raw_time,
                :price,:price_min,:price_max,:is_free,
                :poster,:poster_local,
                :tags,:organizer,:description,
                :extra,:crawled_at,
                :status,:sort_key
            )
        """, {
            "uid": e.uid,
            **{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
               for k, v in d.items()}
        })
    conn.commit()
    conn.close()


def download_posters(events: list[Event], out_dir: str | os.PathLike,
                     limit: int = 200, timeout: float = 15.0):
    """下载所有有效海报到 out_dir, 写回 event.poster_local。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": DEFAULT_UA, "Referer": ""}
    with httpx.Client(timeout=timeout, follow_redirects=True, verify=False,
                      headers=headers) as cli:
        n = 0
        for e in events:
            if not e.poster or not e.poster.startswith("http"):
                continue
            if n >= limit:
                break
            ext = e.poster.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
                ext = "jpg"
            fname = f"{e.source}_{e.uid[:12]}.{ext}"
            fp = out_dir / fname
            if fp.exists():
                e.poster_local = str(fp.relative_to(out_dir.parent))
                continue
            try:
                r = cli.get(e.poster, headers={"Referer": e.url or ""})
                if r.status_code == 200 and len(r.content) > 1024:
                    fp.write_bytes(r.content)
                    e.poster_local = str(fp.relative_to(out_dir.parent))
                    n += 1
            except Exception as ex:
                log.debug("poster %s fail: %s", e.poster, ex)
    log.info("downloaded %d posters", n)

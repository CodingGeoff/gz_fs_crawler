"""主入口：python run.py [--source xxx] [--no-poster] [--max-pages N]

输出文件：
  data/events.json           全部活动 JSON
  data/events.csv            CSV（Excel 直接打开）
  data/events.sqlite         SQLite, 表名 events
  data/by_category/*.json    按分类拆分
  data/by_source/*.json      按数据源拆分
  data/posters/              海报本地副本
  data/summary.md            人类可读摘要
"""
from __future__ import annotations

import argparse
import concurrent.futures as _cf
import json
import logging
import time
from collections import Counter, defaultdict
from pathlib import Path

from crawler.adapters import ALL_ADAPTERS
from crawler.base import safe_iter
from crawler.storage import dump_json, dump_csv, dump_sqlite, download_posters


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crawler.run")

DATA_DIR = Path(__file__).parent / "data"
POSTERS_DIR = DATA_DIR / "posters"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", "-s", action="append", default=None,
                    help="只跑指定 source（可多次），默认全跑。")
    ap.add_argument("--max-pages", type=int, default=2,
                    help="多页站点每站抓多少页 (默认 2)。")
    ap.add_argument("--no-poster", action="store_true",
                    help="不下载海报，仅保留 URL")
    ap.add_argument("--poster-limit", type=int, default=120)
    ap.add_argument("--out", default=str(DATA_DIR), help="输出目录")
    ap.add_argument("--workers", type=int, default=6,
                    help="并行运行的 adapter 数 (默认 6)。设 1 = 串行")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    adapters = [cls(max_pages=args.max_pages) for cls in ALL_ADAPTERS
                if not args.source or cls.source in args.source]
    log.info("启用 %d 个 adapter (并行 %d): %s",
             len(adapters), args.workers,
             ", ".join(a.source for a in adapters))

    all_events = []
    per_source: dict[str, int] = {}
    started = time.time()

    # 并行运行所有 adapter — 每个 adapter 有自己的 HTTPClient (httpx 池)
    def _run(ad):
        t0 = time.time()
        evs = safe_iter(ad)
        log.info("[%s] %d events (%.1fs)", ad.source_name, len(evs),
                 time.time() - t0)
        return ad.source_name, evs

    seen_uids: set[str] = set()
    if args.workers <= 1:
        results = (_run(ad) for ad in adapters)
    else:
        with _cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(_run, adapters))

    for name, evs in results:
        unique = []
        for e in evs:
            if e.uid in seen_uids:
                continue
            seen_uids.add(e.uid)
            unique.append(e)
        per_source[name] = len(unique)
        all_events.extend(unique)

    # 统计时间字段完整度
    with_time = sum(1 for e in all_events if e.start_time)
    log.info("总计 %d 条 / 含时间 %d (%.0f%%) / 耗时 %.1fs",
             len(all_events), with_time,
             100 * with_time / max(1, len(all_events)),
             time.time() - started)

    # 按 status + sort_key 排序：未来 → 今天 → 归档
    all_events.sort(key=lambda e: (e.sort_key or "9_") )

    # 海报下载（优先给 upcoming/today 下载，archived 留位）
    if not args.no_poster and all_events:
        log.info("下载海报中 (最多 %d 张, 优先未过期活动) ...", args.poster_limit)
        priority = [e for e in all_events if e.status in ("today", "upcoming")]
        rest = [e for e in all_events if e.status not in ("today", "upcoming")]
        download_posters(priority + rest, POSTERS_DIR, limit=args.poster_limit)

    # 输出
    dump_json(all_events, out_dir / "events.json")
    dump_csv(all_events, out_dir / "events.csv")
    dump_sqlite(all_events, out_dir / "events.sqlite")

    # 分类 / 来源 / 状态 拆分
    by_cat: dict[str, list] = defaultdict(list)
    by_src: dict[str, list] = defaultdict(list)
    by_st:  dict[str, list] = defaultdict(list)
    for e in all_events:
        by_cat[e.category or "其他"].append(e)
        by_src[e.source].append(e)
        by_st[e.status or "unknown"].append(e)
    for cat, lst in by_cat.items():
        dump_json(lst, out_dir / "by_category" / f"{cat}.json")
    for src, lst in by_src.items():
        dump_json(lst, out_dir / "by_source" / f"{src}.json")
    for st, lst in by_st.items():
        dump_json(lst, out_dir / "by_status" / f"{st}.json")

    # Summary markdown
    write_summary(all_events, per_source, out_dir / "summary.md")
    log.info("✅ 已写入 %s", out_dir.resolve())


def write_summary(events, per_source, path: Path):
    cat_count = Counter(e.category for e in events)
    city_count = Counter(e.city for e in events if e.city)
    status_count = Counter(e.status for e in events)
    free_count = sum(1 for e in events if e.is_free)
    with_poster = sum(1 for e in events if e.poster)
    with_time = sum(1 for e in events if e.start_time)
    no_time = len(events) - with_time
    lines = [
        "# 广佛大学生活动 / 羊毛聚合 - 抓取概况",
        "",
        f"- 抓取总数: **{len(events)}**",
        f"- 含海报: {with_poster}",
        f"- 含确定开始时间: **{with_time}** ({100*with_time//max(1,len(events))}%)",
        f"- 未识别出时间: {no_time}",
        f"- 免费活动: {free_count}",
        "",
        "## 按状态（基于当前时间）",
        "",
        f"- 🔥 进行中/今天 (today): **{status_count.get('today', 0)}**",
        f"- ⏰ 即将开始 (upcoming): **{status_count.get('upcoming', 0)}**",
        f"- 📦 已归档 (archived): {status_count.get('archived', 0)}",
        f"- ❓ 未知时间 (unknown): {status_count.get('unknown', 0)}",
        "",
        "## 按来源",
        ""
    ]
    for k, v in sorted(per_source.items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    lines += ["", "## 按分类", ""]
    for k, v in cat_count.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## 按城市", ""]
    for k, v in city_count.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", "## 即将到来 TOP 10", ""]
    upcoming = [e for e in events if e.status in ("today", "upcoming")][:10]
    for e in upcoming:
        lines.append(
            f"- **[{e.category}]** {e.title}  \n"
            f"  📍 {e.address or '-'} | 🕒 {e.start_time or e.raw_time or '-'} | "
            f"💰 {e.price or '-'} | 🌐 {e.source_name}  \n"
            f"  {e.url}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

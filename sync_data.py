"""同步数据到 public/ 目录，并合并过往数据（不删除历史活动）。

逻辑：
  1. 读取 backup/events.json（过往快照）
  2. 读取 data/events.json（最新抓取）
  3. 按 uid 合并：新数据覆盖同 uid 旧数据，旧数据中独有的活动保留
  4. 写入 public/data/events.json
  5. 复制 posters 到 public/posters/
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
PUBLIC_DATA = PUBLIC_DIR / "data"
PUBLIC_POSTERS = PUBLIC_DIR / "posters"


def load_json(p: Path):
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  读取 {p} 失败: {e}")
        return []


def uid_of(e: dict) -> str:
    """与 Event.uid 一致：md5(url+title)。"""
    if e.get("uid"):
        return e["uid"]
    key = (e.get("url", "") + "|" + e.get("title", "")).encode("utf-8")
    return hashlib.md5(key).hexdigest()


def merge_events(old: list[dict], new: list[dict]) -> list[dict]:
    """合并：新数据优先，旧数据中独有的活动保留（标为 archived）。"""
    by_uid = {}
    # 先放旧数据
    for e in old:
        by_uid[uid_of(e)] = e
    # 新数据覆盖
    added = 0
    for e in new:
        uid = uid_of(e)
        if uid not in by_uid:
            added += 1
        by_uid[uid] = e
    print(f"  过往活动: {len(old)} / 新抓取: {len(new)} (新增 {added}) / 合并后: {len(by_uid)}")
    # 排序
    out = list(by_uid.values())
    out.sort(key=lambda e: (e.get("sort_key") or "9_"))
    return out


def copy_posters():
    src = DATA_DIR / "posters"
    if not src.exists():
        print("  ⚠️  无 posters 目录")
        return 0
    PUBLIC_POSTERS.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src.iterdir():
        if f.is_file():
            dst = PUBLIC_POSTERS / f.name
            if not dst.exists() or dst.stat().st_size != f.stat().st_size:
                shutil.copy2(f, dst)
            n += 1
    return n


def main():
    print("📦 同步数据到 public/ ...")

    # 找最新的 backup
    backups = sorted(ROOT.glob("data_backup_*"))
    old_events = []
    if backups:
        old_events = load_json(backups[-1] / "events.json")
        print(f"  使用备份: {backups[-1].name} ({len(old_events)} 条)")
    else:
        print("  无备份，仅使用新数据")

    new_events = load_json(DATA_DIR / "events.json")
    if not new_events:
        print("  ⚠️  无新数据 (data/events.json)，仅使用备份")
        new_events = []

    merged = merge_events(old_events, new_events)

    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    out_path = PUBLIC_DATA / "events.json"
    out_path.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"  ✅ 写入 {out_path} ({size_kb:.0f} KB)")

    n = copy_posters()
    print(f"  ✅ 复制 {n} 张海报到 {PUBLIC_POSTERS}")

    # 统计
    from collections import Counter
    st = Counter(e.get("status", "unknown") for e in merged)
    print(f"  📊 总计 {len(merged)} 条: 🔥{st.get('today',0)} ⏰{st.get('upcoming',0)} 📦{st.get('archived',0)} ❓{st.get('unknown',0)}")


if __name__ == "__main__":
    main()

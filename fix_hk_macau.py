"""修正 events.json 中被误标为深圳/珠海的香港/澳门活动。

问题：eventbrite/meetup 按 URL slug 赋 city，不校验实际地点，
导致香港/澳门活动被标为"深圳"/"珠海"。

修复：扫描 venue + address，若包含香港/澳门关键字则修正 city。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from crawler.utils import detect_hk_macau, extract_city


def fix_events(events: list[dict]) -> tuple[list[dict], int]:
    """修正 city 字段，返回 (修正后列表, 修正数量)。"""
    fixed = 0
    for e in events:
        text = " ".join(filter(None, [e.get("venue", ""), e.get("address", ""),
                                        e.get("organizer", "")]))
        real = detect_hk_macau(text)
        if real and e.get("city") != real:
            # 误标为深圳/珠海/广州 → 修正为香港/澳门
            old = e.get("city", "")
            e["city"] = real
            fixed += 1
            print(f"  [{e.get('source')}] {old} -> {real}: {e.get('title', '')[:40]}")
        elif not real and e.get("city") in ("香港", "澳门"):
            # 之前误标为港澳但实际不在港澳 → 从地址重新提取城市
            real_city = extract_city(e.get("address", "") + " " + e.get("venue", ""))
            if real_city and real_city not in ("香港", "澳门"):
                old = e.get("city", "")
                e["city"] = real_city
                fixed += 1
                print(f"  [revert] {old} -> {real_city}: {e.get('title', '')[:40]}")
    return events, fixed


def main():
    for path in [ROOT / "data" / "events.json", ROOT / "public" / "data" / "events.json"]:
        if not path.exists():
            print(f"跳过（不存在）: {path}")
            continue
        print(f"\n处理: {path}")
        events = json.loads(path.read_text(encoding="utf-8"))
        print(f"  总计 {len(events)} 条活动")
        events, fixed = fix_events(events)
        print(f"  修正 {fixed} 条")
        if fixed > 0:
            path.write_text(
                json.dumps(events, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            print(f"  已写回 {path}")

    # 统计修正后的城市分布
    path = ROOT / "public" / "data" / "events.json"
    if path.exists():
        events = json.loads(path.read_text(encoding="utf-8"))
        from collections import Counter
        cities = Counter(e.get("city", "") for e in events)
        print("\n城市分布:")
        for city, cnt in cities.most_common():
            print(f"  {city or '(空)':<8} {cnt}")


if __name__ == "__main__":
    main()

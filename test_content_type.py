# -*- coding: utf-8 -*-
"""测试 detect_content_type 准确性。"""
import json
import sys
from crawler.utils import detect_content_type

sys.stdout.reconfigure(encoding="utf-8")

d = json.load(open("public/data/events.json", encoding="utf-8"))

event_cnt = 0
info_cnt = 0
info_samples = []
misjudge_risk = []  # 可能误判的真实活动

for e in d:
    ct = detect_content_type(e)
    if ct == "info":
        info_cnt += 1
        info_samples.append(e)
    else:
        event_cnt += 1
        # 检查是否有真实活动被误判的风险
        title = e.get("title", "")
        # 有场地有时间的应该是 event，确认
        has_venue = bool(e.get("venue") or e.get("address"))
        has_time = bool(e.get("start_time", "")) and "8888" not in e.get("start_time", "")
        if not has_venue and not has_time:
            misjudge_risk.append(e)

print(f"活动(event): {event_cnt}")
print(f"资讯(info): {info_cnt}")
print(f"总计: {len(d)}")
print()

# 检查 info 中是否有误判（有明确场地+时间的真实活动）
print("=== 检查 info 中是否有误判（有场地+时间的） ===")
false_positive = 0
for e in info_samples:
    has_venue = bool(e.get("venue") or e.get("address"))
    st = e.get("start_time", "")
    has_real_time = bool(st) and "8888" not in st and "9999" not in st
    if has_venue and has_real_time:
        false_positive += 1
        print(f"  [误判] {e.get('title','')[:50]} | venue={e.get('venue','')} | time={st}")
print(f"误判数: {false_positive}")

print()
print("=== info 样本（前30条） ===")
for e in info_samples[:30]:
    title = e.get("title", "?")[:55]
    st = e.get("start_time", "")[:10] or "无"
    venue = e.get("venue", "") or e.get("address", "") or "无场地"
    print(f"  {st} | {title}")

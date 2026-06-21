# -*- coding: utf-8 -*-
"""修复现有 events.json 中的脏数据：
1. 异常年份（8888/9999 等）→ 清空 start_time/end_time，状态改 unknown
2. 添加 content_type 字段（event/info）
"""
import json
import re
import sys
from pathlib import Path
from crawler.utils import detect_content_type

sys.stdout.reconfigure(encoding="utf-8")

p = Path("public/data/events.json")
data = json.loads(p.read_text(encoding="utf-8"))

print(f"读取 {len(data)} 条事件")

# 1. 修复异常日期
YEAR_PAT = re.compile(r"^(\d{4})")
fixed_date = 0
for e in data:
    for k in ("start_time", "end_time"):
        v = e.get(k, "")
        if not v:
            continue
        m = YEAR_PAT.match(v)
        if m:
            y = int(m.group(1))
            if y < 2000 or y > 2100:
                print(f"  [异常日期] {k}={v} → 清空 | {e.get('title','')[:40]}")
                e[k] = ""
                fixed_date += 1

# 清空日期后重新判定状态
from datetime import datetime
now = datetime.now()
today_str = now.strftime("%Y-%m-%d")
fixed_status = 0
for e in data:
    s = e.get("start_time", "")
    e_dt = e.get("end_time", "") or s
    if not s:
        if e.get("status") != "unknown":
            e["status"] = "unknown"
            e["sort_key"] = "9_"
            fixed_status += 1
        continue
    # 重新计算 sort_key
    try:
        if s[:10] == today_str:
            e["status"] = "today"
            e["sort_key"] = "1_" + s[:16]
        elif s[:10] < today_str:
            e["status"] = "archived"
            e["sort_key"] = "5_" + s[:10]
        else:
            e["status"] = "upcoming"
            e["sort_key"] = "2_" + s[:16]
    except Exception:
        pass

print(f"修复异常日期: {fixed_date} 条")

# 2. 添加 content_type
info_cnt = 0
for e in data:
    ct = detect_content_type(e)
    e["content_type"] = ct
    if ct == "info":
        info_cnt += 1
print(f"标注资讯类: {info_cnt} 条")

# 写回
p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
             encoding="utf-8")
print(f"✅ 写入 {p} ({p.stat().st_size / 1024:.0f} KB)")

# 统计
from collections import Counter
st = Counter(e.get("status", "unknown") for e in data)
ct = Counter(e.get("content_type", "event") for e in data)
print(f"状态: 🔥{st.get('today',0)} ⏰{st.get('upcoming',0)} 📦{st.get('archived',0)} ❓{st.get('unknown',0)}")
print(f"类型: 🎫活动{ct.get('event',0)} 📰资讯{ct.get('info',0)}")

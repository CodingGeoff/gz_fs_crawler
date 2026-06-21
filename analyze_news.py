# -*- coding: utf-8 -*-
"""分析疑似非活动内容（推文/新闻/攻略/百科等）。"""
import json
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

d = json.load(open("public/data/events.json", encoding="utf-8"))

# 非活动标题关键词（攻略/指南/盘点/新闻/公告等）
NEWS_PAT = re.compile(
    r"指南|攻略|盘点|推荐|汇总|名单|排行榜|排行|百科|常识|须知|解读|"
    r"大全|宝典|避坑|防骗|科普|问答|解析|评测|测评|清单|手册|教程|"
    r"秘籍|秘笈|必看|必去|必吃|打卡|网红|收藏|转发|关注|投票|抽奖|"
    r"福利|赠书|赠票|公告|通知|声明|回应|辟谣|最新消息|快讯|资讯|"
    r"报道|新闻|资讯|动态|更新|上线|发布|推出|开通|启动|举办.*?届|"
    r"入选|荣获|获奖|上榜|跻身|位列"
)

suspect = []
for e in d:
    title = e.get("title", "")
    st = e.get("start_time", "")
    has_time = bool(st) and "8888" not in st and "9999" not in st
    has_venue = bool(e.get("venue") or e.get("address"))
    is_news = bool(NEWS_PAT.search(title))
    # 疑似非活动：标题命中新闻关键词 OR 无明确时间 AND 无地点
    if (is_news or not has_time) and not has_venue:
        suspect.append(e)

print(f"疑似非活动内容: {len(suspect)} 条 (总 {len(d)} 条)")
print("=" * 60)

# 按来源统计
src_cnt = Counter(e.get("source", "?") for e in suspect)
print("\n按来源分布:")
for s, c in src_cnt.most_common():
    name = next((e.get("source_name", s) for e in suspect if e.get("source") == s), s)
    print(f"  {name}: {c}")

print("\n--- 标题样本 (前40条) ---")
for e in suspect[:40]:
    src = e.get("source_name", "?")
    title = e.get("title", "?")[:55]
    st = e.get("start_time", "")[:10] or "无"
    print(f"  [{src}] {st} | {title}")

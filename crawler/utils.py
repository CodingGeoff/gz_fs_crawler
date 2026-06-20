"""日期 / 价格 / 文本 通用解析器。

时间解析支持以下中文格式（全部经过实际站点验证）：
  ✓ 2026年5月1日（周五）10:00-11:30
  ✓ 2026年5月1日 10:00 - 11:30
  ✓ 2026年5月1-2日
  ✓ 2026年5月1日-5月5日
  ✓ 2026年5月1日-2026年5月5日
  ✓ 2026-06-03 19:30
  ✓ 2026/06/03 19:30
  ✓ 06月03日 周三 19:30 ~ 06月30日 周二 21:00
  ✓ 5月1日 10:00
  ✓ 单点："2026年6月6日" 或 "2026-06-03"
"""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# 时间解析
# ---------------------------------------------------------------------------
_WEEK = r"(?:[（(]?[周星期][一二三四五六日天][)）]?)?"

# 完整日期片段：2026年5月1日 或 2026-05-01 或 2026/5/1
_FULL_DATE = (
    r"(?P<y{i}>\d{{4}})\s*[年\-/.]\s*"
    r"(?P<m{i}>\d{{1,2}})\s*[月\-/.]\s*"
    r"(?P<d{i}>\d{{1,2}})\s*日?"
)
# 月日片段：5月1日 或 05-01 / 05/01
_MD_DATE = (
    r"(?P<m{i}>\d{{1,2}})\s*[月\-/.]\s*"
    r"(?P<d{i}>\d{{1,2}})\s*日?"
)
# 时分片段
_HM = r"(?P<H{i}>\d{{1,2}})\s*[:点：]\s*(?P<M{i}>\d{{2}})"


def _hm(text: str) -> list[tuple[int, int]]:
    """返回文本中所有 HH:MM 时间点。"""
    return [(int(h), int(m)) for h, m in
            re.findall(r"(\d{1,2})\s*[:点：]\s*(\d{2})", text)]


def _safe_date(y, m, d, H=None, M=None) -> str:
    try:
        if H is not None:
            return datetime(int(y), int(m), int(d), int(H), int(M)).strftime("%Y-%m-%d %H:%M")
        return date(int(y), int(m), int(d)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


_REL_DAYS = {
    "今天": 0, "今日": 0,
    "明天": 1, "明日": 1,
    "后天": 2,
    "大后天": 3,
}


def _resolve_relative(text: str) -> Tuple[str, str]:
    """把 '明天 14:00' / '后天 14:00 - 18:00' 这种解析为 (start_iso, end_iso)。
    返回 ('','') 表示未命中。
    """
    if not text:
        return "", ""
    from datetime import timedelta
    now = datetime.now()
    for k, off in _REL_DAYS.items():
        if k in text:
            d = (now + timedelta(days=off)).date()
            times = _hm(text)
            if times:
                s = datetime(d.year, d.month, d.day, times[0][0],
                             times[0][1]).strftime("%Y-%m-%d %H:%M")
                e = ""
                if len(times) > 1:
                    e = datetime(d.year, d.month, d.day, times[1][0],
                                 times[1][1]).strftime("%Y-%m-%d %H:%M")
                return s, e
            return d.strftime("%Y-%m-%d"), ""
    return "", ""


def parse_time_range(text: str, default_year: Optional[int] = None) -> Tuple[str, str]:
    """从一段杂乱文本里解析 (start_iso, end_iso)。

    返回 ("","") 表示完全失败；只有起点时 end 为空。
    """
    if not text:
        return "", ""
    text = text.replace("\u00a0", " ").strip()
    default_year = default_year or datetime.now().year

    # === 0. 相对时间：今天/明天/后天 ===
    s, e = _resolve_relative(text)
    if s:
        return s, e

    times = _hm(text)
    t1 = times[0] if times else None
    t2 = times[1] if len(times) > 1 else None

    # === 1. 两个完整日期：A年B月C日 ... X年Y月Z日 ===
    m = re.search(
        _FULL_DATE.format(i=1) + r".*?[-~至到]\s*" + _FULL_DATE.format(i=2),
        text, re.S)
    if m:
        s = _safe_date(m["y1"], m["m1"], m["d1"], *(t1 or (None, None)))
        e = _safe_date(m["y2"], m["m2"], m["d2"], *(t2 or t1 or (None, None)))
        if s and e:
            return s, e

    # === 2. 一个完整日期 + 月日：2026年5月1日-5月5日 ===
    m = re.search(
        _FULL_DATE.format(i=1) + r"\s*[-~至到]\s*" + _MD_DATE.format(i=2),
        text)
    if m:
        s = _safe_date(m["y1"], m["m1"], m["d1"], *(t1 or (None, None)))
        e = _safe_date(m["y1"], m["m2"], m["d2"], *(t2 or t1 or (None, None)))
        if s and e:
            return s, e

    # === 3. 同月日范围：2026年5月1-2日 ===
    m = re.search(
        r"(?P<y>\d{4})\s*年\s*(?P<m>\d{1,2})\s*月\s*"
        r"(?P<d1>\d{1,2})\s*[-~至到]\s*(?P<d2>\d{1,2})\s*日",
        text)
    if m:
        s = _safe_date(m["y"], m["m"], m["d1"], *(t1 or (None, None)))
        e = _safe_date(m["y"], m["m"], m["d2"], *(t2 or t1 or (None, None)))
        if s and e:
            return s, e

    # === 4. 两个月日（无年份）：06月03日 ~ 06月30日 ===
    mds = re.findall(_MD_DATE.format(i="").replace("{i}", ""), text)
    # 上面 format hack 麻烦，用更简单的写法
    md_iter = list(re.finditer(r"(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*日?(?!\s*\d)", text))
    if len(md_iter) >= 2:
        a, b = md_iter[0], md_iter[1]
        s = _safe_date(default_year, a.group(1), a.group(2), *(t1 or (None, None)))
        e = _safe_date(default_year, b.group(1), b.group(2), *(t2 or t1 or (None, None)))
        if s and e:
            return s, e

    # === 5. 单个完整日期 ===
    m = re.search(_FULL_DATE.format(i=1), text)
    if m:
        s = _safe_date(m["y1"], m["m1"], m["d1"], *(t1 or (None, None)))
        if s:
            # 同一天有两个时间：start=t1, end=t2 (例如 10:00-11:30)
            e = ""
            if t1 and t2:
                e = _safe_date(m["y1"], m["m1"], m["d1"], t2[0], t2[1])
            return s, e

    # === 6. 单个月日 ===
    if md_iter:
        a = md_iter[0]
        s = _safe_date(default_year, a.group(1), a.group(2), *(t1 or (None, None)))
        if s:
            e = ""
            if t1 and t2:
                e = _safe_date(default_year, a.group(1), a.group(2), t2[0], t2[1])
            return s, e

    # === 7. 兜底：纯 ISO ===
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        s = _safe_date(m.group(1), m.group(2), m.group(3), *(t1 or (None, None)))
        if s:
            return s, ""

    # === 8. 兜底：MM-DD HH:MM (互动吧报名截止常用) ===
    m = re.search(r"\b(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})\b", text)
    if m:
        mo, da, h, mi = m.groups()
        s = _safe_date(default_year, mo, da, h, mi)
        if s:
            return s, ""
    m = re.search(r"\b(\d{1,2})-(\d{1,2})\b", text)
    if m and re.search(r"截止|至|结束|开始", text):
        mo, da = m.groups()
        s = _safe_date(default_year, mo, da)
        if s:
            return s, ""

    return "", ""


# ---------------------------------------------------------------------------
# 价格解析
# ---------------------------------------------------------------------------
# 严格判定"免费"：
#   - "免费" / "免门票" / "免票" 关键字
#   - 整段就是 "0元" (而非 "50.0 元" / "100元" 里的 "0 元")
#   - "公益免费 / 公益活动" 等明确表述
# 注意：不能用 "公益" 单独匹配，因为"公益讲座"+收费的情况存在
RE_FREE = re.compile(
    r"(?<![1-9])免费|免门票|免票|"            # 不被"半免费"误伤
    r"(?<![\d.])0\s*元(?![\d.])|"             # "0元" 独立词；防 100.0元 / 50元
    r"公益(?:活动|课程|讲座|沙龙)?\s*[，。、,.\s]?\s*免",  # 公益+免
    re.I)
# 当文本里同时出现"收费/付费/<数字>元/人"时，强制不算 free
# 关键升级: 任何 >=1 元的数字都算付费暗示（防 "0元起免费观看 实际 99 元起"）
RE_PAID_HINT = re.compile(
    r"收费|付费|"
    r"\d+\s*元\s*[/／]\s*(?:人|位|张|桌|个|把|份)|"
    r"预订金|"
    r"[1-9]\d*\s*元"                          # >=1 元的数字
)
RE_PRICE = re.compile(r"(\d+(?:\.\d+)?)")


# 在长文本里找"价格段"的关键字
_PRICE_KEYS = (
    "票价", "门票", "票务", "价格", "费用", "活动费用", "活动收费",
    "收费标准", "票价信息", "票档", "票面价", "演出票价",
)


def find_price_in_text(text: str) -> str:
    """从长文本里搜索价格段，返回原文片段（保真）。

    优先级：明确"票价/费用："前缀 > 数字+元/人 组合 > 数字范围
    """
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    # 1. 显式标签：票价：XXX
    for k in _PRICE_KEYS:
        m = re.search(
            rf"{k}\s*[：:]\s*([^。\n]{{2,150}}?)(?=\s*(?:[\u4e00-\u9fff]{{2,5}})\s*[:：]|[。\n]|$)",
            text)
        if m:
            seg = clean(m.group(1))
            # 必须含数字，否则跳过（"票价：详情见报名页"这种没用）
            if re.search(r"\d", seg) or RE_FREE.search(seg):
                return seg[:150]
    # 2. "XX元/人" 或 "VIP 380元"
    m = re.search(
        r"[\u4e00-\u9fff]{0,8}(?:[\d¥￥]+\s*(?:元|RMB))[^\n。]{0,40}",
        text)
    if m:
        seg = clean(m.group(0))
        if re.search(r"[1-9]\d*", seg):  # 必须有 >=1 的数字
            return seg[:120]
    return ""


def parse_price(text: str):
    """返回 (price_min, price_max, is_free)。

    优先级：
      1) 如果文本提到任何 ≥1 元的具体金额 → 必然不免费，从数字推断
      2) 文本只含"免费/0 元/赠票"等关键字且无付费暗示 → 免费
      3) 都没匹配 → (None, None, None)
    """
    if not text:
        return None, None, None
    text = text.replace("，", ",").strip()
    has_paid_hint = bool(RE_PAID_HINT.search(text))

    # 收集所有数字 (过滤年份等异常大数)
    nums = [float(x) for x in RE_PRICE.findall(text)
            if float(x) < 100000]
    # 保留 >= 1 元的（避免 "0.5 元" 等异常）
    nums_paid = [n for n in nums if n >= 1]

    if has_paid_hint and nums_paid:
        # 有"100元/人"这种付费暗示 → 一定收费
        return min(nums_paid), max(nums_paid), False

    if RE_FREE.search(text) and not has_paid_hint:
        return 0.0, 0.0, True

    if not nums:
        return None, None, None
    if len(nums) == 1:
        return nums[0], nums[0], nums[0] == 0
    return min(nums), max(nums), min(nums) == 0


# ---------------------------------------------------------------------------
# 文本清洗 / 城市识别
# ---------------------------------------------------------------------------
def clean(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def extract_city(text: str) -> str:
    if not text:
        return ""
    for c in ["广州", "佛山", "高明", "南海", "顺德", "禅城", "三水"]:
        if c in text:
            return c
    return ""


# 城市归一化：去 "市"、合并区/县到市
CITY_ALIAS = {
    "广州市": "广州",
    "佛山市": "佛山",
    "高明": "佛山", "高明区": "佛山",
    "南海": "佛山", "南海区": "佛山",
    "顺德": "佛山", "顺德区": "佛山",
    "禅城": "佛山", "禅城区": "佛山",
    "三水": "佛山", "三水区": "佛山",
}


def normalize_city(city: str) -> str:
    """把 '广州市' / '佛山市' / 各区名 → '广州' / '佛山'。"""
    if not city:
        return ""
    return CITY_ALIAS.get(city.strip(), city.strip())


# ---------------------------------------------------------------------------
# 统一分类体系（解决标签 overlap 和混乱）
# ---------------------------------------------------------------------------
# 11 个清晰互斥的大类
NORMALIZED_CATEGORIES = [
    "演出", "展览", "讲座沙龙", "社交聚会",
    "公益课/工作坊", "招聘求职", "教育升学",
    "美食探店", "优惠羊毛", "节庆赛事", "其他",
]

# 旧分类 → 新分类
CATEGORY_ALIAS = {
    # 演出类
    "演出": "演出",
    # 展览类
    "展览": "展览",
    # 讲座类
    "讲座": "讲座沙龙",
    "沙龙": "讲座沙龙",
    "讲座沙龙": "讲座沙龙",
    # 招聘类（合并 招聘会+宣讲会+招聘 三个）
    "招聘": "招聘求职",
    "招聘会": "招聘求职",
    "宣讲会": "招聘求职",
    "双选会": "招聘求职",
    "招聘求职": "招聘求职",
    # 教育类
    "教育": "教育升学",
    "升学": "教育升学",
    "教育升学": "教育升学",
    # 美食
    "美食": "美食探店",
    "美食探店": "美食探店",
    # 优惠
    "优惠": "优惠羊毛",
    "羊毛": "优惠羊毛",
    "优惠羊毛": "优惠羊毛",
    # 公益课/工作坊
    "公益课": "公益课/工作坊",
    "工作坊": "公益课/工作坊",
    "培训": "公益课/工作坊",
    "亲子": "公益课/工作坊",
    "公益课/工作坊": "公益课/工作坊",
    # 社交聚会
    "聚会": "社交聚会",
    "户外": "社交聚会",
    "徒步": "社交聚会",
    "社交": "社交聚会",
    "社交聚会": "社交聚会",
    # 兜底
    "活动": None,    # 走关键字推断
    "资讯": None,
    "": None,
}

# 关键字 → 分类（按优先级匹配；用在 "活动" / 空 / 未匹配 时）
# 顺序很重要：先匹配的优先级高
_CAT_KEYWORDS = [
    # 节庆赛事（优先于演出/社交，因为"龙舟赛"含赛事关键字也含户外）
    (("龙舟", "龙船", "端午", "中秋", "国庆", "春节", "元宵", "圣诞",
      "新年", "六一", "儿童节", "七夕",
      "嘉年华", "庙会", "灯会", "焰火", "烟花", "赛龙舟",
      "马拉松", "联赛", "邀请赛", "竞赛", "锦标赛", "电竞", "巡游",
      "花会", "花展", "民俗", "桂花展", "荷花节", "梅花节", "樱花节",
      "音乐节", "美食节", "啤酒节", "啤酒花园", "Fes",
      "运动会", "赛事", "FES"), "节庆赛事"),
    # 演出
    (("演唱会", "音乐会", "话剧", "脱口秀", "音乐剧", "歌剧",
      "舞剧", "舞蹈", "Livehouse", "LiveHouse", "live house",
      "音乐分享", "民谣", "爵士", "古典音乐",
      "演出", "驻演", "巡演", "演奏会", "DJ", "派对",
      "魔术", "马戏", "戏曲", "粤剧", "曲艺",
      "电影放映", "影展", "纪录片展映", "影音鉴赏",
      "Band房", "乐队"), "演出"),
    # 展览
    (("展览", "美术馆", "博物馆", "看展", "艺术展", "画展", "VR体验",
      "沉浸式", "策展", "陈列展", "摄影展", "影像展",
      "博览会", "展销会", "展会"), "展览"),
    # 招聘求职
    (("招聘会", "宣讲会", "双选会", "校招", "校园招聘", "求职", "实习",
      "招聘", "面试", "公务员", "事业单位", "选调", "校园引才"), "招聘求职"),
    # 教育升学（注意：高考/中考必须在 教育里，不在节庆）
    (("高考", "中考", "考研", "考证", "升学", "学位", "招生", "教师资格",
      "公务员考试", "执业资格", "护士资格", "司法考试", "成考",
      "MBA", "GMAT", "雅思", "托福", "夏校", "留学"), "教育升学"),
    # 美食
    (("美食地图", "美食街", "粤菜", "茶餐厅", "饭店",
      "餐厅", "小吃", "夜市", "美食", "探店", "好吃",
      "好吃的", "甜品", "下午茶", "早茶"), "美食探店"),
    # 优惠
    (("消费券", "优惠券", "免费领", "免单", "立减", "羊毛", "福利",
      "教师节福利", "618", "双11", "黑五", "白嫖", "团购"), "优惠羊毛"),
    # 公益课/工作坊
    (("公益", "志愿者", "工作坊", "亲子", "儿童", "手工",
      "DIY", "夏令营", "冬令营", "训练营", "培训", "课程", "课堂",
      "辅导班", "研学", "体验课"), "公益课/工作坊"),
    # 讲座沙龙
    (("讲座", "沙龙", "读书会", "分享会", "对谈", "Talk", "圆桌",
      "论坛", "公开课", "学术", "研讨", "Workshop",
      "演讲", "创业", "增长营", "AI重构", "AI重塑",
      "AI赋能", "新生态", "实战营", "私享会", "闭门会",
      "增长沙龙", "营销沙龙"), "讲座沙龙"),
    # 社交聚会（户外/聚会/打卡/榜单）
    (("徒步", "户外", "登山", "爬山", "天堂顶", "穿越", "露营", "飞盘",
      "桌游", "狼人杀", "剧本杀", "聚会", "交友", "约会", "搭子",
      "社交", "走读", "骑行", "夜跑", "羽毛球", "篮球", "游船", "野餐",
      "溯溪", "采摘", "踏青", "赏花", "游玩", "打卡", "旅游",
      "好去处", "好玩", "去哪里", "去哪儿", "周末去哪", "古道",
      "周末好去处", "遛娃", "亲子游", "墨石", "峰林", "古村",
      "夜市", "1日游", "2日游", "1天玩", "周末玩",
      # 公园 / 景区
      "湿地公园", "森林公园", "动物园", "植物园",
      "海岸线", "海滩", "古镇", "景区", "游记"), "社交聚会"),
]


def normalize_category(category: str, title: str = "", url: str = "") -> str:
    """统一规整分类标签。

    流程：
      1) 看 CATEGORY_ALIAS 是否有直接映射
      2) 没有/旧名='活动' → 用关键字推断
      3) 都不命中 → 返回 '其他'
    """
    mapped = CATEGORY_ALIAS.get((category or "").strip())
    if mapped:
        return mapped
    # 关键字推断
    txt = f"{title} {url}".lower()
    for keywords, cat in _CAT_KEYWORDS:
        for kw in keywords:
            if kw.lower() in txt:
                return cat
    return "其他"


# ---------------------------------------------------------------------------
# 多策略时间提取（详情页全文 + 标题 + 发布时间 兜底）
# ---------------------------------------------------------------------------
_TIME_KEYS = (
    "活动时间", "讲座时间", "演出时间", "放映时间", "展览时间", "举办时间",
    "开放时间", "活动日期", "时间", "日期", "演出日期",
)


def find_time_in_text(text: str, default_year: Optional[int] = None
                     ) -> tuple[str, str, str]:
    """从一段长文本里寻找时间信息，返回 (raw_time, start, end)。

    优先级：明确"XX时间："前缀 > 文中任意一个完整日期短语。
    """
    if not text:
        return "", "", ""
    text = text.replace("\u00a0", " ")
    # 1. 优先匹配显式标签
    STOP = (r"活动地点|活动地址|活动对象|活动名称|活动详情|活动主题|活动费用|"
            r"活动咨询|活动须知|活动嘉宾|招募对象|报名方式|报名时间|"
            r"地点|地址|场地|对象|嘉宾|费用|价格|主办|协办|承办|场次|参与|预约")
    for k in _TIME_KEYS:
        pat = (rf"{k}\s*[:：]\s*"
               rf"(.+?)(?=\s*(?:{STOP})\s*[:：]|[\n\r。；;]|$)")
        for m in re.finditer(pat, text):
            raw = clean(m.group(1))[:80]
            # 去掉尾部残留的关键词（防"活动"被吞）
            raw = re.split(r"\s+(?:活动|名称|主题)$", raw)[0].strip()
            if not raw:
                continue
            s, e = parse_time_range(raw, default_year)
            if s:
                return raw, s, e

    # 2. 无前缀，尝试在全文找任意一段时间短语（最长 60 字窗口）
    candidates = [
        # 2026年5月1日 10:00-11:30
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日(?:[（(][^()）]{0,6}[)）])?(?:\s*\d{1,2}[:点]\d{2}(?:\s*[-~至到]\s*\d{1,2}[:点]\d{2})?)?",
        # 2026年5月1-2日
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[-~至到]\s*\d{1,2}\s*日",
        # 2026年5月1日-5月5日
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*[-~至到]\s*\d{1,2}\s*月\s*\d{1,2}\s*日",
        # 2026-06-03 19:30
        r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:\s*\d{1,2}[:点]\d{2})?",
        # 5月1日 10:00
        r"\d{1,2}\s*月\s*\d{1,2}\s*日(?:\s*\d{1,2}[:点]\d{2})?",
    ]
    for pat in candidates:
        m = re.search(pat, text)
        if m:
            raw = m.group(0)
            s, e = parse_time_range(raw, default_year)
            if s:
                return raw.strip(), s, e
    return "", "", ""

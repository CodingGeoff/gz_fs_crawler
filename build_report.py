"""把 data/events.json 渲染成漂亮的单文件 HTML 看板。

设计目标（v2）：
  - **移动端友好**：顶部筛选栏可折叠（汉堡按钮）
  - **加载更快**：HTML 不再 inline 数据，从同目录 events.json 异步加载；
    首屏只渲染 30 张卡片，滚动到底再加载下一批
  - **配色更舒服**：浅色卡 + 强调色 + 状态徽章
  - **完全在沙箱 iframe 中可用**：所有 CSS 内联，无外部资源
"""
from __future__ import annotations

import json
import html
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data" / "events.json"
OUT = Path(__file__).parent / "data" / "report.html"


HTML_TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#3b5cff">
<title>广佛大学生雷达 · __COUNT__ 个活动</title>
<style>
:root {
  --bg: #f5f6fa;
  --card: #ffffff;
  --text: #1a1f36;
  --muted: #8a93a8;
  --line: #e6e9f0;
  --brand: #3b5cff;
  --brand-soft: #eaf0ff;
  --green: #14b87a;
  --orange: #ff7a45;
  --gray: #aab1c1;
  --yellow: #f7b32b;
  --radius: 12px;
  --shadow: 0 1px 3px rgba(20,30,80,.05), 0 4px 16px rgba(20,30,80,.04);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1116; --card: #181c25; --text: #e6e9f0; --muted: #8b94a8;
    --line: #232838; --brand: #5a7bff; --brand-soft: #1d2a4d;
    --shadow: 0 1px 3px rgba(0,0,0,.3), 0 6px 20px rgba(0,0,0,.2);
  }
}
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body { margin: 0; padding: 0; }
body {
  font: 14px/1.55 -apple-system, BlinkMacSystemFont, "PingFang SC",
        "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  background: var(--bg); color: var(--text);
  -webkit-font-smoothing: antialiased;
  padding: 0 16px 24px;
  max-width: 1500px; margin: 0 auto;
}

/* ============ 顶栏 ============ */
.hd {
  position: sticky; top: 0; z-index: 20;
  background: var(--bg);
  padding: 12px 0 8px;
  margin: 0 -16px 4px;
  border-bottom: 1px solid var(--line);
}
.hd-inner { padding: 0 16px; }
.hd-row {
  display: flex; align-items: center; gap: 10px;
}
.brand {
  font-size: 18px; font-weight: 700; letter-spacing: -.2px;
  color: var(--text); white-space: nowrap;
}
.brand .dot { color: var(--brand); }
.stat {
  flex: 1;
  font-size: 12px; color: var(--muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.stat b { color: var(--brand); font-weight: 600; }
.btn-toggle {
  display: none;
  background: var(--brand-soft); color: var(--brand);
  border: none; border-radius: 8px;
  padding: 6px 12px; font-size: 12px; font-weight: 600;
  cursor: pointer;
}
.btn-toggle .ico { display: inline-block; margin-right: 4px; }

/* 筛选面板 */
.filters {
  margin-top: 10px;
  display: flex; flex-direction: column; gap: 6px;
}
.fg { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.fg-label {
  font-size: 11px; color: var(--muted);
  margin-right: 2px; min-width: 36px;
}
.chip {
  padding: 4px 10px; font-size: 12px;
  border-radius: 999px; cursor: pointer;
  background: var(--card); color: var(--text);
  border: 1px solid var(--line);
  transition: all .15s;
  user-select: none; white-space: nowrap;
}
.chip:hover { border-color: var(--brand); color: var(--brand); }
.chip.on { background: var(--brand); color: #fff; border-color: var(--brand); }
.chip.on.s-today { background: var(--green); border-color: var(--green); }
.chip.on.s-archived { background: var(--gray); border-color: var(--gray); }

.q-wrap { flex: 1; min-width: 180px; max-width: 320px; position: relative; }
.q {
  width: 100%;
  padding: 7px 12px 7px 30px;
  font-size: 13px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--card); color: var(--text);
  outline: none;
}
.q:focus { border-color: var(--brand); }
.q-icon {
  position: absolute; left: 10px; top: 50%;
  transform: translateY(-50%);
  color: var(--muted); font-size: 14px; pointer-events: none;
}

/* 移动端 */
@media (max-width: 720px) {
  body { padding: 0 10px 18px; }
  .hd { margin: 0 -10px 4px; }
  .hd-inner { padding: 0 10px; }
  .btn-toggle { display: inline-block; }
  .filters { display: none; max-height: 70vh; overflow-y: auto; }
  .filters.show { display: flex; }
  .brand { font-size: 16px; }
  .q-wrap { max-width: none; }
}

/* ============ 卡片网格 ============ */
.section-tit {
  grid-column: 1/-1;
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600;
  margin: 18px 0 4px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--line);
  color: var(--muted);
}
.section-tit.today { color: var(--green); border-bottom-color: var(--green); }
.section-tit.upcoming { color: var(--brand); border-bottom-color: var(--brand); }
.section-tit.unknown { color: var(--yellow); border-bottom-color: var(--yellow); }
.section-tit .count {
  background: currentColor; color: #fff !important;
  padding: 1px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 700;
}
.section-tit.archived .count { background: var(--gray); color: #fff; }
.section-tit.today .count { background: var(--green); color: #fff; }
.section-tit.upcoming .count { background: var(--brand); color: #fff; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(255px, 1fr));
  gap: 12px;
}
@media (max-width: 480px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
}

.card {
  background: var(--card);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  display: flex; flex-direction: column;
  transition: transform .12s, box-shadow .12s;
  position: relative;
  text-decoration: none; color: inherit;
}
.card:hover { transform: translateY(-2px);
              box-shadow: 0 2px 8px rgba(20,30,80,.08), 0 12px 30px rgba(20,30,80,.08); }
.card.archived { opacity: .6; }
.card.archived:hover { opacity: 1; }

.poster {
  width: 100%; padding-top: 60%;       /* 5:3 ratio */
  background: linear-gradient(135deg, #eaf0ff 0%, #f5f6fa 100%) center/cover no-repeat;
  position: relative;
}
.poster::after {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(to bottom, transparent 50%, rgba(0,0,0,.5) 100%);
  pointer-events: none;
}
.badges-l, .badges-r {
  position: absolute; top: 6px;
  display: flex; flex-wrap: wrap; gap: 4px;
  z-index: 2; max-width: 60%;
}
.badges-l { left: 6px; }
.badges-r { right: 6px; flex-direction: row-reverse; }
.bdg {
  padding: 2px 7px; border-radius: 999px;
  font-size: 10px; font-weight: 600;
  background: rgba(0,0,0,.6); color: #fff;
  backdrop-filter: blur(4px);
  white-space: nowrap;
}
.bdg.cat { background: rgba(59,92,255,.88); }
.bdg.city { background: rgba(0,0,0,.6); }
.bdg.free { background: var(--orange); }
.bdg.paid { background: rgba(255,255,255,.85); color: #1a1f36; }
.bdg.status-today { background: var(--green); }
.bdg.status-upcoming { background: var(--brand); }
.bdg.status-archived { background: var(--gray); }
.bdg.status-unknown { background: var(--yellow); color: #1a1f36; }

.body {
  padding: 10px 12px 11px;
  flex: 1;
  display: flex; flex-direction: column;
  gap: 4px;
}
.tit {
  font-weight: 600; font-size: 13px;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2; line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 35px;
  margin-bottom: 2px;
}
.meta {
  font-size: 11.5px; color: var(--muted);
  display: flex; align-items: flex-start; gap: 4px;
  line-height: 1.4;
}
.meta .v {
  flex: 1; overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}
.meta.t .v { color: var(--brand); font-weight: 500; }
.meta.p .v { color: var(--orange); font-weight: 500; }
.foot {
  margin-top: 6px; padding-top: 6px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 10.5px; color: var(--muted);
  border-top: 1px dashed var(--line);
}

.empty {
  grid-column: 1/-1;
  text-align: center; padding: 60px 0;
  color: var(--muted); font-size: 14px;
}
.loading {
  grid-column: 1/-1;
  text-align: center; padding: 16px;
  color: var(--muted); font-size: 12px;
}

/* 滚动到底按钮 */
.fab {
  position: fixed; right: 14px; bottom: 14px;
  width: 42px; height: 42px;
  border-radius: 50%;
  background: var(--brand); color: #fff;
  border: none; box-shadow: var(--shadow);
  font-size: 18px; cursor: pointer;
  display: none; align-items: center; justify-content: center;
  z-index: 30;
}
.fab.show { display: flex; }
</style>
</head>
<body>

<div class="hd">
  <div class="hd-inner">
    <div class="hd-row">
      <div class="brand">🛸 广佛雷达<span class="dot">·</span></div>
      <div class="stat">
        共 <b id="stTotal">__COUNT__</b> · 🔥<b id="stToday">__TODAY__</b>
        · ⏰<b id="stUpcoming">__UPCOMING__</b>
        · 📦<b id="stArchived">__ARCHIVED__</b>
      </div>
      <button class="btn-toggle" id="btnToggle" aria-label="筛选">
        <span class="ico">☰</span>筛选
      </button>
    </div>
    <div class="filters" id="filters">
      <div class="fg">
        <span class="fg-label">状态</span>
        <span id="cStatus"></span>
      </div>
      <div class="fg">
        <span class="fg-label">分类</span>
        <span id="cCat"></span>
      </div>
      <div class="fg">
        <span class="fg-label">城市</span>
        <span id="cCity"></span>
      </div>
      <div class="fg">
        <span class="fg-label">站点</span>
        <span id="cSrc"></span>
      </div>
      <div class="fg">
        <div class="q-wrap">
          <span class="q-icon">🔍</span>
          <input class="q" id="q" placeholder="搜索：标题/地址/主办方/学校..." />
        </div>
      </div>
    </div>
  </div>
</div>

<div class="grid" id="grid">
  <div class="loading">📡 正在加载数据…</div>
</div>

<button class="fab" id="fab" aria-label="回到顶部">↑</button>

<script>
const STATUS_LABELS = {today:'🔥 今天/进行中', upcoming:'⏰ 即将开始',
                       unknown:'❓ 未知时间', archived:'📦 已归档'};
const STATUS_ORDER = ['today','upcoming','unknown','archived'];

let DATA = [];                           // 加载后填充
let f = { status:'', cat:'', city:'', src:'' };
let q = '';
let rendered = 0;
const PAGE_SIZE = 30;
let filterCache = null;

// ============ 加载数据：优先 inline，否则尝试 fetch ============
async function loadData() {
  // 1) 优先用 inline 数据（保证 file:// 和沙箱 iframe 都能用）
  if (window.__EVENTS__) {
    DATA = window.__EVENTS__;
    delete window.__EVENTS__;          // 释放内存
  } else {
    // 2) 兜底从 events.json 加载（需要 http server）
    try {
      const resp = await fetch('events.json');
      DATA = await resp.json();
    } catch (e) {
      document.getElementById('grid').innerHTML =
        '<div class="empty">⚠ 无法加载 events.json</div>';
      return;
    }
  }
  buildChips();
  invalidate();
}

// ============ Chip 生成 ============
function buildChips() {
  const cats = uniq(DATA.map(e => e.category));
  const cities = uniq(DATA.map(e => e.city)).filter(Boolean);
  const srcMap = {};
  DATA.forEach(e => { if (e.source) srcMap[e.source] = e.source_name; });

  // 状态
  const stCnt = count(DATA.map(e => e.status));
  const stList = [
    ['', '全部'],
    ['today', '🔥 今天 (' + (stCnt.today||0) + ')'],
    ['upcoming', '⏰ 即将 (' + (stCnt.upcoming||0) + ')'],
    ['archived', '📦 归档 (' + (stCnt.archived||0) + ')'],
    ['unknown', '❓ 未知 (' + (stCnt.unknown||0) + ')'],
  ];
  setChips('cStatus', stList, 'status', v => 's-' + v);

  setChips('cCat',
    [['','全部']].concat(cats.map(c => [c,c])),
    'cat');
  setChips('cCity',
    [['','全部']].concat(cities.map(c => [c,c])),
    'city');
  setChips('cSrc',
    [['','全部']].concat(Object.entries(srcMap).sort((a,b)=>a[1].localeCompare(b[1]))
                          .map(([code,name]) => [code, name])),
    'src');
}
function setChips(elId, items, group, extraCls) {
  const el = document.getElementById(elId);
  el.innerHTML = items.map(([val, label]) => {
    const cls = ['chip'];
    if (val === f[group]) cls.push('on');
    if (extraCls && val) cls.push(extraCls(val));
    return `<span class="${cls.join(' ')}" data-g="${group}" data-v="${esc(val)}">${esc(label)}</span>`;
  }).join('');
}

// ============ 筛选 + 分组渲染 ============
function applyFilter() {
  const ql = q.toLowerCase();
  return DATA.filter(e => {
    if (f.status && e.status !== f.status) return false;
    if (f.cat && e.category !== f.cat) return false;
    if (f.city && e.city !== f.city) return false;
    if (f.src && e.source !== f.src) return false;
    if (q) {
      const hay = (e.title+' '+e.address+' '+e.organizer+' '+e.venue+' '+e.description).toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  });
}

function invalidate() {
  filterCache = null;
  rendered = 0;
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  grid.dataset.lastStatus = '';
  delete grid.__statusCount;
  renderMore();
}

function renderMore() {
  if (filterCache === null) filterCache = applyFilter();
  const list = filterCache;
  const grid = document.getElementById('grid');

  if (list.length === 0) {
    grid.innerHTML = '<div class="empty">😶 没有符合条件的活动</div>';
    return;
  }

  // 把所有 item 按 status 排好序后 flat 渲染
  // (DATA 已经在 Python 侧 sort 过, 这里只过滤，保持顺序)
  const fragments = [];
  const next = Math.min(rendered + PAGE_SIZE, list.length);
  let lastStatus = grid.dataset.lastStatus || '';

  // 第一次渲染时插入首个分组标题
  if (rendered === 0) {
    lastStatus = '';
  }

  // 预先按 status 统计总数（在 list 范围内）
  if (!grid.__statusCount) {
    const c = {};
    list.forEach(e => { const k = e.status||'unknown'; c[k]=(c[k]||0)+1; });
    grid.__statusCount = c;
  }
  for (let i = rendered; i < next; i++) {
    const e = list[i];
    const st = e.status || 'unknown';
    if (st !== lastStatus) {
      const cnt = grid.__statusCount[st] || 0;
      fragments.push(`<div class="section-tit ${st}">${STATUS_LABELS[st] || st} <span class="count">${cnt}</span></div>`);
      lastStatus = st;
    }
    fragments.push(renderCard(e));
  }
  grid.dataset.lastStatus = lastStatus;

  // sentinel
  // 删除已有 loading
  grid.querySelectorAll('.loading').forEach(el => el.remove());
  if (next < list.length) {
    fragments.push(`<div class="loading" id="sentinel">↓ 滚动加载更多（已显示 ${next} / ${list.length}）</div>`);
  } else {
    fragments.push(`<div class="loading">✨ 已显示全部 ${list.length} 条</div>`);
  }

  grid.insertAdjacentHTML('beforeend', fragments.join(''));
  rendered = next;
  if (rendered < list.length) observeSentinel();
}

let io = null;
function observeSentinel() {
  if (io) io.disconnect();
  const sentinel = document.getElementById('sentinel');
  if (!sentinel) return;
  io = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) {
      sentinel.remove();
      renderMore();
    }
  }, { rootMargin: '400px' });
  io.observe(sentinel);
}

function renderCard(e) {
  const poster = e.poster_local || e.poster || '';
  const bg = poster ? `style="background-image:url('${poster}')"` : '';
  const stBadge = STATUS_LABELS[e.status]
    ? `<span class="bdg status-${e.status}">${STATUS_LABELS[e.status].slice(0,2)||'?'}</span>`
    : '';
  // 左上：分类 + 城市；右上：状态 + (FREE 或 价格区间)
  const priceBadge = e.is_free
    ? '<span class="bdg free">FREE</span>'
    : (e.price_min && e.price_min >= 1
        ? `<span class="bdg paid">¥${e.price_min}${e.price_max && e.price_max !== e.price_min ? '-' + e.price_max : ''}</span>`
        : '');
  return `<a class="card ${e.status||''}" href="${e.url}" target="_blank" rel="noopener">
    <div class="poster" ${bg}>
      <div class="badges-l">
        ${e.category ? `<span class="bdg cat">${esc(e.category)}</span>` : ''}
        ${e.city ? `<span class="bdg city">${esc(e.city)}</span>` : ''}
      </div>
      <div class="badges-r">
        ${stBadge}
        ${priceBadge}
      </div>
    </div>
    <div class="body">
      <div class="tit">${esc(e.title)}</div>
      ${e.start_time ? `<div class="meta t">🕒<span class="v">${esc(e.start_time)}${e.end_time && e.end_time!==e.start_time ? ' → '+esc(e.end_time):''}</span></div>` : ''}
      ${e.address ? `<div class="meta">📍<span class="v">${esc(e.address)}</span></div>` : ''}
      ${e.price && !e.is_free ? `<div class="meta p">💰<span class="v">${esc(e.price)}</span></div>` : ''}
      ${e.organizer ? `<div class="meta">🏢<span class="v">${esc(e.organizer)}</span></div>` : ''}
      <div class="foot">
        <span>${esc(e.source_name)}</span>
        <span>详情 →</span>
      </div>
    </div>
  </a>`;
}

// ============ 工具 ============
function uniq(arr) { return [...new Set(arr.filter(Boolean))].sort(); }
function count(arr) {
  const o = {};
  arr.forEach(x => { o[x] = (o[x]||0) + 1; });
  return o;
}
function esc(s) {
  return (s == null ? '' : String(s)).replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ============ 事件 ============
document.body.addEventListener('click', e => {
  const c = e.target.closest('.chip');
  if (c) {
    const g = c.dataset.g, v = c.dataset.v;
    f[g] = v;
    buildChips();   // 重新生成 chip（高亮）
    invalidate();
    return;
  }
});

document.getElementById('q').addEventListener('input', e => {
  q = e.target.value.trim();
  // 防抖
  clearTimeout(window.__qTimer);
  window.__qTimer = setTimeout(invalidate, 200);
});

document.getElementById('btnToggle').addEventListener('click', () => {
  document.getElementById('filters').classList.toggle('show');
});

// 回到顶部
const fab = document.getElementById('fab');
fab.addEventListener('click', () => window.scrollTo({top:0, behavior:'smooth'}));
window.addEventListener('scroll', () => {
  fab.classList.toggle('show', window.scrollY > 600);
}, {passive:true});

// 不直接调用 loadData()，等下面的 inline data script 注入后再触发
</script>
<!-- ============ 内联数据 ============ -->
<script id="data" type="application/json">__DATA_JSON__</script>
<script>
(function() {
  try {
    const el = document.getElementById('data');
    window.__EVENTS__ = JSON.parse(el.textContent);
    el.remove();
  } catch (e) { console.warn('inline data parse failed:', e); }
  // 延迟到下一帧让浏览器先把首屏样式绘制
  requestAnimationFrame(loadData);
})();
</script>

</body>
</html>"""


def main():
    events = json.loads(DATA.read_text(encoding="utf-8"))
    status_count = Counter(e.get("status", "unknown") for e in events)

    # 城市归一化：去掉"市"后缀，把别名合并
    CITY_NORMALIZE = {
        "广州市": "广州", "佛山市": "佛山", "禅城": "佛山", "禅城区": "佛山",
        "顺德": "佛山", "顺德区": "佛山", "南海": "佛山", "南海区": "佛山",
        "三水": "佛山", "三水区": "佛山", "高明": "佛山", "高明区": "佛山",
    }

    # 为节省 HTML 大小，drop 一些超长字段
    slim = []
    for e in events:
        e2 = {k: v for k, v in e.items()
              if k not in ("description", "extra", "raw_time",
                           "tags", "crawled_at", "sort_key", "poster_local",
                           "district", "price_min", "price_max", "uid")}
        # 城市归一化
        c = e.get("city", "")
        e2["city"] = CITY_NORMALIZE.get(c, c)
        # description 短截
        if e.get("description"):
            e2["description"] = e["description"][:120]
        slim.append(e2)
    data_json = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))

    html_out = (HTML_TPL
        .replace("__COUNT__", str(len(events)))
        .replace("__TODAY__", str(status_count.get("today", 0)))
        .replace("__UPCOMING__", str(status_count.get("upcoming", 0)))
        .replace("__ARCHIVED__", str(status_count.get("archived", 0)))
        .replace("__DATA_JSON__", data_json))
    OUT.write_text(html_out, encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"✅ HTML report → {OUT}")
    print(f"   {len(events)} events  /  size {size_kb:.0f} KB")


if __name__ == "__main__":
    main()

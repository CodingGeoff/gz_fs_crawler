/* ============================================================
   广佛活动雷达 · App Logic
   ============================================================ */

(() => {
'use strict';

// ============ Config ============
const STATUS_LABELS = {
  today: '🔥 今天/进行中',
  upcoming: '⏰ 即将开始',
  unknown: '❓ 未知时间',
  archived: '📦 已归档',
};
const STATUS_ICONS = { today: '🔥', upcoming: '⏰', unknown: '❓', archived: '📦' };
const STATUS_ORDER = ['today', 'upcoming', 'unknown', 'archived'];
const PAGE_SIZE = 36;

const CATEGORY_ICONS = {
  '讲座沙龙': '🎤', '展览': '🖼️', '演出': '🎭', '公益课/工作坊': '🎨',
  '优惠羊毛': '🎁', '美食探店': '🍜', '招聘求职': '💼', '教育升学': '📚',
  '节庆赛事': '🏆', '社交聚会': '🤝', '其他': '📌',
};

// ============ State ============
let DATA = [];
let filtered = [];
let rendered = 0;
let viewMode = 'grid';
let sortBy = 'default';
const filter = { status: '', cat: '', city: '', src: '', price: '', ctype: '' };
let query = '';
let io = null;
let statusSectionCount = {};

// ============ DOM ============
const $ = id => document.getElementById(id);
const container = $('container');
const searchInput = $('search');
const searchClear = $('searchClear');

// ============ Utils ============
const esc = s => (s == null ? '' : String(s))
  .replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// 简单 hash（与 Python md5 不需要一致，只需唯一稳定）
function hashUid(s) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h) + s.charCodeAt(i);
    h = h & h;
  }
  return 'u' + (h >>> 0).toString(36);
}

const uniq = arr => [...new Set(arr.filter(Boolean))].sort();
const countBy = arr => {
  const o = {};
  arr.forEach(x => { o[x] = (o[x] || 0) + 1; });
  return o;
};

function highlight(text, q) {
  if (!text || !q) return esc(text);
  const safe = esc(text);
  const ql = q.toLowerCase();
  const tl = text.toLowerCase();
  let result = '';
  let i = 0;
  while (i < text.length) {
    const idx = tl.indexOf(ql, i);
    if (idx === -1) {
      result += esc(text.slice(i));
      break;
    }
    result += esc(text.slice(i, idx));
    result += '<mark class="hl">' + esc(text.slice(idx, idx + q.length)) + '</mark>';
    i = idx + q.length;
  }
  return result;
}

function fmtTime(s) {
  if (!s) return '';
  return s;
}

function relTime(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T'));
  if (isNaN(d)) return s;
  const now = new Date();
  const diff = d - now;
  const day = 86400000;
  if (diff < 0) return '';
  if (diff < day && d.getDate() === now.getDate()) return '今天';
  const days = Math.round(diff / day);
  if (days === 1) return '明天';
  if (days < 7) return days + ' 天后';
  if (days < 30) return Math.round(days / 7) + ' 周后';
  return Math.round(days / 30) + ' 个月后';
}

// ============ 智能排序：今天单日 > 短时长 > 早结束 ============
function parseDate(s) {
  if (!s) return null;
  const d = new Date(s.replace(' ', 'T'));
  return isNaN(d) ? null : d;
}

function isSameDay(d1, d2) {
  return d1 && d2 && d1.getFullYear() === d2.getFullYear() &&
         d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();
}

/** 判断是否"仅今天"举办的单日活动（start 和 end 同一天且是今天） */
function isTodayOnly(e) {
  if ((e.status || 'unknown') !== 'today') return false;
  const sDt = parseDate(e.start_time);
  if (!sDt) return false;
  const now = new Date();
  if (!isSameDay(sDt, now)) return false; // 开始时间不是今天
  // 没有 end_time 或 end 和 start 同一天 → 单日活动
  if (!e.end_time) return true;
  const eDt = parseDate(e.end_time);
  if (!eDt) return true;
  return isSameDay(sDt, eDt);
}

/** 活动时长（小时），越短权重越高。
 *  无 end_time 时返回大值（视为"时长未知/很长"），避免错误地排在短时长活动之前。
 */
function durationHours(e) {
  const sDt = parseDate(e.start_time);
  if (!sDt) return 999999;
  const eDt = parseDate(e.end_time);
  if (!eDt || eDt <= sDt) return 999999;  // 无 end_time 或 end<=start → 视为很长
  return (eDt - sDt) / 3600000;
}

/** 智能比较：仅今天优先 → 活动优先于资讯 → 时长短优先 → 结束早优先 → 开始早优先 */
function smartCompare(a, b) {
  const sa = smartScore(a);
  const sb = smartScore(b);
  if (sa.statusGroup !== sb.statusGroup) return sa.statusGroup - sb.statusGroup;
  if (sa.todayOnly !== sb.todayOnly) return sb.todayOnly - sa.todayOnly; // true(1) 排前
  if (sa.isInfo !== sb.isInfo) return sa.isInfo - sb.isInfo; // event(0) 排前，info(1) 排后
  if (sa.dur !== sb.dur) return sa.dur - sb.dur;       // 时长短的排前
  if (sa.endTs !== sb.endTs) return sa.endTs - sb.endTs; // 结束早的排前
  return sa.startTs - sb.startTs;                       // 开始早的排前
}

function smartScore(e) {
  const st = e.status || 'unknown';
  const statusGroup = st === 'today' ? 1 : st === 'upcoming' ? 2 : st === 'unknown' ? 3 : 9;
  const sDt = parseDate(e.start_time);
  const eDt = parseDate(e.end_time || e.start_time);
  return {
    statusGroup,
    todayOnly: isTodayOnly(e) ? 1 : 0,
    isInfo: (e.content_type === 'info') ? 1 : 0,
    dur: durationHours(e),
    endTs: eDt ? eDt.getTime() : 9999999999999,
    startTs: sDt ? sDt.getTime() : 9999999999999,
  };
}

// ============ Data loading ============
async function loadData() {
  try {
    const resp = await fetch('data/events.json');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    DATA = await resp.json();
  } catch (e) {
    container.innerHTML = `<div class="empty"><div class="ico">⚠️</div><div class="msg">无法加载活动数据</div><div class="hint">${esc(e.message)}</div></div>`;
    return;
  }
  // Normalize city
  const CITY_NORM = {
    '广州市': '广州', '佛山市': '佛山', '禅城': '佛山', '禅城区': '佛山',
    '顺德': '佛山', '顺德区': '佛山', '南海': '佛山', '南海区': '佛山',
    '三水': '佛山', '三水区': '佛山', '高明': '佛山', '高明区': '佛山',
  };
  DATA.forEach(e => {
    e.city = CITY_NORM[e.city] || e.city || '';
    // 计算 uid（events.json 中没有此字段）
    if (!e.uid) e.uid = hashUid((e.url || '') + '|' + (e.title || ''));
  });
  buildChips();
  buildStats();
  invalidate();
}

// ============ Stats ============
function buildStats() {
  const total = DATA.length;
  const stCnt = countBy(DATA.map(e => e.status || 'unknown'));
  const todayOnlyCnt = DATA.filter(e => isTodayOnly(e)).length;
  const free = DATA.filter(e => e.is_free).length;
  const cities = uniq(DATA.map(e => e.city)).length;
  const sources = uniq(DATA.map(e => e.source)).length;
  const latest = DATA.reduce((m, e) => {
    if (!e.crawled_at) return m;
    return e.crawled_at > m ? e.crawled_at : m;
  }, '');

  $('heroStats').innerHTML = [
    ['📡', total, '活动总数'],
    ['🔥', todayOnlyCnt, '仅今天举办'],
    ['⏰', stCnt.today || 0, '今天/进行中'],
    ['📌', stCnt.upcoming || 0, '即将开始'],
    ['🎁', free, '免费活动'],
    ['🌐', sources, '数据来源'],
  ].map(([ico, num, lbl]) => `
    <div class="hero-stat">
      <div class="num">${ico} ${num}</div>
      <div class="lbl">${lbl}</div>
    </div>`).join('');

  $('headerStats').innerHTML = STATUS_ORDER.filter(s => stCnt[s]).map(s => `
    <div class="header-stat ${s}">
      <span class="dot"></span>
      <b>${stCnt[s]}</b>${STATUS_ICONS[s] || ''}
    </div>`).join('');

  $('footTotal').textContent = total;
  if (latest) {
    $('footUpdated').textContent = latest.replace('T', ' ').slice(0, 16);
  }
}

// ============ Chips ============
function buildChips() {
  const stCnt = countBy(DATA.map(e => e.status || 'unknown'));
  setChips('chipsStatus', [
    ['', '全部'],
    ['today', `🔥 今天 (${stCnt.today || 0})`],
    ['upcoming', `⏰ 即将 (${stCnt.upcoming || 0})`],
    ['unknown', `❓ 未知 (${stCnt.unknown || 0})`],
    ['archived', `📦 归档 (${stCnt.archived || 0})`],
  ], 'status', v => 'status-' + v);

  const cats = uniq(DATA.map(e => e.category));
  setChips('chipsCat',
    [['', '全部']].concat(cats.map(c => [c, (CATEGORY_ICONS[c] || '') + ' ' + c])),
    'cat');

  const cities = uniq(DATA.map(e => e.city));
  setChips('chipsCity',
    [['', '全部']].concat(cities.map(c => [c, c])),
    'city');

  const srcMap = {};
  DATA.forEach(e => { if (e.source) srcMap[e.source] = e.source_name; });
  setChips('chipsSrc',
    [['', '全部']].concat(Object.entries(srcMap).sort((a, b) => a[1].localeCompare(b[1]))
      .map(([code, name]) => [code, name])),
    'src');

  setChips('chipsPrice', [
    ['', '全部'],
    ['free', '🎁 免费'],
    ['paid', '💰 付费'],
  ], 'price');

  const evCnt = DATA.filter(e => e.content_type !== 'info').length;
  const infoCnt = DATA.length - evCnt;
  setChips('chipsCtype', [
    ['', '全部'],
    ['event', `🎫 活动 (${evCnt})`],
    ['info', `📰 资讯 (${infoCnt})`],
  ], 'ctype');
}

function setChips(elId, items, group, extraCls) {
  const el = $(elId);
  el.innerHTML = items.map(([val, label]) => {
    const cls = ['chip'];
    if (val === filter[group]) cls.push('active');
    if (extraCls && val) cls.push(extraCls(val));
    return `<span class="${cls.join(' ')}" data-g="${group}" data-v="${esc(val)}">${esc(label)}</span>`;
  }).join('');
}

// ============ Filter + Sort ============
function applyFilter() {
  const ql = query.toLowerCase();
  let list = DATA.filter(e => {
    if (filter.status && (e.status || 'unknown') !== filter.status) return false;
    if (filter.cat && e.category !== filter.cat) return false;
    if (filter.city && e.city !== filter.city) return false;
    if (filter.src && e.source !== filter.src) return false;
    if (filter.price === 'free' && !e.is_free) return false;
    if (filter.price === 'paid' && e.is_free) return false;
    if (filter.ctype === 'event' && e.content_type === 'info') return false;
    if (filter.ctype === 'info' && e.content_type !== 'info') return false;
    if (ql) {
      const hay = (e.title + ' ' + e.address + ' ' + e.organizer + ' ' +
                   e.venue + ' ' + e.description + ' ' + (e.source_name || '')).toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  });

  // Sort
  if (sortBy === 'time-asc') {
    list.sort((a, b) => (a.sort_key || '9_').localeCompare(b.sort_key || '9_'));
  } else if (sortBy === 'time-desc') {
    list.sort((a, b) => (b.sort_key || '0_').localeCompare(a.sort_key || '0_'));
  } else if (sortBy === 'price-asc') {
    list.sort((a, b) => {
      if (a.is_free && !b.is_free) return -1;
      if (!a.is_free && b.is_free) return 1;
      return (a.price_min || 999) - (b.price_min || 999);
    });
  } else if (sortBy === 'title') {
    list.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
  } else {
    // 默认智能排序：仅今天 > 短时长 > 早结束 > 早开始
    list.sort(smartCompare);
  }

  return list;
}

function invalidate() {
  filtered = applyFilter();
  rendered = 0;
  statusSectionCount = countBy(filtered.map(e => e.status || 'unknown'));
  container.innerHTML = '';
  container.className = viewMode === 'list' ? 'list' : 'grid';
  container.dataset.lastStatus = '';
  renderMore();
}

// ============ Render ============
function renderMore() {
  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty"><div class="ico">😶</div><div class="msg">没有符合条件的活动</div><div class="hint">试试调整筛选条件或清空搜索</div></div>`;
    return;
  }

  const next = Math.min(rendered + PAGE_SIZE, filtered.length);
  const frags = [];
  let lastStatus = container.dataset.lastStatus || '';

  for (let i = rendered; i < next; i++) {
    const e = filtered[i];
    const st = e.status || 'unknown';
    if (st !== lastStatus) {
      const cnt = statusSectionCount[st] || 0;
      frags.push(`<div class="section-head ${st}">
        <span class="icon">${STATUS_ICONS[st] || ''}</span>
        <span class="title">${(STATUS_LABELS[st] || st).replace(/^[^\u4e00-\u9fa5a-zA-Z]+/, '').trim()}</span>
        <span class="count">${cnt}</span>
      </div>`);
      lastStatus = st;
    }
    frags.push(renderCard(e));
  }
  container.dataset.lastStatus = lastStatus;

  // Remove old sentinel
  container.querySelectorAll('.sentinel').forEach(el => el.remove());

  if (next < filtered.length) {
    frags.push(`<div class="sentinel" id="sentinel">↓ 滚动加载更多（已显示 ${next} / ${filtered.length}）</div>`);
  } else {
    frags.push(`<div class="sentinel">✨ 已显示全部 ${filtered.length} 条活动</div>`);
  }

  container.insertAdjacentHTML('beforeend', frags.join(''));
  rendered = next;
  if (rendered < filtered.length) observeSentinel();
}

function renderCard(e) {
  const poster = e.poster_local || e.poster || '';
  const st = e.status || 'unknown';
  const todayOnly = isTodayOnly(e);
  const isInfo = e.content_type === 'info';
  const stBadge = STATUS_LABELS[st]
    ? `<span class="badge status-${st}">${STATUS_ICONS[st]}</span>` : '';
  const todayOnlyBadge = todayOnly ? '<span class="badge today-only-badge">🔥仅今天</span>' : '';
  const infoBadge = isInfo ? '<span class="badge info-badge">📰资讯</span>' : '';
  const priceBadge = e.is_free
    ? '<span class="badge free">FREE</span>'
    : (e.price_min && e.price_min >= 1
        ? `<span class="badge paid">¥${e.price_min}${e.price_max && e.price_max !== e.price_min ? '-' + e.price_max : ''}</span>`
        : '');
  const catIcon = CATEGORY_ICONS[e.category] || '';
  const rel = relTime(e.start_time);
  const relBadge = rel ? `<span class="badge" style="background:rgba(245,158,11,0.9)">${esc(rel)}</span>` : '';

  const timeStr = e.start_time
    ? `${esc(e.start_time)}${e.end_time && e.end_time !== e.start_time ? ' → ' + esc(e.end_time) : ''}`
    : (e.raw_time ? esc(e.raw_time) : '');

  const posterImg = poster
    ? `<img src="${esc(poster)}" alt="${esc(e.title)}" loading="lazy" onerror="this.classList.add('broken')">`
    : '';

  const cardCls = ['card', st];
  if (todayOnly) cardCls.push('today-only');
  if (isInfo) cardCls.push('info-card');

  return `<div class="${cardCls.join(' ')}" data-uid="${esc(e.uid)}" style="animation-delay:${Math.min((rendered % PAGE_SIZE) * 20, 400)}ms">
    <div class="card-poster">
      ${posterImg}
      <div class="card-badges">
        <div class="badge-group left">
          ${e.category ? `<span class="badge cat">${esc(catIcon)} ${esc(e.category)}</span>` : ''}
          ${e.city ? `<span class="badge city">${esc(e.city)}</span>` : ''}
        </div>
        <div class="badge-group">
          ${todayOnlyBadge}
          ${infoBadge}
          ${relBadge}
          ${stBadge}
          ${priceBadge}
        </div>
      </div>
    </div>
    <div class="card-body">
      <div class="card-title">${highlight(e.title, query)}</div>
      ${timeStr ? `<div class="card-meta time"><span class="ico">🕒</span><span class="val">${esc(timeStr)}</span></div>` : ''}
      ${e.address ? `<div class="card-meta"><span class="ico">📍</span><span class="val">${highlight(e.address, query)}</span></div>` : ''}
      ${e.organizer ? `<div class="card-meta"><span class="ico">🏢</span><span class="val">${highlight(e.organizer, query)}</span></div>` : ''}
      <div class="card-foot">
        <span class="card-source">🌐 ${esc(e.source_name)}</span>
        <span class="card-arrow">详情 →</span>
      </div>
    </div>
  </div>`;
}

function observeSentinel() {
  if (io) io.disconnect();
  const sentinel = $('sentinel');
  if (!sentinel) return;
  io = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) {
      sentinel.remove();
      renderMore();
    }
  }, { rootMargin: '500px' });
  io.observe(sentinel);
}

// ============ Modal ============
function openModal(uid) {
  const e = DATA.find(x => x.uid === uid);
  if (!e) return;
  const poster = e.poster_local || e.poster || '';
  const posterEl = $('modalPoster');
  // 清除旧 img
  posterEl.querySelectorAll('img').forEach(i => i.remove());
  posterEl.style.backgroundImage = '';
  if (poster) {
    const img = document.createElement('img');
    img.src = poster;
    img.alt = e.title || '';
    img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;';
    img.onerror = () => { img.remove(); posterEl.style.background = 'var(--brand-soft)'; };
    posterEl.appendChild(img);
  } else {
    posterEl.style.background = 'var(--brand-soft)';
  }
  const st = e.status || 'unknown';
  const todayOnly = isTodayOnly(e);
  const isInfo = e.content_type === 'info';
  const timeStr = e.start_time
    ? `${esc(e.start_time)}${e.end_time && e.end_time !== e.start_time ? ' → ' + esc(e.end_time) : ''}`
    : (e.raw_time ? esc(e.raw_time) : '未知');
  const priceStr = e.is_free ? '🎁 免费' : (e.price || (e.price_min ? `¥${e.price_min}` : '未知'));
  $('modalBody').innerHTML = `
    <div class="modal-badges">
      ${todayOnly ? '<span class="badge today-only-badge">🔥仅今天举办</span>' : ''}
      ${isInfo ? '<span class="badge info-badge">📰 资讯/攻略</span>' : ''}
      ${e.category ? `<span class="badge cat">${esc((CATEGORY_ICONS[e.category] || '') + ' ' + e.category)}</span>` : ''}
      ${e.city ? `<span class="badge city">${esc(e.city)}</span>` : ''}
      <span class="badge status-${st}">${STATUS_ICONS[st]} ${(STATUS_LABELS[st] || '').replace(/^[^\u4e00-\u9fa5a-zA-Z]+/, '').trim()}</span>
      ${e.is_free ? '<span class="badge free">FREE</span>' : ''}
    </div>
    <h2 class="modal-title">${esc(e.title)}</h2>
    <div class="modal-info">
      <div class="modal-info-row">
        <div class="ico">🕒</div>
        <div><div class="lbl">时间</div><div class="val">${timeStr}</div></div>
      </div>
      ${e.venue || e.address ? `<div class="modal-info-row">
        <div class="ico">📍</div>
        <div><div class="lbl">地点</div><div class="val">${esc([e.venue, e.address].filter(Boolean).join(' · '))}</div></div>
      </div>` : ''}
      <div class="modal-info-row">
        <div class="ico">💰</div>
        <div><div class="lbl">价格</div><div class="val">${esc(priceStr)}</div></div>
      </div>
      ${e.organizer ? `<div class="modal-info-row">
        <div class="ico">🏢</div>
        <div><div class="lbl">主办方</div><div class="val">${esc(e.organizer)}</div></div>
      </div>` : ''}
      <div class="modal-info-row">
        <div class="ico">🌐</div>
        <div><div class="lbl">来源</div><div class="val">${esc(e.source_name)}</div></div>
      </div>
      ${e.tags && e.tags.length ? `<div class="modal-info-row">
        <div class="ico">🏷️</div>
        <div><div class="lbl">标签</div><div class="val">${esc(e.tags.join(' · '))}</div></div>
      </div>` : ''}
    </div>
    ${e.description ? `<div class="modal-desc">${esc(e.description)}</div>` : ''}
    <div class="modal-actions">
      ${e.url ? `<a class="btn-primary" href="${esc(e.url)}" target="_blank" rel="noopener">🔗 查看原页面 →</a>` : '<span class="btn-primary" style="opacity:0.5;cursor:default">🔗 暂无原页面链接</span>'}
    </div>
  `;
  $('modalOverlay').classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  $('modalOverlay').classList.remove('show');
  document.body.style.overflow = '';
}

// ============ Theme ============
function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
    $('themeToggle').textContent = saved === 'dark' ? '☀️' : '🌙';
  }
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const isDark = cur === 'dark' || (!cur && matchMedia('(prefers-color-scheme: dark)').matches);
  const next = isDark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  $('themeToggle').textContent = next === 'dark' ? '☀️' : '🌙';
}

// ============ Events ============
document.body.addEventListener('click', e => {
  const chip = e.target.closest('.chip');
  if (chip) {
    const g = chip.dataset.g, v = chip.dataset.v;
    filter[g] = v;
    buildChips();
    invalidate();
    return;
  }
  const card = e.target.closest('.card');
  if (card) {
    openModal(card.dataset.uid);
    return;
  }
});

searchInput.addEventListener('input', e => {
  query = e.target.value.trim();
  searchClear.classList.toggle('show', query.length > 0);
  clearTimeout(window.__qTimer);
  window.__qTimer = setTimeout(invalidate, 200);
});

searchClear.addEventListener('click', () => {
  searchInput.value = '';
  query = '';
  searchClear.classList.remove('show');
  invalidate();
  searchInput.focus();
});

$('sortSelect').addEventListener('change', e => {
  sortBy = e.target.value;
  invalidate();
});

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    viewMode = btn.dataset.view;
    container.className = viewMode === 'list' ? 'list' : 'grid';
  });
});

$('filterToggle').addEventListener('click', () => {
  const fg = $('filterGrid');
  const btn = $('filterToggle');
  fg.classList.toggle('show');
  btn.classList.toggle('active');
  btn.textContent = fg.classList.contains('show') ? '✕ 收起' : '☰ 筛选';
});

$('themeToggle').addEventListener('click', toggleTheme);

$('modalClose').addEventListener('click', closeModal);
$('modalOverlay').addEventListener('click', e => {
  if (e.target === $('modalOverlay')) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// FAB
const fab = $('fab');
window.addEventListener('scroll', () => {
  fab.classList.toggle('show', window.scrollY > 600);
  $('header').classList.toggle('scrolled', window.scrollY > 10);
}, { passive: true });
fab.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

// ============ Init ============
initTheme();
loadData();

})();

/* Giao dien vnports: goi API chay job, hoi tien do va hien thi ket qua. */
'use strict';

const KIND_LABELS = {
  port_authority: 'Cảng vụ hàng hải (1–3 ngày, chính thức)',
  terminal: 'Terminal / ePort (7–14 ngày)',
  ais: 'Theo dõi AIS (1–7 ngày)',
  carrier: 'Lịch hãng tàu (14–30 ngày)',
};

const el = (id) => document.getElementById(id);
const MAX_RENDER = 300;   // vuot qua thi chi ve phan dau, tranh treo trinh duyet
const state = { rows: [], jobId: null, timer: null, sortKey: 'eta', sortAsc: true };

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* body rỗng */ }
    throw new Error(detail);
  }
  return response.json();
}

/* ---------- khởi tạo form từ /api/config ---------- */

async function loadConfig() {
  const config = await api('/api/config');
  if (config.demo_default) {
    el('demoBadge').hidden = false;
    el('demoMode').checked = true;
  }

  const counts = {};
  config.sources.forEach((source) => {
    counts[source.kind] = (counts[source.kind] || 0) + 1;
  });
  el('kinds').innerHTML = Object.entries(KIND_LABELS).map(([kind, label]) => `
    <label><input type="checkbox" name="kind" value="${kind}" checked>
      <span>${label}</span><span class="count-tag">${counts[kind] || 0}</span></label>`).join('');

  el('ports').innerHTML = config.ports
    .map((port) => `<option value="${port.key}">${port.name_vi || port.name}</option>`).join('');
  el('portFilter').innerHTML = '<option value="">Mọi cảng</option>' +
    config.ports.map((port) => `<option value="${port.name}">${port.name_vi || port.name}</option>`).join('');
  el('kindFilter').innerHTML = '<option value="">Mọi loại nguồn</option>' +
    Object.keys(KIND_LABELS).map((kind) => `<option value="${kind}">${KIND_LABELS[kind]}</option>`).join('');
}

function readParams() {
  const kinds = [...document.querySelectorAll('input[name=kind]:checked')].map((i) => i.value);
  const ports = [...el('ports').selectedOptions].map((o) => o.value);
  return {
    ports: ports.length ? ports : ['all'],
    kinds: kinds.length ? kinds : ['all'],
    sources: ['all'],
    days: Number(el('days').value),
    from_days: Number(el('fromDays').value),
    keep_no_eta: el('keepNoEta').checked,
    demo: el('demoMode').checked,
  };
}

/* ---------- chạy job và theo dõi tiến độ ---------- */

async function runJob() {
  const params = readParams();
  if (!params.kinds.length) { alert('Chọn ít nhất một loại nguồn'); return; }
  el('runBtn').disabled = true;
  el('runBtn').textContent = 'Đang chạy…';
  el('cancelBtn').hidden = false;
  el('progressWrap').hidden = false;
  el('errorBox').hidden = true;
  el('log').textContent = '';

  try {
    const job = await api('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    state.jobId = job.id;
    pollJob();
  } catch (error) {
    showError('Không tạo được job: ' + error.message);
    finishRun();
  }
}

function pollJob() {
  clearInterval(state.timer);
  state.timer = setInterval(async () => {
    try {
      const job = await api(`/api/jobs/${state.jobId}?logs=60`);
      renderProgress(job);
      if (['done', 'error', 'cancelled'].includes(job.status)) {
        clearInterval(state.timer);
        finishRun();
        if (job.status === 'done') await loadResults(job);
        else showError(job.message || 'Job kết thúc với trạng thái ' + job.status);
        if (job.errors && job.errors.length) showError(job.errors.join('\n'), true);
        loadJobList();
      }
    } catch (error) {
      clearInterval(state.timer);
      finishRun();
      showError('Mất kết nối tới máy chủ: ' + error.message);
    }
  }, 800);
}

function renderProgress(job) {
  el('progressBar').style.width = job.progress + '%';
  el('progressText').textContent =
    `${job.done_sources}/${job.total_sources} nguồn` +
    (job.current_source ? ` · đang chạy ${job.current_source}` : '') +
    (job.status === 'done' ? ` · ${job.message}` : '');
  el('log').textContent = (job.logs || []).join('\n');
  el('log').scrollTop = el('log').scrollHeight;
}

function finishRun() {
  el('runBtn').disabled = false;
  el('runBtn').textContent = 'Chạy thu thập';
  el('cancelBtn').hidden = true;
}

async function cancelJob() {
  if (state.jobId) await api(`/api/jobs/${state.jobId}/cancel`, { method: 'POST' });
}

/* ---------- kết quả ---------- */

async function loadResults(job) {
  const data = await api(`/api/jobs/${state.jobId}/results`);
  state.rows = data.rows;
  el('csvLink').href = `/api/jobs/${state.jobId}/results.csv`;
  el('csvLink').hidden = data.rows.length === 0;
  renderStats(job);
  renderTable();
}

function renderStats(job) {
  const stats = job.stats || {};
  const ports = Object.keys(stats.by_port || {}).length;
  const sources = Object.keys(stats.by_source || {}).length;
  const window = stats.window_start && stats.window_end
    ? `${fmtDate(stats.window_start)} → ${fmtDate(stats.window_end)}` : '—';
  el('stats').innerHTML = `
    <div class="stat"><b>${stats.total ?? 0}</b><span>tàu trong cửa sổ</span></div>
    <div class="stat"><b>${ports}</b><span>cảng</span></div>
    <div class="stat"><b>${sources}</b><span>nguồn có dữ liệu</span></div>
    <div class="stat"><b>${stats.raw_count ?? 0} → ${stats.merged_count ?? 0}</b><span>thô → sau gộp trùng</span></div>
    <div class="stat"><b style="font-size:13px">${window}</b><span>cửa sổ ETA</span></div>`;
}

function fmtDate(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
}

function fmtEta(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  return date.toLocaleString('vi-VN',
    { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function countdown(iso) {
  if (!iso) return { text: '—', hours: Infinity };
  const hours = (new Date(iso) - Date.now()) / 3.6e6;
  if (hours < 0) return { text: 'đã tới', hours };
  if (hours < 48) return { text: `${Math.round(hours)} giờ`, hours };
  return { text: `${Math.round(hours / 24)} ngày`, hours };
}

function visibleRows() {
  const query = el('search').value.trim().toLowerCase();
  const port = el('portFilter').value;
  const kind = el('kindFilter').value;
  let rows = state.rows.filter((row) => {
    if (port && row.port_name !== port) return false;
    if (kind && row.source_kind !== kind) return false;
    if (!query) return true;
    return ['vessel_name', 'imo', 'port_name', 'agent', 'from_port', 'flag', 'berth', 'source']
      .some((key) => String(row[key] || '').toLowerCase().includes(query));
  });
  const key = state.sortKey;
  rows.sort((a, b) => {
    let x = key === 'countdown' ? a.eta : a[key];
    let y = key === 'countdown' ? b.eta : b[key];
    x = x === null || x === undefined ? '' : x;
    y = y === null || y === undefined ? '' : y;
    return (x > y ? 1 : x < y ? -1 : 0) * (state.sortAsc ? 1 : -1);
  });
  return rows;
}

function renderTable() {
  const rows = visibleRows();
  el('resultTable').hidden = rows.length === 0;
  el('emptyState').hidden = rows.length > 0;
  if (!rows.length) {
    el('rowNote').hidden = true;
    el('emptyState').innerHTML = state.rows.length
      ? '<p>Không có dòng nào khớp bộ lọc.</p>'
      : '<p>Job chạy xong nhưng không nguồn nào trả về dữ liệu. Xem nhật ký bên trái.</p>';
    return;
  }
  const shown = rows.slice(0, MAX_RENDER);
  el('rowNote').hidden = rows.length <= MAX_RENDER;
  el('rowNote').textContent =
    `Đang hiển thị ${shown.length}/${rows.length} dòng — lọc thêm hoặc tải CSV để xem đầy đủ.`;
  el('resultBody').innerHTML = shown.map((row) => {
    const left = countdown(row.eta);
    const urgency = left.hours < 24 ? 'soon' : left.hours < 72 ? 'mid' : '';
    const merged = (row.merged_sources || []).length
      ? `<span class="merged" title="${row.merged_sources.join(', ')}">+${row.merged_sources.length}</span>` : '';
    return `<tr>
      <td class="num">${fmtEta(row.eta)}</td>
      <td class="num ${urgency}">${left.text}</td>
      <td class="ship">${esc(row.vessel_name)}</td>
      <td class="num">${esc(row.imo) || '—'}</td>
      <td>${esc(row.flag) || '—'}</td>
      <td>${esc(row.port_name) || '—'}</td>
      <td>${esc(row.berth) || '—'}</td>
      <td>${esc(row.from_port) || '—'}</td>
      <td>${esc(row.agent) || '—'}</td>
      <td><span class="pill ${row.source_kind}">${esc(row.source)}</span>${merged}</td>
    </tr>`;
  }).join('');
}

function esc(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function showError(text, append) {
  const box = el('errorBox');
  box.hidden = false;
  box.textContent = append && box.textContent ? box.textContent + '\n' + text : text;
}

async function loadJobList() {
  const jobs = await api('/api/jobs');
  el('jobList').innerHTML = jobs.map((job) => `
    <li data-id="${job.id}">
      <span>${new Date(job.created_at).toLocaleTimeString('vi-VN')} · ${job.status}</span>
      <span>${job.result_count} tàu</span>
    </li>`).join('') || '<li>Chưa có lần chạy nào</li>';
}

/* ---------- gắn sự kiện ---------- */

el('runBtn').addEventListener('click', runJob);
el('cancelBtn').addEventListener('click', cancelJob);
el('search').addEventListener('input', renderTable);
el('portFilter').addEventListener('change', renderTable);
el('kindFilter').addEventListener('change', renderTable);
document.querySelectorAll('th[data-sort]').forEach((th) => {
  th.addEventListener('click', () => {
    const key = th.dataset.sort;
    state.sortAsc = state.sortKey === key ? !state.sortAsc : true;
    state.sortKey = key;
    renderTable();
  });
});
el('jobList').addEventListener('click', async (event) => {
  const item = event.target.closest('li[data-id]');
  if (!item) return;
  state.jobId = item.dataset.id;
  const job = await api(`/api/jobs/${state.jobId}?logs=60`);
  renderProgress(job);
  if (job.status === 'done') await loadResults(job);
});

loadConfig().then(loadJobList).catch((error) => showError('Không tải được cấu hình: ' + error.message));

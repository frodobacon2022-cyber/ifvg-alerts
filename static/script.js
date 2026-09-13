// ============================================================
// Ambient mouse-reactive glow
// ============================================================
let glowRaf = null;
document.addEventListener('mousemove', (e) => {
  if (glowRaf) return;
  glowRaf = requestAnimationFrame(() => {
    document.documentElement.style.setProperty('--mx', e.clientX + 'px');
    document.documentElement.style.setProperty('--my', e.clientY + 'px');
    glowRaf = null;
  });
});

// ============================================================
// 3D tilt-on-hover for cards (event delegation so it works on
// dynamically re-rendered content without re-attaching listeners)
// ============================================================
const TILT_SELECTOR = '.tracker-card, .account-card, .stat-card, .goal-card, .news-link-card, .tilt-card';
let tiltRaf = null;
document.addEventListener('mousemove', (e) => {
  if (tiltRaf) return;
  tiltRaf = requestAnimationFrame(() => {
    const hovered = e.target.closest ? e.target.closest(TILT_SELECTOR) : null;
    document.querySelectorAll(TILT_SELECTOR).forEach(card => {
      if (card !== hovered) card.style.transform = '';
    });
    if (hovered) {
      const r = hovered.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      hovered.style.transform = `perspective(600px) rotateX(${-y * 6}deg) rotateY(${x * 6}deg) translateY(-2px)`;
    }
    tiltRaf = null;
  });
});

// ============================================================
// Tabs
// ============================================================
const tabs = document.querySelectorAll('.tab');
const panels = {
  dashboard: document.getElementById('tab-dashboard'),
  records: document.getElementById('tab-records'),
};

function loadDashboardPage() {
  loadTracker();
  loadAccounts();
  loadCalendar();
  loadPsychology();
  loadGoals();
  loadStats();
}

function loadRecordsPage() {
  loadTrades();
  loadAlertHistory();
}

const tabLoaders = {
  dashboard: loadDashboardPage,
  records: loadRecordsPage,
};

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    Object.values(panels).forEach(p => p.classList.add('hidden'));
    panels[tab.dataset.tab].classList.remove('hidden');
    if (tabLoaders[tab.dataset.tab]) tabLoaders[tab.dataset.tab]();
  });
});

// ============================================================
// Helpers
// ============================================================
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function fmtNum(n) {
  return (n === null || n === undefined || n === '') ? '—' : n;
}

function fmtMoney(n) {
  if (n === null || n === undefined || n === '') return '—';
  const num = Number(n);
  return (num < 0 ? '-$' : '$') + Math.abs(num).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diffMs = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function todayStr() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

// ============================================================
// Setup Tracker (also feeds Briefing tab)
// ============================================================
async function fetchLatestAlertsBySymbol() {
  const res = await fetch('/api/alerts?limit=200');
  const alerts = await res.json();
  const latest = {};
  alerts.forEach(a => {
    const key = `${a.symbol}__${a.timeframe}`;
    if (!latest[key] || a.id > latest[key].id) latest[key] = a;
  });
  return { alerts, latest: Object.values(latest) };
}

function renderTrackerGrid(container, latestAlerts) {
  if (!latestAlerts.length) {
    container.innerHTML = '<div class="empty-state">No alerts received yet. Once your TradingView alert fires, symbols will appear here.</div>';
    return;
  }
  container.innerHTML = latestAlerts.map(a => {
    const count = (a.reasons || []).length;
    let stateClass = 'state-none';
    if (count >= 4) stateClass = 'state-full';
    else if (count >= 2) stateClass = 'state-forming';
    return `
      <div class="tracker-card ${stateClass}">
        <div>
          <span class="tracker-symbol">${escapeHtml(a.symbol)}</span>
          <span class="tracker-tf">${escapeHtml(a.timeframe || '')}</span>
        </div>
        <div class="tracker-score">${count}/5</div>
        <div class="tracker-direction">${escapeHtml(a.direction || '')} · ${timeAgo(a.received_at)}</div>
      </div>
    `;
  }).join('');
}

async function loadTracker() {
  const { latest } = await fetchLatestAlertsBySymbol();
  renderTrackerGrid(document.getElementById('tracker-grid'), latest);
}

// ============================================================
// Alert History
// ============================================================
async function loadAlertHistory() {
  const res = await fetch('/api/alerts?limit=200');
  const alerts = await res.json();
  const tbody = document.getElementById('alerts-tbody');

  if (!alerts.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No alerts logged yet.</td></tr>';
    return;
  }

  tbody.innerHTML = alerts.map(a => `
    <tr>
      <td>${formatTime(a.received_at)}</td>
      <td>${escapeHtml(a.symbol)}</td>
      <td>${escapeHtml(a.timeframe || '')}</td>
      <td>${escapeHtml(a.direction || '')}</td>
      <td>${(a.reasons || []).length}/5</td>
      <td>
        <select class="taken-select" data-id="${a.id}">
          <option value="" ${a.taken === null ? 'selected' : ''}>—</option>
          <option value="1" ${a.taken === 1 ? 'selected' : ''}>Yes</option>
          <option value="0" ${a.taken === 0 ? 'selected' : ''}>No</option>
        </select>
      </td>
      <td>${escapeHtml(a.outcome_note || '')}</td>
    </tr>
  `).join('');

  document.querySelectorAll('.taken-select').forEach(sel => {
    sel.addEventListener('change', async (e) => {
      const id = e.target.dataset.id;
      const val = e.target.value === '' ? null : parseInt(e.target.value);
      await fetch(`/api/alerts/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taken: val, outcome_note: null }),
      });
    });
  });
}

// ============================================================
// Trade Journal
// ============================================================
async function loadTrades() {
  const res = await fetch('/api/trades');
  const trades = await res.json();
  const tbody = document.getElementById('trades-tbody');

  if (!trades.length) {
    tbody.innerHTML = '<tr><td colspan="13" class="empty-state">No trades logged yet.</td></tr>';
    return;
  }

  tbody.innerHTML = trades.map(t => {
    const condCount = ['cond_htf_trend','cond_liquidity_sweep','cond_killzone','cond_smt_divergence','cond_clean_move']
      .filter(k => t[k]).length;
    const resultClass = t.result ? `result-${t.result}` : '';
    return `
      <tr>
        <td>${formatTime(t.created_at)}</td>
        <td>${escapeHtml(t.symbol)}</td>
        <td>${escapeHtml(t.direction || '')}</td>
        <td>${escapeHtml(t.session || '')}</td>
        <td>${fmtNum(t.entry_price)}</td>
        <td>${fmtNum(t.stop_price)}</td>
        <td>${fmtNum(t.target_price)}</td>
        <td>${fmtNum(t.exit_price)}</td>
        <td>${fmtNum(t.contracts)}</td>
        <td class="${resultClass}">${fmtNum(t.pnl)}</td>
        <td>${condCount}/5</td>
        <td class="${resultClass}">${escapeHtml(t.result || '')}</td>
        <td><button class="btn-secondary delete-trade" data-id="${t.id}">Del</button></td>
      </tr>
    `;
  }).join('');

  document.querySelectorAll('.delete-trade').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.target.dataset.id;
      if (!confirm('Delete this trade?')) return;
      await fetch(`/api/trades/${id}`, { method: 'DELETE' });
      loadTrades();
    });
  });
}

const tradeModal = document.getElementById('trade-modal');
document.getElementById('new-trade-btn').addEventListener('click', () => tradeModal.classList.remove('hidden'));
document.getElementById('modal-close').addEventListener('click', () => tradeModal.classList.add('hidden'));
document.getElementById('cancel-trade').addEventListener('click', () => tradeModal.classList.add('hidden'));

document.getElementById('trade-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  ['cond_htf_trend','cond_liquidity_sweep','cond_killzone','cond_smt_divergence','cond_clean_move'].forEach(k => {
    data[k] = form.querySelector(`[name="${k}"]`).checked ? 1 : 0;
  });
  await fetch('/api/trades', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  form.reset();
  tradeModal.classList.add('hidden');
  loadTrades();
});

// ---------- Tradovate CSV Import ----------
const importBtn = document.getElementById('import-btn');
const importFileInput = document.getElementById('import-file-input');
const importStatus = document.getElementById('import-status');

importBtn.addEventListener('click', () => importFileInput.click());

importFileInput.addEventListener('change', async () => {
  const file = importFileInput.files[0];
  if (!file) return;

  importStatus.innerHTML = '<p class="panel-note">Importing…</p>';
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/import/tradovate', { method: 'POST', body: formData });
    const result = await res.json();
    let msg = `<p class="panel-note">Imported ${result.imported} trade(s).`;
    if (result.skipped_duplicates) msg += ` Skipped ${result.skipped_duplicates} already-imported trade(s).`;
    msg += '</p>';
    if (result.warnings && result.warnings.length) {
      msg += '<ul>' + result.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('') + '</ul>';
    }
    importStatus.innerHTML = msg;
    loadTrades();
  } catch (err) {
    importStatus.innerHTML = '<p class="panel-note">Import failed. Check the file is a valid Tradovate CSV export and try again.</p>';
  }
  importFileInput.value = '';
});

// ============================================================
// Active Trade Management calculator
// ============================================================
const gateChecks = document.querySelectorAll('.gate-check');
const calcResults = document.getElementById('calc-results');
const calcGateMsg = document.getElementById('calc-gate-msg');

function allGatesChecked() {
  return Array.from(gateChecks).every(c => c.checked);
}

function updateGateState() {
  if (allGatesChecked()) {
    calcResults.classList.remove('hidden');
    calcGateMsg.classList.add('hidden');
  } else {
    calcResults.classList.add('hidden');
    calcGateMsg.classList.remove('hidden');
  }
  runCalculator();
}

gateChecks.forEach(c => c.addEventListener('change', updateGateState));

function runCalculator() {
  if (!allGatesChecked()) return;

  const direction = document.getElementById('calc-direction').value;
  const entry = parseFloat(document.getElementById('calc-entry').value);
  const stop = parseFloat(document.getElementById('calc-stop').value);
  const target = parseFloat(document.getElementById('calc-target').value);
  const pointValue = parseFloat(document.getElementById('calc-point-value').value);
  const riskDollars = parseFloat(document.getElementById('calc-risk-dollars').value);

  const breakevenEl = document.getElementById('calc-breakeven');
  const rrEl = document.getElementById('calc-rr');
  const contractsEl = document.getElementById('calc-contracts');

  if (isNaN(entry)) { breakevenEl.textContent = '—'; rrEl.textContent = '—'; contractsEl.textContent = '—'; return; }

  breakevenEl.textContent = entry.toString();

  const stopDistance = !isNaN(stop) ? Math.abs(entry - stop) : null;
  const targetDistance = !isNaN(target) ? Math.abs(target - entry) : null;

  if (stopDistance && targetDistance) {
    rrEl.textContent = `1 : ${(targetDistance / stopDistance).toFixed(2)}`;
  } else {
    rrEl.textContent = '—';
  }

  if (stopDistance && pointValue && riskDollars) {
    const contracts = Math.floor(riskDollars / (stopDistance * pointValue));
    contractsEl.textContent = contracts >= 1 ? contracts.toString() : '< 1 (risk too small for this stop)';
  } else {
    contractsEl.textContent = '—';
  }
}

['calc-direction','calc-entry','calc-stop','calc-target','calc-point-value','calc-risk-dollars'].forEach(id => {
  document.getElementById(id).addEventListener('input', runCalculator);
});

// ============================================================
// Accounts (Multi-Account Overview)
// ============================================================
let accountsCache = [];

function accountStatus(a) {
  if (a.max_drawdown !== null && a.current_balance <= a.max_drawdown) return 'risk';
  if (a.profit_target !== null && a.current_balance >= a.profit_target) return 'target';
  return 'healthy';
}

async function loadAccounts() {
  const res = await fetch('/api/accounts');
  accountsCache = await res.json();
  renderAccounts();
  loadRiskStatus();
  populateGoalAccountSelect();
}

function renderAccounts() {
  const grid = document.getElementById('accounts-grid');
  const totalsEl = document.getElementById('accounts-totals');

  if (!accountsCache.length) {
    grid.innerHTML = '<div class="empty-state">No accounts added yet.</div>';
    totalsEl.innerHTML = '';
    return;
  }

  const totalCapital = accountsCache.reduce((s, a) => s + (a.current_balance || 0), 0);
  const totalAllocated = accountsCache.reduce((s, a) => s + (a.starting_balance || 0), 0);

  totalsEl.innerHTML = `
    <div class="stat-card"><span class="stat-label">Accounts</span><span class="stat-value">${accountsCache.length}</span></div>
    <div class="stat-card"><span class="stat-label">Total capital</span><span class="stat-value">${fmtMoney(totalCapital)}</span></div>
    <div class="stat-card"><span class="stat-label">Total allocated</span><span class="stat-value">${fmtMoney(totalAllocated)}</span></div>
  `;

  grid.innerHTML = accountsCache.map(a => {
    const status = accountStatus(a);
    const start = a.starting_balance || 0;
    const target = a.profit_target;
    let pct = 0;
    if (target !== null && target !== undefined && target !== start) {
      pct = Math.max(0, Math.min(100, ((a.current_balance - start) / (target - start)) * 100));
    }
    const toFloor = a.max_drawdown !== null ? fmtMoney(a.current_balance - a.max_drawdown) : '—';
    const toTarget = a.profit_target !== null ? fmtMoney(a.profit_target - a.current_balance) : '—';

    return `
      <div class="account-card status-${status}">
        <div><span class="account-name">${escapeHtml(a.name)}</span><span class="account-firm">${escapeHtml(a.firm || '')}</span></div>
        <div class="account-balance">${fmtMoney(a.current_balance)}</div>
        <div class="account-bar-track"><div class="account-bar-fill" style="width:${pct}%"></div></div>
        <div class="account-meta"><span>To floor: ${toFloor}</span><span>To target: ${toTarget}</span></div>
        <div class="account-actions">
          <button class="btn-secondary edit-account" data-id="${a.id}">Edit</button>
          <button class="btn-secondary delete-account" data-id="${a.id}">Delete</button>
        </div>
      </div>
    `;
  }).join('');

  document.querySelectorAll('.edit-account').forEach(btn => {
    btn.addEventListener('click', () => openAccountModal(parseInt(btn.dataset.id)));
  });
  document.querySelectorAll('.delete-account').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this account?')) return;
      await fetch(`/api/accounts/${btn.dataset.id}`, { method: 'DELETE' });
      loadAccounts();
    });
  });
}

const accountModal = document.getElementById('account-modal');
const accountForm = document.getElementById('account-form');
let editingAccountId = null;

function openAccountModal(id) {
  editingAccountId = id || null;
  accountForm.reset();
  if (id) {
    const a = accountsCache.find(x => x.id === id);
    if (a) {
      Object.keys(a).forEach(k => {
        const el = accountForm.querySelector(`[name="${k}"]`);
        if (el) el.value = a[k] ?? '';
      });
    }
  }
  accountModal.classList.remove('hidden');
}

document.getElementById('new-account-btn').addEventListener('click', () => openAccountModal(null));
document.getElementById('account-modal-close').addEventListener('click', () => accountModal.classList.add('hidden'));
document.getElementById('cancel-account').addEventListener('click', () => accountModal.classList.add('hidden'));

accountForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(accountForm).entries());
  const url = editingAccountId ? `/api/accounts/${editingAccountId}` : '/api/accounts';
  const method = editingAccountId ? 'PUT' : 'POST';
  await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  accountModal.classList.add('hidden');
  loadAccounts();
});

// ---------- Risk caps ----------
async function loadRiskCapsIntoInputs() {
  const res = await fetch('/api/settings');
  const settings = await res.json();
  document.getElementById('daily-risk-cap').value = settings.daily_risk_cap || '';
  document.getElementById('weekly-risk-cap').value = settings.weekly_risk_cap || '';
}

document.getElementById('save-caps-btn').addEventListener('click', async () => {
  const daily = document.getElementById('daily-risk-cap').value;
  const weekly = document.getElementById('weekly-risk-cap').value;
  await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ daily_risk_cap: daily, weekly_risk_cap: weekly }),
  });
  loadRiskStatus();
});

async function loadRiskStatus() {
  const res = await fetch('/api/risk-status');
  const s = await res.json();
  const el = document.getElementById('risk-status');
  if (!el) return;

  const dailyOver = s.daily_cap && s.risked_today >= s.daily_cap;
  const weeklyOver = s.weekly_cap && s.risked_week >= s.weekly_cap;

  el.innerHTML = `
    <div class="stat-card"><span class="stat-label">Risked today</span><span class="stat-value" style="color:${dailyOver ? 'var(--red)' : 'var(--text)'}">${fmtMoney(s.risked_today)}${s.daily_cap ? ' / ' + fmtMoney(s.daily_cap) : ''}</span></div>
    <div class="stat-card"><span class="stat-label">Risked this week</span><span class="stat-value" style="color:${weeklyOver ? 'var(--red)' : 'var(--text)'}">${fmtMoney(s.risked_week)}${s.weekly_cap ? ' / ' + fmtMoney(s.weekly_cap) : ''}</span></div>
  `;
}
loadRiskCapsIntoInputs();

// ============================================================
// Economic Calendar / News
// ============================================================
const NEWS_SOURCES = [
  { name: 'Walter Bloomberg (@DeItaone)', url: 'https://twitter.com/DeItaone', note: 'Relentless real-time headline feed, day/night/weekends.' },
  { name: 'RANsquawk', url: 'https://twitter.com/RANsquawk', note: 'Breaking news feed known for actively moving markets.' },
  { name: 'Zero Hedge', url: 'https://twitter.com/zerohedge', note: 'Macro / economic news.' },
  { name: 'Reuters', url: 'https://twitter.com/Reuters', note: 'Mainstream fast financial news.' },
  { name: 'Bloomberg News', url: 'https://twitter.com/BloombergNews', note: 'Mainstream fast financial news.' },
  { name: 'WSJ Markets', url: 'https://twitter.com/WSJmarkets', note: 'Global markets, economic data, corporate events.' },
  { name: 'Forex Factory Calendar', url: 'https://www.forexfactory.com/calendar', note: 'The original red/orange/yellow folder calendar.' },
];

function renderNewsLinks() {
  const el = document.getElementById('news-links');
  el.innerHTML = NEWS_SOURCES.map(s => `
    <div class="news-link-card">
      <a href="${s.url}" target="_blank" rel="noopener">${escapeHtml(s.name)}</a>
      <p>${escapeHtml(s.note)}</p>
    </div>
  `).join('');
}
renderNewsLinks();

let calendarCache = [];
let calendarSelectedDate = todayStr();

function parseDateStr(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function formatDateStr(d) {
  return d.toISOString().slice(0, 10);
}

function shiftDate(dateStr, days) {
  const d = parseDateStr(dateStr);
  d.setUTCDate(d.getUTCDate() + days);
  return formatDateStr(d);
}

function formatDisplayDate(dateStr) {
  if (dateStr === todayStr()) return 'Today';
  const d = parseDateStr(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

function updateDateNavUI() {
  document.getElementById('cal-date-label').textContent = formatDisplayDate(calendarSelectedDate);
  document.getElementById('cal-date-picker').value = calendarSelectedDate;
}

async function loadCalendar() {
  const res = await fetch('/api/calendar');
  calendarCache = await res.json();
  updateDateNavUI();
  renderCalendarTable();
}

function renderCalendarTable() {
  const tbody = document.getElementById('calendar-tbody');
  const dayEvents = calendarCache
    .filter(ev => ev.event_date === calendarSelectedDate)
    .sort((a, b) => (a.event_time || '').localeCompare(b.event_time || ''));

  if (!dayEvents.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No events for this day.</td></tr>';
    return;
  }
  tbody.innerHTML = dayEvents.map(ev => `
    <tr>
      <td>${escapeHtml(ev.event_time || '')}</td>
      <td>${escapeHtml(ev.title)}</td>
      <td class="impact-${ev.impact}">${ev.impact}</td>
      <td>${escapeHtml(ev.notes || '')}</td>
      <td><button class="btn-secondary delete-event" data-id="${ev.id}">Del</button></td>
    </tr>
  `).join('');
  document.querySelectorAll('.delete-event').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/calendar/${btn.dataset.id}`, { method: 'DELETE' });
      loadCalendar();
    });
  });
}

document.getElementById('cal-prev-day').addEventListener('click', () => {
  calendarSelectedDate = shiftDate(calendarSelectedDate, -1);
  updateDateNavUI();
  renderCalendarTable();
});

document.getElementById('cal-next-day').addEventListener('click', () => {
  calendarSelectedDate = shiftDate(calendarSelectedDate, 1);
  updateDateNavUI();
  renderCalendarTable();
});

document.getElementById('cal-today-btn').addEventListener('click', () => {
  calendarSelectedDate = todayStr();
  updateDateNavUI();
  renderCalendarTable();
});

const calDatePicker = document.getElementById('cal-date-picker');
calDatePicker.addEventListener('change', () => {
  if (calDatePicker.value) {
    calendarSelectedDate = calDatePicker.value;
    updateDateNavUI();
    renderCalendarTable();
  }
});
document.getElementById('cal-date-label').addEventListener('click', () => {
  if (calDatePicker.showPicker) calDatePicker.showPicker();
  else calDatePicker.focus();
});

async function loadSyncStatus() {
  const res = await fetch('/api/calendar/sync-status');
  const s = await res.json();
  const el = document.getElementById('cal-sync-status');
  el.textContent = s.last_sync ? `Last synced ${timeAgo(s.last_sync)}` : 'Never synced from Forex Factory yet.';
}
loadSyncStatus();

document.getElementById('cal-sync-btn').addEventListener('click', async () => {
  const statusEl = document.getElementById('cal-sync-status');
  statusEl.textContent = 'Syncing…';
  try {
    const res = await fetch('/api/calendar/sync', { method: 'POST' });
    const result = await res.json();
    if (result.error) {
      statusEl.textContent = result.error;
    } else {
      statusEl.textContent = `Synced ${result.synced} new event(s), skipped ${result.skipped_duplicates} already-synced.`;
      loadCalendar();
      loadSyncStatus();
    }
  } catch (err) {
    statusEl.textContent = 'Sync failed — check the connection and try again.';
  }
});

const eventModal = document.getElementById('event-modal');
document.getElementById('new-event-btn').addEventListener('click', () => {
  eventModal.classList.remove('hidden');
  const dateField = document.querySelector('#event-form [name="event_date"]');
  if (dateField && !dateField.value) dateField.value = calendarSelectedDate;
});
document.getElementById('event-modal-close').addEventListener('click', () => eventModal.classList.add('hidden'));
document.getElementById('cancel-event').addEventListener('click', () => eventModal.classList.add('hidden'));

document.getElementById('event-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  await fetch('/api/calendar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  e.target.reset();
  eventModal.classList.add('hidden');
  loadCalendar();
});

// ============================================================
// Psychology / Rule Compliance
// ============================================================
async function loadPsychology() {
  const res = await fetch('/api/psychology');
  const p = await res.json();

  const statsEl = document.getElementById('psych-stats');
  statsEl.innerHTML = `
    <div class="stat-card"><span class="stat-label">Full compliance (5/5)</span><span class="stat-value">${p.full_compliance}</span></div>
    <div class="stat-card"><span class="stat-label">Partial (1-4)</span><span class="stat-value">${p.partial_compliance}</span></div>
    <div class="stat-card"><span class="stat-label">No conditions (0)</span><span class="stat-value">${p.no_conditions}</span></div>
  `;

  const tbody = document.getElementById('psych-compliance-tbody');
  tbody.innerHTML = `
    <tr><td>Full compliance (5/5)</td><td>${p.compliant_trades}</td><td>${p.compliant_win_rate !== null ? p.compliant_win_rate + '%' : '—'}</td></tr>
    <tr><td>Anything less than 5/5</td><td>${p.noncompliant_trades}</td><td>${p.noncompliant_win_rate !== null ? p.noncompliant_win_rate + '%' : '—'}</td></tr>
  `;
}

// ============================================================
// Goals / Milestones
// ============================================================
function populateGoalAccountSelect() {
  const sel = document.getElementById('goal-account-select');
  const current = sel.value;
  sel.innerHTML = '<option value="">None (custom goal)</option>' +
    accountsCache.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
  sel.value = current;
}

async function loadGoals() {
  const [goalsRes, accountsRes] = await Promise.all([fetch('/api/goals'), fetch('/api/accounts')]);
  const goals = await goalsRes.json();
  accountsCache = await accountsRes.json();
  populateGoalAccountSelect();

  const el = document.getElementById('goals-list');
  if (!goals.length) {
    el.innerHTML = '<div class="empty-state">No goals set yet.</div>';
    return;
  }

  el.innerHTML = goals.map(g => {
    const account = accountsCache.find(a => a.id === g.account_id);
    const currentValue = account ? account.current_balance : g.current_value;
    const start = g.starting_value || 0;
    let pct = 0;
    if (g.target_value !== start) {
      pct = Math.max(0, Math.min(100, ((currentValue - start) / (g.target_value - start)) * 100));
    }
    return `
      <div class="goal-card">
        <div class="goal-title-row">
          <span class="goal-title">${escapeHtml(g.title)}${account ? ' · ' + escapeHtml(account.name) : ''}</span>
          <span class="goal-pct">${pct.toFixed(0)}%</span>
        </div>
        <div class="account-bar-track"><div class="account-bar-fill" style="width:${pct}%"></div></div>
        <div class="account-meta">
          <span>${fmtMoney(currentValue)} of ${fmtMoney(g.target_value)}</span>
          <span>${g.target_date ? 'By ' + escapeHtml(g.target_date) : ''}</span>
        </div>
        <div class="account-actions">
          <button class="btn-secondary delete-goal" data-id="${g.id}">Delete</button>
        </div>
      </div>
    `;
  }).join('');

  document.querySelectorAll('.delete-goal').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/goals/${btn.dataset.id}`, { method: 'DELETE' });
      loadGoals();
    });
  });
}

const goalModal = document.getElementById('goal-modal');
document.getElementById('new-goal-btn').addEventListener('click', () => goalModal.classList.remove('hidden'));
document.getElementById('goal-modal-close').addEventListener('click', () => goalModal.classList.add('hidden'));
document.getElementById('cancel-goal').addEventListener('click', () => goalModal.classList.add('hidden'));

document.getElementById('goal-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  if (!data.account_id) data.account_id = null;
  await fetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  e.target.reset();
  goalModal.classList.add('hidden');
  loadGoals();
});

// ============================================================
// Stats
// ============================================================
async function loadStats() {
  const res = await fetch('/api/stats');
  const stats = await res.json();

  document.getElementById('stat-total').textContent = stats.total_trades;
  document.getElementById('stat-winrate').textContent = stats.win_rate !== null ? `${stats.win_rate}%` : '—';
  const pnlEl = document.getElementById('stat-pnl');
  pnlEl.textContent = fmtMoney(stats.total_pnl);
  pnlEl.style.color = stats.total_pnl > 0 ? 'var(--green)' : (stats.total_pnl < 0 ? 'var(--red)' : 'var(--text)');

  const tbody = document.getElementById('session-tbody');
  const sessions = Object.entries(stats.by_session || {});
  if (!sessions.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No data yet.</td></tr>';
    return;
  }
  tbody.innerHTML = sessions.map(([session, s]) => {
    const decided = s.wins + s.losses;
    const wr = decided ? Math.round((s.wins / decided) * 100) : null;
    return `
      <tr>
        <td>${escapeHtml(session)}</td>
        <td class="result-win">${s.wins}</td>
        <td class="result-loss">${s.losses}</td>
        <td>${wr !== null ? wr + '%' : '—'}</td>
        <td>${fmtMoney(s.total_pnl)}</td>
      </tr>
    `;
  }).join('');
}

// ============================================================
// Init
// ============================================================
loadDashboardPage();
loadRecordsPage();
setInterval(loadTracker, 30000);

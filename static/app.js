const API = '';
let allInvoices = [], filterStatus = '', editingInvoiceId = null;
let editingCpId = null, editingMcId = null, editingServiceId = null;
let itemRows = [];
let serviceItemsCache = [];
const CURRENCY_SYMBOLS = { EUR: '€', USD: '$', UAH: '₴' };
const STATUS_LABELS = { draft: 'Draft', sent: 'Pending', paid: 'Paid' };

// ── NAVIGATION ──
document.querySelectorAll('.nav-item[data-screen]').forEach(el => {
  el.addEventListener('click', e => { e.preventDefault(); goTo(el.dataset.screen); });
});

function goTo(screen) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navEl = document.querySelector(`.nav-item[data-screen="${screen}"]`);
  if (navEl) navEl.classList.add('active');
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(`screen-${screen}`).classList.add('active');
  if (screen === 'invoices') loadInvoices();
  if (screen === 'new-invoice') initNewInvoiceForm();
  if (screen === 'templates') loadTemplates();
  if (screen === 'counterparties') loadCounterparties();
  if (screen === 'service-items') loadServiceItems();
  if (screen === 'my-companies') loadMyCompanies();
}

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (type ? ' ' + type : '');
  setTimeout(() => el.classList.remove('show'), 3000);
}

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── INVOICES ──
function _populateFilterSelect(id, values, allLabel = 'All') {
  const sel = document.getElementById(id);
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = `<option value="">${allLabel}</option>` +
    values.map(v => `<option value="${v}">${v}</option>`).join('');
  if (cur) sel.value = cur;
}

function _ensureDefaultDateFilters() {
  // По умолчанию диапазон = с 1 января текущего года по сегодня.
  // Заодно избавляет от плейсхолдера "дд.мм.рррр" в дате с локализованным браузером.
  const today = new Date();
  const pad = n => String(n).padStart(2, '0');
  const fromDefault = `${today.getFullYear()}-01-01`;
  const toDefault = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  const from = document.getElementById('filter-date-from');
  const to = document.getElementById('filter-date-to');
  if (from && !from.value) from.value = fromDefault;
  if (to && !to.value) to.value = toDefault;
}

async function loadInvoices() {
  try {
    _ensureDefaultDateFilters();
    allInvoices = await api('GET', '/invoices/');
    const cps = [...new Set(allInvoices.map(i => i.counterparty_name).filter(Boolean))].sort();
    const mcs = [...new Set(allInvoices.map(i => i.my_company_name).filter(Boolean))].sort();
    _populateFilterSelect('filter-cp', cps);
    _populateFilterSelect('filter-mc', mcs);
    renderInvoices();
  } catch (e) { toast(e.message, 'error'); }
}

function clearFilters() {
  document.getElementById('search-input').value = '';
  ['filter-cp', 'filter-mc', 'filter-date-from', 'filter-date-to'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  renderInvoices();
}

let sortField = 'date', sortDir = -1;

function sortInvoices(field) {
  if (sortField === field) sortDir *= -1;
  else { sortField = field; sortDir = -1; }
  document.querySelectorAll('.sort-btn').forEach(b => {
    b.classList.remove('sort-asc', 'sort-desc');
    if (b.dataset.sort === field) b.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
  });
  renderInvoices();
}

function renderInvoices() {
  const q = (document.getElementById('search-input').value || '').toLowerCase();
  const tbody = document.getElementById('invoices-body');
  const cpFilter = document.getElementById('filter-cp')?.value || '';
  const mcFilter = document.getElementById('filter-mc')?.value || '';
  const dateFrom = document.getElementById('filter-date-from')?.value || '';
  const dateTo   = document.getElementById('filter-date-to')?.value || '';

  let list = allInvoices.filter(inv => {
    const matchSearch = !q || inv.number.toLowerCase().includes(q) || inv.counterparty_name.toLowerCase().includes(q);
    const matchCp     = !cpFilter || inv.counterparty_name === cpFilter;
    const matchMc     = !mcFilter || inv.my_company_name === mcFilter;
    const matchFrom   = !dateFrom || inv.date >= dateFrom;
    const matchTo     = !dateTo   || inv.date <= dateTo;
    return matchSearch && matchCp && matchMc && matchFrom && matchTo;
  });
  list = list.sort((a, b) => {
    let va = a[sortField], vb = b[sortField];
    if (sortField === 'date') { va = new Date(va); vb = new Date(vb); }
    if (sortField === 'total_amount') { va = +va; vb = +vb; }
    if (va < vb) return -sortDir;
    if (va > vb) return sortDir;
    return 0;
  });
  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><i class="ti ti-files-off"></i><p>No invoices found</p></div></td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(inv => {
    const sym = CURRENCY_SYMBOLS[inv.currency] || inv.currency;
    const amt = inv.total_amount.toLocaleString('en-US', {minimumFractionDigits: 2});
    const d = new Date(inv.date).toLocaleDateString('ru-RU');
    return `<tr>
      <td><span class="invoice-number">${inv.number}</span></td>
      <td>${inv.counterparty_name}</td>
      <td>${inv.my_company_name || '—'}</td>
      <td>${d}</td>
      <td class="right" style="font-family:var(--font-mono)">${sym} ${amt}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-sm btn-pdf" onclick="generateAndDownload(${inv.id},'${inv.number}')" title="Download PDF"><i class="ti ti-download"></i> PDF</button>
          <button class="btn btn-sm btn-edit" onclick="editInvoice(${inv.id})"><i class="ti ti-edit"></i> Edit</button>
          <button class="btn btn-sm btn-copy" onclick="duplicateInvoice(${inv.id})"><i class="ti ti-copy"></i> Duplicate</button>
          <button class="btn btn-sm btn-delete" onclick="deleteInvoice(${inv.id},'${inv.number}')"><i class="ti ti-trash"></i> Delete</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}



document.querySelectorAll('.filter-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    filterStatus = tab.dataset.status;
    renderInvoices();
  });
});

async function markPaid(id) {
  try { await api('PATCH', `/invoices/${id}/status?status=paid`); toast('Marked as paid', 'success'); loadInvoices(); }
  catch (e) { toast(e.message, 'error'); }
}

async function deleteInvoice(id, number) {
  if (!confirm(`Delete invoice ${number}? This action cannot be undone.`)) return;
  try { await api('DELETE', `/invoices/${id}`); toast('Invoice deleted'); loadInvoices(); }
  catch (e) { toast(e.message, 'error'); }
}

async function duplicateInvoice(id) {
  try { await api('POST', `/invoices/${id}/duplicate`); toast('Duplicated', 'success'); loadInvoices(); }
  catch (e) { toast(e.message, 'error'); }
}

async function generateAndDownload(id, number) {
  try {
    toast('Generating PDF…');
    await api('POST', `/invoices/${id}/generate-pdf`);
    window.open(`${API}/invoices/${id}/pdf`, '_blank');
    toast('PDF ready', 'success');
    loadInvoices();
  } catch (e) { toast(e.message, 'error'); }
}

async function editInvoice(id) {
  try {
    const inv = await api('GET', `/invoices/${id}`);
    editingInvoiceId = id;
    await initNewInvoiceForm();
    document.getElementById('form-title').textContent = `Edit ${inv.number}`;
    document.getElementById('f-number').value = inv.number;
    document.getElementById('f-date').value = inv.date;
    document.getElementById('f-due-date').value = inv.due_date || '';
    document.getElementById('f-currency').value = inv.currency;
    document.getElementById('f-total').value = inv.total_amount;
    document.getElementById('f-counterparty').value = inv.counterparty_id;
    document.getElementById('f-template').value = inv.template_id;
    document.getElementById('f-my-company').value = inv.my_company_id || '';
    document.getElementById('f-currency-sym').textContent = CURRENCY_SYMBOLS[inv.currency] || '€';
    itemRows = inv.items.map(i => ({ description: i.description, unit: i.unit, rate: i.rate }));
    renderItemRows();
    recalcPreview();
    goTo('new-invoice');
  } catch (e) { toast(e.message, 'error'); }
}

// ── NEW INVOICE FORM ──
async function initNewInvoiceForm() {
  if (!editingInvoiceId) {
    document.getElementById('form-title').textContent = 'New invoice';
    document.getElementById('f-date').value = today();
    numberAutoGenerated = true;
    document.getElementById('f-number').value = generateNumber();
    document.getElementById('f-due-date').value = '';
    document.getElementById('f-currency').value = 'EUR';
    document.getElementById('f-total').value = '';
    document.getElementById('f-currency-sym').textContent = '€';
    itemRows = [];
  } else {
    // В режиме редактирования номер не трогаем — он уже сохранён, и автогенерацию не включаем.
    numberAutoGenerated = false;
  }
  // loadMcSelect должен закончиться ДО loadServiceSelect — ставки зависят от выбранной компании
  await Promise.all([loadCpSelect(), loadTmplSelect(), loadMcSelect()]);
  await loadServiceSelect();
  // Селекты уже наполнились (loadMcSelect мог автовыбрать первую компанию) — пересчитываем номер.
  regenerateNumberIfAuto();
  renderItemRows();
  recalcPreview();
}

let numberAutoGenerated = false;

function _initialsOf(name, n = 2) {
  if (!name) return '';
  const letters = (name.match(/[A-Za-zА-Яа-яЁё]/g) || []).slice(0, n);
  return letters.join('').toUpperCase();
}

function _selectedText(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return '';
  const opt = sel.options[sel.selectedIndex];
  return opt && opt.value ? opt.textContent.trim() : '';
}

// Формат: DDMMYYYY + 2 буквы контрагента + 2 буквы моей компании.
// Если что-то не выбрано — соответствующие буквы пропускаются.
function generateNumber() {
  const dateStr = document.getElementById('f-date').value;
  let datePart;
  if (dateStr) {
    const [y, m, day] = dateStr.split('-');
    datePart = `${day}${m}${y}`;
  } else {
    const now = new Date();
    datePart = `${String(now.getDate()).padStart(2,'0')}${String(now.getMonth()+1).padStart(2,'0')}${now.getFullYear()}`;
  }
  return datePart + _initialsOf(_selectedText('f-counterparty')) + _initialsOf(_selectedText('f-my-company'));
}

// Перегенерация номера — только если пользователь его руками не правил.
function regenerateNumberIfAuto() {
  if (!numberAutoGenerated) return;
  document.getElementById('f-number').value = generateNumber();
}

function today() { return new Date().toISOString().slice(0, 10); }

async function loadCpSelect() {
  try {
    const cps = await api('GET', '/counterparties/');
    const sel = document.getElementById('f-counterparty');
    const cur = sel.value;
    sel.innerHTML = '<option value=""></option>' + cps.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    if (cur) sel.value = cur;
  } catch {}
}

async function loadTmplSelect() {
  try {
    const tmpls = await api('GET', '/templates/');
    const sel = document.getElementById('f-template');
    const cur = sel.value;
    sel.innerHTML = '<option value="">— template —</option>' + tmpls.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
    if (cur) sel.value = cur;
    else if (tmpls.length) sel.value = tmpls[0].id;
  } catch {}
}

async function loadMcSelect() {
  try {
    const mcs = await api('GET', '/my-companies/');
    const sel = document.getElementById('f-my-company');
    const cur = sel.value;
    sel.innerHTML = '<option value=""></option>' + mcs.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    if (cur) sel.value = cur;
  } catch {}
}

function rateForCompany(serviceItem, mcId) {
  // Ставка для выбранной компании, иначе default_rate
  if (mcId && serviceItem.rates) {
    const r = serviceItem.rates.find(r => r.my_company_id === mcId);
    if (r) return r.rate;
  }
  return serviceItem.default_rate;
}

function renderServiceSelect() {
  const mcId = parseInt(document.getElementById('f-my-company').value) || null;
  const sel = document.getElementById('service-item-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">+ from library</option>' + serviceItemsCache.map(i => {
    const rate = rateForCompany(i, mcId);
    return `<option value="${i.id}" data-desc="${i.description}" data-unit="${i.unit}" data-rate="${rate}">${i.description} (${rate}€/h)</option>`;
  }).join('');
}

async function loadServiceSelect() {
  try {
    serviceItemsCache = await api('GET', '/service-items/');
    renderServiceSelect();
  } catch {}
}

document.getElementById('f-currency').addEventListener('change', function() {
  document.getElementById('f-currency-sym').textContent = CURRENCY_SYMBOLS[this.value] || this.value;
  recalcPreview();
});

document.getElementById('f-my-company').addEventListener('change', function() {
  renderServiceSelect();
  rerateRowsForCompany();
  regenerateNumberIfAuto();
});

document.getElementById('f-counterparty').addEventListener('change', regenerateNumberIfAuto);
document.getElementById('f-date').addEventListener('change', regenerateNumberIfAuto);
document.getElementById('f-number').addEventListener('input', () => { numberAutoGenerated = false; });

function rerateRowsForCompany() {
  const mcId = parseInt(document.getElementById('f-my-company').value) || null;
  let changed = 0;
  itemRows.forEach(row => {
    if (!row.service_item_id) return;  // строка введена вручную — не трогаем
    const item = serviceItemsCache.find(s => s.id === row.service_item_id);
    if (!item) return;
    const newRate = rateForCompany(item, mcId);
    if (newRate !== row.rate) { row.rate = newRate; changed++; }
  });
  if (changed) {
    renderItemRows();
    recalcPreview();
    toast(`Updated rates for ${changed} ${changed === 1 ? 'item' : 'items'}`, 'success');
  }
}

document.getElementById('service-item-select').addEventListener('change', function() {
  const opt = this.options[this.selectedIndex];
  if (!opt.value) return;
  itemRows.push({
    service_item_id: parseInt(opt.value),
    description: opt.dataset.desc,
    unit: opt.dataset.unit,
    rate: parseFloat(opt.dataset.rate),
  });
  this.value = '';
  renderItemRows();
  recalcPreview();
});

function addItemRow() {
  itemRows.push({ description: '', unit: 'Hours', rate: 100 });
  renderItemRows();
  recalcPreview();
}

function removeItemRow(i) {
  itemRows.splice(i, 1);
  renderItemRows();
  recalcPreview();
}

function renderItemRows() {
  const tbody = document.getElementById('items-body');
  tbody.innerHTML = itemRows.map((row, i) => `
    <tr>
      <td><input value="${row.description}" placeholder="Description" onchange="itemRows[${i}].description=this.value"></td>
      <td><input type="number" value="${row.rate}" min="1" onchange="itemRows[${i}].rate=parseFloat(this.value)||1;recalcPreview()"></td>
      <td><span class="time-preview" id="tp-${i}">—</span></td>
      <td><span class="amount-preview" id="ap-${i}">—</span></td>
      <td><button class="btn btn-sm btn-ghost" onclick="removeItemRow(${i})"><i class="ti ti-trash"></i></button></td>
    </tr>`).join('');
}

function recalcPreview() {
  const total = parseFloat(document.getElementById('f-total').value) || 0;
  const sym = CURRENCY_SYMBOLS[document.getElementById('f-currency').value] || '€';
  const n = itemRows.length;
  const totalsEl = document.getElementById('items-totals');
  if (!total || !n) { totalsEl.innerHTML = ''; return; }

  // Случайное распределение для превью
  const weights = itemRows.map(() => 0.5 + Math.random());
  const wsum = weights.reduce((a, b) => a + b, 0);
  let remaining = total;
  const results = [];
  itemRows.forEach((row, i) => {
    let amount;
    if (i < n - 1) {
      amount = Math.round((weights[i] / wsum) * total * 100) / 100;
      remaining -= amount;
    } else {
      amount = Math.round(remaining * 100) / 100;
    }
    const mins = Math.max(1, Math.round(amount / row.rate * 60));
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    results.push({ time: `${h}:${String(m).padStart(2,'0')}`, amount });
    const tp = document.getElementById(`tp-${i}`);
    const ap = document.getElementById(`ap-${i}`);
    if (tp) tp.textContent = `~${h}:${String(m).padStart(2,'0')}`;
    if (ap) ap.textContent = `${sym} ${amount.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  });
  totalsEl.innerHTML = `
    <div class="total-line">${results.map((r, i) => `${r.time} × ${sym}${itemRows[i].rate}`).join(' + ')}</div>
    <div class="total-grand">${sym} ${total.toLocaleString('en-US', {minimumFractionDigits: 2})}</div>`;
}

async function saveInvoice() {
  const number = document.getElementById('f-number').value.trim();
  const date = document.getElementById('f-date').value;
  const cpId = parseInt(document.getElementById('f-counterparty').value);
  const tmplId = parseInt(document.getElementById('f-template').value);
  const total = parseFloat(document.getElementById('f-total').value);
  const mcId = parseInt(document.getElementById('f-my-company').value) || null;

  if (!number) return toast('Enter invoice number', 'error');
  if (!date) return toast('Enter date', 'error');
  if (!cpId) return toast('Select a client', 'error');
  if (!tmplId) return toast('Select a template', 'error');
  if (!total || total <= 0) return toast('Enter amount', 'error');
  if (!itemRows.length) return toast('Add at least one item', 'error');

  const payload = {
    number, date,
    due_date: document.getElementById('f-due-date').value || null,
    currency: document.getElementById('f-currency').value,
    total_amount: total,
    counterparty_id: cpId,
    template_id: tmplId,
    my_company_id: mcId,
    notes: null,
    items: itemRows.map(r => ({ description: r.description, unit: r.unit || 'Hours', rate: r.rate })),
  };

  try {
    if (editingInvoiceId) {
      await api('PUT', `/invoices/${editingInvoiceId}`, payload);
      toast('Invoice updated', 'success');
    } else {
      await api('POST', '/invoices/', payload);
      toast('Invoice created', 'success');
    }
    editingInvoiceId = null;
    goTo('invoices');
  } catch (e) { toast(e.message, 'error'); }
}

function resetInvoiceForm() { editingInvoiceId = null; initNewInvoiceForm(); }

// ── TEMPLATES ──
async function loadTemplates() {
  try {
    const tmpls = await api('GET', '/templates/');
    const grid = document.getElementById('templates-grid');
    grid.innerHTML = tmpls.map(t => `
      <div class="tmpl-card">
        <div class="tmpl-preview"><i class="ti ti-file-description"></i><span style="font-size:11px">${t.filename}</span></div>
        <div class="tmpl-info">
          <div class="tmpl-name">${t.name}</div>
          <div class="tmpl-meta">Used ${t.usage_count} times</div>
          <div class="tmpl-actions">
            <button class="btn btn-sm" onclick="duplicateTemplate(${t.id},'${t.name}')"><i class="ti ti-copy"></i> Copy</button>
            <button class="btn btn-sm btn-delete" onclick="deleteTemplate(${t.id})"><i class="ti ti-trash"></i> Delete</button>
          </div>
        </div>
      </div>`).join('') +
      `<div class="tmpl-card-add" onclick="document.getElementById('tmpl-upload-input').click()"><i class="ti ti-upload"></i><span>Upload</span></div>`;
  } catch (e) { toast(e.message, 'error'); }
}

async function uploadTemplate(input) {
  const file = input.files[0];
  if (!file) return;
  const name = file.name.replace(/\.[^.]+$/, '').replace(/_/g, ' ');
  const fd = new FormData();
  fd.append('file', file);
  fd.append('name', name);
  try {
    const res = await fetch(API + '/templates/upload', { method: 'POST', body: fd });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error'); }
    toast('Template uploaded', 'success');
    loadTemplates();
  } catch (e) { toast(e.message, 'error'); }
  input.value = '';
}

async function duplicateTemplate(id, name) {
  try { await api('POST', `/templates/${id}/duplicate?new_name=Copy+${encodeURIComponent(name)}`); toast('Duplicated', 'success'); loadTemplates(); }
  catch (e) { toast(e.message, 'error'); }
}

async function deleteTemplate(id) {
  if (!confirm('Delete template?')) return;
  try { await api('DELETE', `/templates/${id}`); toast('Deleted'); loadTemplates(); }
  catch (e) { toast(e.message, 'error'); }
}

// ── COUNTERPARTIES ──
async function loadCounterparties() {
  try {
    const cps = await api('GET', '/counterparties/');
    const grid = document.getElementById('cp-grid');
    grid.innerHTML = cps.map(cp => `
      <div class="cp-card">
        <div class="cp-name">${cp.name}</div>
        <div class="cp-detail">
          ${cp.company_number ? `Registration number: ${cp.company_number}<br>` : ''}
          ${cp.eu_vat ? `EU VAT: ${cp.eu_vat}<br>` : ''}
          ${cp.iban ? `IBAN: ${cp.iban}` : ''}
        </div>
        <div class="cp-stats"><span>${cp.invoice_count} invoices</span><span>€ ${(cp.total_billed||0).toLocaleString('en-US',{maximumFractionDigits:0})}</span></div>
        <div class="cp-actions">
          <button class="btn btn-sm" onclick="openCpModal(${cp.id})"><i class="ti ti-edit"></i> Edit</button>
          <button class="btn btn-sm btn-delete" onclick="deleteCp(${cp.id})"><i class="ti ti-trash"></i> Delete</button>
        </div>
      </div>`).join('') +
      `<div class="cp-card-add" onclick="openCpModal()"><i class="ti ti-plus"></i><span>Add</span></div>`;
  } catch (e) { toast(e.message, 'error'); }
}

async function openCpModal(id) {
  editingCpId = id || null;
  document.getElementById('cp-modal-title').textContent = id ? 'Edit client' : 'New client';
  ['id','name','address','old-address','company-number','eu-vat','iban','swift','notes'].forEach(f => {
    const el = document.getElementById('cp-' + f); if (el) el.value = '';
  });
  if (id) {
    try {
      const cp = await api('GET', `/counterparties/${id}`);
      document.getElementById('cp-id').value = cp.id;
      document.getElementById('cp-name').value = cp.name || '';
      document.getElementById('cp-address').value = cp.address || '';
      document.getElementById('cp-old-address').value = cp.old_address || '';
      document.getElementById('cp-company-number').value = cp.company_number || '';
      document.getElementById('cp-eu-vat').value = cp.eu_vat || '';
      document.getElementById('cp-iban').value = cp.iban || '';
      document.getElementById('cp-swift').value = cp.swift || '';
      document.getElementById('cp-notes').value = cp.notes || '';
    } catch (e) { toast(e.message, 'error'); return; }
  }
  document.getElementById('cp-modal').style.display = 'flex';
}

function closeCpModal() { document.getElementById('cp-modal').style.display = 'none'; editingCpId = null; }

async function saveCp() {
  const name = document.getElementById('cp-name').value.trim();
  if (!name) return toast('Enter name', 'error');
  const payload = {
    name,
    address: document.getElementById('cp-address').value || null,
    old_address: document.getElementById('cp-old-address').value || null,
    company_number: document.getElementById('cp-company-number').value || null,
    eu_vat: document.getElementById('cp-eu-vat').value || null,
    iban: document.getElementById('cp-iban').value || null,
    swift: document.getElementById('cp-swift').value || null,
    notes: document.getElementById('cp-notes').value || null,
  };
  try {
    if (editingCpId) await api('PUT', `/counterparties/${editingCpId}`, payload);
    else await api('POST', '/counterparties/', payload);
    toast('Saved', 'success');
    closeCpModal();
    loadCounterparties();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteCp(id) {
  if (!confirm('Delete client?')) return;
  try { await api('DELETE', `/counterparties/${id}`); toast('Deleted'); loadCounterparties(); }
  catch (e) { toast(e.message, 'error'); }
}

// ── MY COMPANIES ──
async function loadMyCompanies() {
  try {
    const mcs = await api('GET', '/my-companies/');
    const grid = document.getElementById('mc-grid');
    grid.innerHTML = mcs.map(mc => `
      <div class="cp-card">
        <div class="cp-name">${mc.name}</div>
        <div class="cp-detail">
          ${mc.country ? mc.country + '<br>' : ''}
          ${mc.company_number ? `Company: ${mc.company_number}<br>` : ''}
          ${mc.iban ? `IBAN: ${mc.iban}<br>` : (mc.account_number ? `Account: ${mc.account_number}<br>` : '')}
          ${mc.swift ? `SWIFT: ${mc.swift}` : (mc.routing_number ? `Routing: ${mc.routing_number}` : '')}
        </div>
        <div class="cp-actions">
          <button class="btn btn-sm" onclick="openMcModal(${mc.id})"><i class="ti ti-edit"></i> Edit</button>
          <button class="btn btn-sm btn-delete" onclick="deleteMc(${mc.id})"><i class="ti ti-trash"></i> Delete</button>
        </div>
      </div>`).join('') +
      `<div class="cp-card-add" onclick="openMcModal()"><i class="ti ti-plus"></i><span>Add company</span></div>`;
  } catch (e) { toast(e.message, 'error'); }
}

async function openMcModal(id) {
  editingMcId = id || null;
  document.getElementById('mc-modal-title').textContent = id ? 'Edit company' : 'New company';
  ['id','name','address','country','company-number','iban','swift','vat','account-number','routing-number'].forEach(f => {
    const el = document.getElementById('mc-' + f); if (el) el.value = '';
  });
  if (id) {
    try {
      const mc = await api('GET', `/my-companies/${id}`);
      // нет GET one, используем список
    } catch {}
    try {
      const mcs = await api('GET', '/my-companies/');
      const mc = mcs.find(m => m.id === id);
      if (mc) {
        document.getElementById('mc-id').value = mc.id;
        document.getElementById('mc-name').value = mc.name || '';
        document.getElementById('mc-address').value = mc.address || '';
        document.getElementById('mc-country').value = mc.country || '';
        document.getElementById('mc-company-number').value = mc.company_number || '';
        document.getElementById('mc-iban').value = mc.iban || '';
        document.getElementById('mc-swift').value = mc.swift || '';
        document.getElementById('mc-vat').value = mc.vat || '';
        document.getElementById('mc-account-number').value = mc.account_number || '';
        document.getElementById('mc-routing-number').value = mc.routing_number || '';
      }
    } catch (e) { toast(e.message, 'error'); return; }
  }
  document.getElementById('mc-modal').style.display = 'flex';
}

function closeMcModal() { document.getElementById('mc-modal').style.display = 'none'; editingMcId = null; }

async function saveMc() {
  const name = document.getElementById('mc-name').value.trim();
  if (!name) return toast('Enter name', 'error');
  const payload = {
    name,
    address: document.getElementById('mc-address').value || null,
    country: document.getElementById('mc-country').value || null,
    company_number: document.getElementById('mc-company-number').value || null,
    iban: document.getElementById('mc-iban').value || null,
    swift: document.getElementById('mc-swift').value || null,
    vat: document.getElementById('mc-vat').value || null,
    account_number: document.getElementById('mc-account-number').value || null,
    routing_number: document.getElementById('mc-routing-number').value || null,
  };
  try {
    if (editingMcId) await api('PUT', `/my-companies/${editingMcId}`, payload);
    else await api('POST', '/my-companies/', payload);
    toast('Saved', 'success');
    closeMcModal();
    loadMyCompanies();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteMc(id) {
  if (!confirm('Delete company?')) return;
  try { await api('DELETE', `/my-companies/${id}`); toast('Deleted'); loadMyCompanies(); }
  catch (e) { toast(e.message, 'error'); }
}

// ── SERVICE ITEMS ──
let allServiceItems = [];

async function loadServiceItems() {
  try {
    allServiceItems = await api('GET', '/service-items/');
    renderServiceItems();
  } catch (e) { toast(e.message, 'error'); }
}

function renderServiceItems() {
  const q = (document.getElementById('service-search')?.value || '').trim().toLowerCase();
  // Подстрочный matching: q найдётся в любом месте описания, не только в начале.
  const items = q
    ? allServiceItems.filter(i => (i.description || '').toLowerCase().includes(q))
    : allServiceItems;
  const tbody = document.getElementById('service-items-body');
  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><i class="ti ti-list-off"></i><p>${q ? 'No results' : 'No items yet — add your first'}</p></div></td></tr>`;
    return;
  }
  tbody.innerHTML = items.map(item => {
    const ratesList = item.rates && item.rates.length
      ? item.rates.map(r => `<span style="display:inline-block;background:var(--bg);border:1px solid var(--border);border-radius:20px;padding:2px 8px;font-size:11px;margin:2px">${r.my_company_name}: ${r.rate}€/h</span>`).join(' ')
      : `<span style="color:var(--text-muted);font-size:11px">No rates</span>`;
    return `<tr>
      <td>${item.description}</td>
      <td>${item.unit}</td>
      <td class="right" style="font-family:var(--font-mono)">${item.default_rate} €/h</td>
      <td>${ratesList}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-sm btn-edit" onclick="openServiceModal(${item.id})"><i class="ti ti-edit"></i></button>
          <button class="btn btn-sm btn-delete" onclick="deleteService(${item.id})"><i class="ti ti-trash"></i> Delete</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

async function openServiceModal(id) {
  editingServiceId = id || null;
  document.getElementById('service-modal-title').textContent = id ? 'Edit item' : 'New item';
  document.getElementById('service-id').value = '';
  document.getElementById('service-description').value = '';
  document.getElementById('service-unit').value = 'Hours';
  document.getElementById('service-rate').value = '100';

  // Загружаем компании для ставок
  let companies = [];
  try { companies = await api('GET', '/my-companies/'); } catch {}

  let existingRates = {};
  if (id) {
    try {
      const items = await api('GET', '/service-items/');
      const item = items.find(i => i.id === id);
      if (item) {
        document.getElementById('service-id').value = item.id;
        document.getElementById('service-description').value = item.description;
        document.getElementById('service-unit').value = item.unit;
        document.getElementById('service-rate').value = item.default_rate;
        (item.rates || []).forEach(r => { existingRates[r.my_company_id] = r.rate; });
      }
    } catch (e) { toast(e.message, 'error'); return; }
  }

  // Рендерим ставки по компаниям
  const ratesDiv = document.getElementById('service-rates-list');
  if (companies.length) {
    ratesDiv.innerHTML = `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">Per-company rates (optional)</div>` +
      companies.map(mc => `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          <span style="font-size:13px;flex:1">${mc.name}</span>
          <input type="number" class="company-rate-input" data-company-id="${mc.id}"
            value="${existingRates[mc.id] || ''}" placeholder="rate €/h"
            style="width:120px;padding:6px 8px;border:1px solid var(--border-strong);border-radius:var(--radius-sm);font-size:13px">
        </div>`).join('');
  } else {
    ratesDiv.innerHTML = `<p style="font-size:12px;color:var(--text-muted)">Add companies in "My company" first</p>`;
  }

  document.getElementById('service-modal').style.display = 'flex';
}

function closeServiceModal() { document.getElementById('service-modal').style.display = 'none'; editingServiceId = null; }

async function saveService() {
  const description = document.getElementById('service-description').value.trim();
  if (!description) return toast('Enter description', 'error');
  const payload = {
    description,
    unit: document.getElementById('service-unit').value || 'Hours',
    default_rate: parseFloat(document.getElementById('service-rate').value) || 100,
  };
  try {
    let item;
    if (editingServiceId) {
      item = await api('PUT', `/service-items/${editingServiceId}`, payload);
    } else {
      item = await api('POST', '/service-items/', payload);
    }
    // Сохраняем ставки по компаниям
    const rateInputs = document.querySelectorAll('.company-rate-input');
    for (const input of rateInputs) {
      const companyId = parseInt(input.dataset.companyId);
      const rate = parseFloat(input.value);
      if (rate > 0) {
        await api('POST', `/service-items/${item.id}/rates`, { my_company_id: companyId, rate });
      }
    }
    toast('Saved', 'success');
    closeServiceModal();
    loadServiceItems();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteService(id) {
  if (!confirm('Delete item?')) return;
  try { await api('DELETE', `/service-items/${id}`); toast('Deleted'); loadServiceItems(); }
  catch (e) { toast(e.message, 'error'); }
}

// ── INIT ──
loadInvoices();

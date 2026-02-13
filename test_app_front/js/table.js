const TABLES = {
    locations: {
        endpoint: '/api/locations',
        label: 'Locations',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Name', type: 'text' },
            { key: 'city', label: 'City', type: 'text' },
            { key: 'address', label: 'Address', type: 'text' },
            { key: 'phone', label: 'Phone', type: 'text' },
        ],
    },
    employees: {
        endpoint: '/api/employees',
        label: 'Employees',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'location_id', label: 'Location ID', type: 'number' },
            { key: 'first_name', label: 'First Name', type: 'text' },
            { key: 'last_name', label: 'Last Name', type: 'text' },
            { key: 'role', label: 'Role', type: 'select', options: ['manager','agent','mechanic','receptionist'] },
            { key: 'salary', label: 'Salary', type: 'decimal' },
            { key: 'hire_date', label: 'Hire Date', type: 'date' },
            { key: 'email', label: 'Email', type: 'text' },
            { key: 'phone', label: 'Phone', type: 'text' },
        ],
    },
    categories: {
        endpoint: '/api/categories',
        label: 'Vehicle Categories',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Name', type: 'text' },
            { key: 'description', label: 'Description', type: 'text' },
            { key: 'daily_rate_min', label: 'Min Rate', type: 'decimal' },
            { key: 'daily_rate_max', label: 'Max Rate', type: 'decimal' },
        ],
    },
    vehicles: {
        endpoint: '/api/vehicles',
        label: 'Vehicles',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'category_id', label: 'Category ID', type: 'number' },
            { key: 'location_id', label: 'Location ID', type: 'number' },
            { key: 'make', label: 'Make', type: 'text' },
            { key: 'model', label: 'Model', type: 'text' },
            { key: 'year', label: 'Year', type: 'number' },
            { key: 'license_plate', label: 'Plate', type: 'text' },
            { key: 'color', label: 'Color', type: 'text' },
            { key: 'daily_rate', label: 'Daily Rate', type: 'decimal' },
            { key: 'mileage', label: 'Mileage', type: 'number' },
            { key: 'status', label: 'Status', type: 'select', options: ['available','rented','maintenance','retired'] },
        ],
    },
    clients: {
        endpoint: '/api/clients',
        label: 'Clients',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'first_name', label: 'First Name', type: 'text' },
            { key: 'last_name', label: 'Last Name', type: 'text' },
            { key: 'email', label: 'Email', type: 'text' },
            { key: 'phone', label: 'Phone', type: 'text' },
            { key: 'drivers_license', label: 'License', type: 'text' },
            { key: 'date_of_birth', label: 'DOB', type: 'date' },
            { key: 'registration_date', label: 'Registered', type: 'date' },
        ],
    },
    reservations: {
        endpoint: '/api/reservations',
        label: 'Reservations',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'client_id', label: 'Client ID', type: 'number' },
            { key: 'vehicle_id', label: 'Vehicle ID', type: 'number' },
            { key: 'pickup_location', label: 'Pickup Loc', type: 'number' },
            { key: 'return_location', label: 'Return Loc', type: 'number' },
            { key: 'pickup_date', label: 'Pickup', type: 'date' },
            { key: 'return_date', label: 'Return', type: 'date' },
            { key: 'status', label: 'Status', type: 'select', options: ['confirmed','active','completed','cancelled','no_show'] },
            { key: 'total_cost', label: 'Total Cost', type: 'decimal' },
        ],
    },
    payments: {
        endpoint: '/api/payments',
        label: 'Payments',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'reservation_id', label: 'Reservation ID', type: 'number' },
            { key: 'amount', label: 'Amount', type: 'decimal' },
            { key: 'payment_method', label: 'Method', type: 'select', options: ['credit_card','debit_card','cash'] },
            { key: 'payment_date', label: 'Date', type: 'date' },
            { key: 'status', label: 'Status', type: 'select', options: ['completed','pending','refunded','failed'] },
        ],
    },
    maintenance: {
        endpoint: '/api/maintenance',
        label: 'Maintenance Records',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'vehicle_id', label: 'Vehicle ID', type: 'number' },
            { key: 'maintenance_type', label: 'Type', type: 'select', options: ['oil_change','tire_rotation','brake_service','general_inspection','engine_repair','body_repair','transmission','ac_service','battery_replacement'] },
            { key: 'description', label: 'Description', type: 'text' },
            { key: 'cost', label: 'Cost', type: 'decimal' },
            { key: 'maintenance_date', label: 'Date', type: 'date' },
            { key: 'mileage_at_service', label: 'Mileage', type: 'number' },
            { key: 'completed', label: 'Completed', type: 'boolean' },
        ],
    },
    reviews: {
        endpoint: '/api/reviews',
        label: 'Reviews',
        columns: [
            { key: 'id', label: 'ID' },
            { key: 'reservation_id', label: 'Reservation ID', type: 'number' },
            { key: 'rating', label: 'Rating', type: 'select', options: ['1','2','3','4','5'] },
            { key: 'comment', label: 'Comment', type: 'text' },
            { key: 'review_date', label: 'Date', type: 'date' },
        ],
    },
};

const PAGE_SIZE = 25;
let currentPage = 0;
let currentData = [];
let filteredData = [];
let currentConfig = null;
let sortKey = null;
let sortDir = 'asc';
let searchQuery = '';
let advancedFilters = {}; // { key: { min, max } } for number/decimal/date, { key: value } for select
let advancedOpen = false;

async function renderTable(container, config) {
    currentConfig = config;
    currentPage = 0;
    sortKey = null;
    sortDir = 'asc';
    searchQuery = '';
    advancedFilters = {};
    advancedOpen = false;
    container.innerHTML = '<div class="loading">Loading...</div>';

    try {
        currentData = await api.get(config.endpoint);
    } catch (e) {
        container.innerHTML = `<div class="loading" style="color:var(--danger)">Error: ${e.message}</div>`;
        return;
    }

    applyFiltersAndSort();
    renderPage(container);
}

function applyFiltersAndSort() {
    const q = searchQuery.toLowerCase().trim();

    filteredData = currentData.filter(row => {
        // global text search across all columns
        if (q) {
            const match = Object.values(row).some(v =>
                String(v ?? '').toLowerCase().includes(q)
            );
            if (!match) return false;
        }

        // advanced filters
        for (const [key, filter] of Object.entries(advancedFilters)) {
            const col = currentConfig.columns.find(c => c.key === key);
            if (!col) continue;
            const val = row[key];

            if (col.type === 'select' || col.type === 'boolean') {
                if (filter.value && String(val) !== filter.value) return false;
            } else if (col.type === 'date') {
                if (filter.min && String(val || '') < filter.min) return false;
                if (filter.max && String(val || '') > filter.max) return false;
            } else if (col.type === 'number' || col.type === 'decimal') {
                const num = Number(val);
                if (filter.min !== '' && filter.min != null && num < Number(filter.min)) return false;
                if (filter.max !== '' && filter.max != null && num > Number(filter.max)) return false;
            }
        }

        return true;
    });

    if (sortKey) {
        filteredData.sort((a, b) => {
            let va = a[sortKey], vb = b[sortKey];
            if (va == null) va = '';
            if (vb == null) vb = '';
            const na = Number(va), nb = Number(vb);
            if (!isNaN(na) && !isNaN(nb) && va !== '' && vb !== '') {
                return sortDir === 'asc' ? na - nb : nb - na;
            }
            const sa = String(va).toLowerCase(), sb = String(vb).toLowerCase();
            if (sa < sb) return sortDir === 'asc' ? -1 : 1;
            if (sa > sb) return sortDir === 'asc' ? 1 : -1;
            return 0;
        });
    }
}

function handleSort(key) {
    if (sortKey === key) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
        sortKey = key;
        sortDir = 'asc';
    }
    currentPage = 0;
    applyFiltersAndSort();
    renderPage(document.getElementById('content'));
}

function handleSearch(value) {
    searchQuery = value;
    currentPage = 0;
    applyFiltersAndSort();
    renderPage(document.getElementById('content'));
    // restore focus and cursor position
    const el = document.getElementById('global-search');
    if (el) { el.focus(); el.selectionStart = el.selectionEnd = value.length; }
}

function toggleAdvanced() {
    advancedOpen = !advancedOpen;
    renderPage(document.getElementById('content'));
}

function updateAdvancedFilter(key, field, value) {
    if (!advancedFilters[key]) advancedFilters[key] = {};
    advancedFilters[key][field] = value;
    currentPage = 0;
    applyFiltersAndSort();
    renderPage(document.getElementById('content'));
}

function clearAllFilters() {
    searchQuery = '';
    advancedFilters = {};
    currentPage = 0;
    applyFiltersAndSort();
    renderPage(document.getElementById('content'));
}

function hasActiveFilters() {
    if (searchQuery.trim()) return true;
    return Object.values(advancedFilters).some(f =>
        (f.value && f.value !== '') || (f.min != null && f.min !== '') || (f.max != null && f.max !== '')
    );
}

function buildAdvancedPanel() {
    const cols = currentConfig.columns.filter(c => c.key !== 'id' && c.type);
    const groups = [];

    // select/boolean filters
    const selectCols = cols.filter(c => c.type === 'select' || c.type === 'boolean');
    if (selectCols.length) {
        groups.push(`<div class="adv-group">
            <div class="adv-group-title">Status / Type</div>
            <div class="adv-row">
                ${selectCols.map(c => {
                    const cur = (advancedFilters[c.key] || {}).value || '';
                    const opts = c.type === 'boolean'
                        ? ['true', 'false']
                        : c.options;
                    const labels = c.type === 'boolean'
                        ? { 'true': 'Yes', 'false': 'No' }
                        : null;
                    return `<div class="adv-field">
                        <label>${c.label}</label>
                        <select onchange="updateAdvancedFilter('${c.key}','value',this.value)">
                            <option value="">All</option>
                            ${opts.map(o => `<option value="${o}" ${cur === String(o) ? 'selected' : ''}>${labels ? labels[o] : o}</option>`).join('')}
                        </select>
                    </div>`;
                }).join('')}
            </div>
        </div>`);
    }

    // date range filters
    const dateCols = cols.filter(c => c.type === 'date');
    if (dateCols.length) {
        groups.push(`<div class="adv-group">
            <div class="adv-group-title">Date Ranges</div>
            <div class="adv-row">
                ${dateCols.map(c => {
                    const f = advancedFilters[c.key] || {};
                    return `<div class="adv-field adv-field-range">
                        <label>${c.label}</label>
                        <div class="range-inputs">
                            <input type="date" value="${f.min || ''}" onchange="updateAdvancedFilter('${c.key}','min',this.value)" title="From">
                            <span class="range-sep">to</span>
                            <input type="date" value="${f.max || ''}" onchange="updateAdvancedFilter('${c.key}','max',this.value)" title="To">
                        </div>
                    </div>`;
                }).join('')}
            </div>
        </div>`);
    }

    // number/decimal range filters
    const numCols = cols.filter(c => c.type === 'number' || c.type === 'decimal');
    if (numCols.length) {
        groups.push(`<div class="adv-group">
            <div class="adv-group-title">Numeric Ranges</div>
            <div class="adv-row">
                ${numCols.map(c => {
                    const f = advancedFilters[c.key] || {};
                    const step = c.type === 'decimal' ? '0.01' : '1';
                    return `<div class="adv-field adv-field-range">
                        <label>${c.label}</label>
                        <div class="range-inputs">
                            <input type="number" step="${step}" placeholder="Min" value="${f.min ?? ''}" onchange="updateAdvancedFilter('${c.key}','min',this.value)">
                            <span class="range-sep">to</span>
                            <input type="number" step="${step}" placeholder="Max" value="${f.max ?? ''}" onchange="updateAdvancedFilter('${c.key}','max',this.value)">
                        </div>
                    </div>`;
                }).join('')}
            </div>
        </div>`);
    }

    return groups.join('');
}

function renderPage(container) {
    const config = currentConfig;
    const totalPages = Math.ceil(filteredData.length / PAGE_SIZE);
    const pageData = filteredData.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

    const visibleCols = config.columns.filter(c => c.key !== 'created_at');

    const countLabel = filteredData.length !== currentData.length
        ? `${filteredData.length} / ${currentData.length}`
        : `${currentData.length}`;

    const activeFilters = hasActiveFilters();
    const advChevron = advancedOpen ? '&#9650;' : '&#9660;';

    let html = `
        <div class="table-header">
            <h2>${config.label} <span style="color:var(--text-muted);font-size:14px;font-weight:400">(${countLabel})</span></h2>
            <button class="btn btn-primary" onclick="openCreateModal()">+ New</button>
        </div>
        <div class="filter-bar">
            <div class="filter-bar-main">
                <input type="text" id="global-search" class="search-input" placeholder="Search all columns..." value="${escHtml(searchQuery)}" oninput="handleSearch(this.value)">
                <button class="btn btn-secondary btn-sm adv-toggle ${advancedOpen ? 'adv-toggle-active' : ''}" onclick="toggleAdvanced()">Advanced ${advChevron}</button>
                ${activeFilters ? `<button class="btn btn-danger btn-sm" onclick="clearAllFilters()">Clear filters</button>` : ''}
            </div>
            ${advancedOpen ? `<div class="adv-panel">${buildAdvancedPanel()}</div>` : ''}
        </div>
        <table>
            <thead>
                <tr>
                    ${visibleCols.map(c => {
                        const arrow = sortKey === c.key ? (sortDir === 'asc' ? ' &#9650;' : ' &#9660;') : ' <span class="sort-hint">&#8693;</span>';
                        const cls = sortKey === c.key ? 'th-sortable th-sorted' : 'th-sortable';
                        return `<th class="${cls}" onclick="handleSort('${c.key}')">${c.label}${arrow}</th>`;
                    }).join('')}
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${pageData.length === 0 ? `<tr><td colspan="${visibleCols.length + 1}" style="text-align:center;padding:24px;color:var(--text-muted)">No matching records</td></tr>` : pageData.map(row => `<tr>
                    ${visibleCols.map(c => `<td title="${escHtml(String(row[c.key] ?? ''))}">${escHtml(formatCell(row[c.key], c))}</td>`).join('')}
                    <td class="actions">
                        <button class="btn btn-secondary btn-sm" onclick='openEditModal(${row.id})'>Edit</button>
                        <button class="btn btn-danger btn-sm" onclick='deleteRow(${row.id})'>Del</button>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>
        <div class="pagination">
            <button class="btn btn-secondary btn-sm" onclick="prevPage()" ${currentPage === 0 ? 'disabled' : ''}>Prev</button>
            <span>Page ${currentPage + 1} of ${totalPages || 1}</span>
            <button class="btn btn-secondary btn-sm" onclick="nextPage()" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>Next</button>
        </div>`;

    container.innerHTML = html;
}

function formatCell(val, col) {
    if (val === null || val === undefined) return '';
    if (col.type === 'decimal') return '$' + Number(val).toFixed(2);
    if (col.type === 'boolean') return val ? 'Yes' : 'No';
    return String(val);
}

function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function prevPage() {
    if (currentPage > 0) { currentPage--; renderPage(document.getElementById('content')); }
}

function nextPage() {
    const totalPages = Math.ceil(filteredData.length / PAGE_SIZE);
    if (currentPage < totalPages - 1) { currentPage++; renderPage(document.getElementById('content')); }
}

// ── Modal CRUD ──────────────────────────────────
function openCreateModal() {
    const config = currentConfig;
    const editableFields = config.columns.filter(c => c.key !== 'id' && c.type);
    document.getElementById('modal-title').textContent = `New ${config.label.replace(/s$/,'')}`;
    document.getElementById('modal-form').innerHTML = editableFields.map(c => buildField(c, '')).join('');
    document.getElementById('modal-save').onclick = () => saveNew();
    document.getElementById('modal').classList.remove('hidden');
}

function openEditModal(id) {
    const config = currentConfig;
    const row = currentData.find(r => r.id === id);
    if (!row) return;
    const editableFields = config.columns.filter(c => c.key !== 'id' && c.type);
    document.getElementById('modal-title').textContent = `Edit ${config.label.replace(/s$/,'')} #${id}`;
    document.getElementById('modal-form').innerHTML = editableFields.map(c => buildField(c, row[c.key])).join('');
    document.getElementById('modal-save').onclick = () => saveEdit(id);
    document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

function buildField(col, value) {
    const val = value ?? '';
    if (col.type === 'select') {
        return `<div class="form-group">
            <label>${col.label}</label>
            <select name="${col.key}">
                ${col.options.map(o => `<option value="${o}" ${String(val) === String(o) ? 'selected' : ''}>${o}</option>`).join('')}
            </select>
        </div>`;
    }
    if (col.type === 'boolean') {
        return `<div class="form-group">
            <label>${col.label}</label>
            <select name="${col.key}">
                <option value="true" ${val ? 'selected' : ''}>Yes</option>
                <option value="false" ${!val ? 'selected' : ''}>No</option>
            </select>
        </div>`;
    }
    const inputType = col.type === 'decimal' ? 'number' : (col.type || 'text');
    const step = col.type === 'decimal' ? 'step="0.01"' : '';
    return `<div class="form-group">
        <label>${col.label}</label>
        <input type="${inputType}" name="${col.key}" value="${escHtml(String(val))}" ${step}>
    </div>`;
}

function getFormData() {
    const form = document.getElementById('modal-form');
    const data = {};
    const editableFields = currentConfig.columns.filter(c => c.key !== 'id' && c.type);
    for (const col of editableFields) {
        const el = form.querySelector(`[name="${col.key}"]`);
        if (!el) continue;
        let v = el.value;
        if (col.type === 'number') v = v ? parseInt(v) : null;
        else if (col.type === 'decimal') v = v ? v : null;
        else if (col.type === 'boolean') v = v === 'true';
        else if (col.type === 'select' && col.key === 'rating') v = parseInt(v);
        else if (v === '') v = null;
        data[col.key] = v;
    }
    return data;
}

async function saveNew() {
    try {
        await api.post(currentConfig.endpoint, getFormData());
        closeModal();
        await renderTable(document.getElementById('content'), currentConfig);
    } catch (e) { alert('Error: ' + e.message); }
}

async function saveEdit(id) {
    try {
        await api.put(`${currentConfig.endpoint}/${id}`, getFormData());
        closeModal();
        await renderTable(document.getElementById('content'), currentConfig);
    } catch (e) { alert('Error: ' + e.message); }
}

async function deleteRow(id) {
    if (!confirm(`Delete ${currentConfig.label.replace(/s$/,'')} #${id}?`)) return;
    try {
        await api.del(`${currentConfig.endpoint}/${id}`);
        await renderTable(document.getElementById('content'), currentConfig);
    } catch (e) { alert('Error: ' + e.message); }
}

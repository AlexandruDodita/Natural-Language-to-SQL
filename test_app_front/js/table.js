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
let currentConfig = null;

async function renderTable(container, config) {
    currentConfig = config;
    currentPage = 0;
    container.innerHTML = '<div class="loading">Loading...</div>';

    try {
        currentData = await api.get(config.endpoint);
    } catch (e) {
        container.innerHTML = `<div class="loading" style="color:var(--danger)">Error: ${e.message}</div>`;
        return;
    }

    renderPage(container);
}

function renderPage(container) {
    const config = currentConfig;
    const totalPages = Math.ceil(currentData.length / PAGE_SIZE);
    const pageData = currentData.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

    const visibleCols = config.columns.filter(c => c.key !== 'created_at');

    let html = `
        <div class="table-header">
            <h2>${config.label} <span style="color:var(--text-muted);font-size:14px;font-weight:400">(${currentData.length})</span></h2>
            <button class="btn btn-primary" onclick="openCreateModal()">+ New</button>
        </div>
        <table>
            <thead><tr>
                ${visibleCols.map(c => `<th>${c.label}</th>`).join('')}
                <th>Actions</th>
            </tr></thead>
            <tbody>
                ${pageData.map(row => `<tr>
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
    const totalPages = Math.ceil(currentData.length / PAGE_SIZE);
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

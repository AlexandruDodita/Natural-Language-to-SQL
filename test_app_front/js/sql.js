let sqlHistory = [];

async function renderSqlRunner(container) {
    container.innerHTML = `
        <div class="sql-runner">
            <div class="sql-editor-wrap">
                <div class="sql-toolbar">
                    <span class="sql-title">SQL Query Runner</span>
                    <div class="sql-toolbar-actions">
                        <button class="btn btn-secondary btn-sm" onclick="sqlClear()">Clear</button>
                        <button class="btn btn-primary" id="sql-run-btn" onclick="sqlRun()">Run (Ctrl+Enter)</button>
                    </div>
                </div>
                <textarea id="sql-input" class="sql-input" placeholder="SELECT * FROM locations LIMIT 10;" spellcheck="false"></textarea>
            </div>
            <div id="sql-result" class="sql-result">
                <div class="sql-placeholder">Results will appear here</div>
            </div>
            <div id="sql-history" class="sql-history-panel"></div>
        </div>`;

    document.getElementById('sql-input').addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            sqlRun();
        }
        // Tab inserts spaces
        if (e.key === 'Tab') {
            e.preventDefault();
            const ta = e.target;
            const start = ta.selectionStart;
            ta.value = ta.value.substring(0, start) + '  ' + ta.value.substring(ta.selectionEnd);
            ta.selectionStart = ta.selectionEnd = start + 2;
        }
    });

    renderHistory();
}

async function sqlRun() {
    const input = document.getElementById('sql-input');
    const resultDiv = document.getElementById('sql-result');
    const query = input.value.trim();
    if (!query) return;

    const btn = document.getElementById('sql-run-btn');
    btn.disabled = true;
    btn.textContent = 'Running...';
    resultDiv.innerHTML = '<div class="sql-placeholder">Executing...</div>';

    try {
        const res = await fetch(api.url + '/api/sql', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
        });
        const data = await res.json();

        if (data.error) {
            resultDiv.innerHTML = `<div class="sql-error">${escHtml(data.error)}</div>`;
            addHistory(query, false, data.error);
        } else {
            resultDiv.innerHTML = buildResultTable(data);
            addHistory(query, true, `${data.row_count} rows in ${data.duration_ms.toFixed(1)}ms`);
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="sql-error">Network error: ${escHtml(e.message)}</div>`;
        addHistory(query, false, e.message);
    }

    btn.disabled = false;
    btn.textContent = 'Run (Ctrl+Enter)';
}

function buildResultTable(data) {
    if (data.columns.length === 0) {
        return `<div class="sql-meta">Query executed successfully. 0 rows returned. (${data.duration_ms.toFixed(1)}ms)</div>`;
    }

    const capped = data.rows.length > 500;
    const rows = capped ? data.rows.slice(0, 500) : data.rows;

    return `
        <div class="sql-meta">${data.row_count} row${data.row_count !== 1 ? 's' : ''} returned in ${data.duration_ms.toFixed(1)}ms${capped ? ' (showing first 500)' : ''}</div>
        <div class="sql-table-wrap">
            <table class="sql-table">
                <thead><tr>${data.columns.map(c => `<th>${escHtml(c)}</th>`).join('')}</tr></thead>
                <tbody>${rows.map(row =>
                    `<tr>${row.map(cell => {
                        const val = cell === null ? '<span class="sql-null">NULL</span>' : escHtml(String(cell));
                        return `<td title="${cell === null ? 'NULL' : escHtml(String(cell))}">${val}</td>`;
                    }).join('')}</tr>`
                ).join('')}</tbody>
            </table>
        </div>`;
}

function addHistory(query, success, info) {
    sqlHistory.unshift({ query, success, info, time: new Date() });
    if (sqlHistory.length > 50) sqlHistory.pop();
    renderHistory();
}

function renderHistory() {
    const el = document.getElementById('sql-history');
    if (!el) return;
    if (sqlHistory.length === 0) {
        el.innerHTML = '';
        return;
    }

    el.innerHTML = `
        <div class="sql-history-title">History</div>
        ${sqlHistory.map((h, i) => `
            <div class="sql-history-item ${h.success ? '' : 'sql-history-err'}" onclick="sqlLoadHistory(${i})">
                <code>${escHtml(h.query.length > 80 ? h.query.slice(0, 80) + '...' : h.query)}</code>
                <span class="sql-history-meta">${h.info}</span>
            </div>
        `).join('')}`;
}

function sqlLoadHistory(idx) {
    const h = sqlHistory[idx];
    if (h) document.getElementById('sql-input').value = h.query;
}

function sqlClear() {
    document.getElementById('sql-input').value = '';
    document.getElementById('sql-result').innerHTML = '<div class="sql-placeholder">Results will appear here</div>';
}

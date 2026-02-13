document.addEventListener('DOMContentLoaded', () => {
    const content = document.getElementById('content');
    const tabs = document.querySelectorAll('.tab');

    async function switchTab(tabName) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));

        if (tabName === 'dashboard') {
            await renderDashboard(content);
        } else {
            const config = TABLES[tabName];
            if (config) await renderTable(content, config);
        }
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    switchTab('dashboard');
});

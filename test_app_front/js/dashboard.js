let revenueChart = null;

async function renderDashboard(container) {
    container.innerHTML = '<div class="loading">Loading dashboard...</div>';

    try {
        const [summary, revenue, topVehicles, clientStats] = await Promise.all([
            api.get('/api/dashboard/summary'),
            api.get('/api/dashboard/revenue-by-month'),
            api.get('/api/dashboard/top-vehicles'),
            api.get('/api/dashboard/client-stats'),
        ]);

        const totalRev = Number(summary.total_revenue).toLocaleString('en-US', { minimumFractionDigits: 2 });

        container.innerHTML = `
            <div class="cards">
                <div class="card">
                    <h3>Total Revenue</h3>
                    <span class="card-value">$${totalRev}</span>
                </div>
                <div class="card">
                    <h3>Avg Rating</h3>
                    <span class="card-value">${summary.avg_rating.toFixed(2)} / 5</span>
                </div>
                <div class="card">
                    <h3>Active Reservations</h3>
                    <span class="card-value">${summary.active_reservations}</span>
                </div>
                <div class="card">
                    <h3>Total Clients</h3>
                    <span class="card-value">${summary.total_clients}</span>
                </div>
                <div class="card">
                    <h3>Vehicles</h3>
                    <span class="card-value">${summary.total_vehicles}</span>
                </div>
                <div class="card">
                    <h3>Reservations</h3>
                    <span class="card-value">${summary.total_reservations}</span>
                </div>
                <div class="card">
                    <h3>Payments</h3>
                    <span class="card-value">${summary.total_payments}</span>
                </div>
                <div class="card">
                    <h3>Reviews</h3>
                    <span class="card-value">${summary.total_reviews}</span>
                </div>
            </div>
            <div class="chart-container">
                <h3>Monthly Revenue</h3>
                <canvas id="revenueChart"></canvas>
            </div>
            <div class="dashboard-grid">
                <div class="dashboard-table">
                    <h3>Top Vehicles by Rentals</h3>
                    <table>
                        <thead><tr><th>Vehicle</th><th>Rentals</th><th>Revenue</th><th>Avg Rating</th></tr></thead>
                        <tbody>
                            ${topVehicles.map(v => `<tr>
                                <td>${v.make} ${v.model}</td>
                                <td>${v.rental_count}</td>
                                <td>$${Number(v.total_revenue).toFixed(2)}</td>
                                <td>${v.avg_rating ? v.avg_rating.toFixed(1) : '-'}</td>
                            </tr>`).join('')}
                        </tbody>
                    </table>
                </div>
                <div class="dashboard-table">
                    <h3>Top Clients by Spending</h3>
                    <table>
                        <thead><tr><th>Client</th><th>Reservations</th><th>Total Spent</th><th>Avg Rating</th></tr></thead>
                        <tbody>
                            ${clientStats.map(c => `<tr>
                                <td>${c.first_name} ${c.last_name}</td>
                                <td>${c.reservation_count}</td>
                                <td>$${Number(c.total_spent).toFixed(2)}</td>
                                <td>${c.avg_rating ? c.avg_rating.toFixed(1) : '-'}</td>
                            </tr>`).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        // Revenue chart
        if (revenueChart) revenueChart.destroy();
        const ctx = document.getElementById('revenueChart');
        if (ctx) {
            const labels = revenue.map(r => r.month ? r.month.substring(0, 7) : '');
            revenueChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        label: 'Revenue ($)',
                        data: revenue.map(r => Number(r.revenue)),
                        backgroundColor: '#4f46e5',
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, ticks: { callback: v => '$' + v.toLocaleString() } },
                        x: { ticks: { maxRotation: 45, font: { size: 10 } } }
                    }
                }
            });
        }
    } catch (e) {
        container.innerHTML = `<div class="loading" style="color:var(--danger)">Error loading dashboard: ${e.message}</div>`;
    }
}

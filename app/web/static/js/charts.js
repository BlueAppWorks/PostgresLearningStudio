/* Postgres Learning Studio - Chart.js helpers */

function createTimeSeriesChart(canvasId, label, color, yLabel) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: color + '33',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            scales: {
                x: {
                    title: { display: true, text: 'Elapsed (s)' },
                    ticks: { color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    title: { display: true, text: yLabel },
                    ticks: { color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    beginAtZero: true,
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function addChartPoint(chart, x, y) {
    chart.data.labels.push(x);
    chart.data.datasets[0].data.push(y);
    chart.update('none');
}

/* ============================================================
   Wait Event Stacked Area Chart
   ============================================================ */

var WAIT_EVENT_COLORS = {
    'IO':        { border: '#e74c3c', bg: 'rgba(231, 76, 60, 0.45)' },
    'LWLock':    { border: '#f39c12', bg: 'rgba(243, 156, 18, 0.45)' },
    'Lock':      { border: '#e91e63', bg: 'rgba(233, 30, 99, 0.45)' },
    'Client':    { border: '#3498db', bg: 'rgba(52, 152, 219, 0.45)' },
    'Activity':  { border: '#2ecc71', bg: 'rgba(46, 204, 113, 0.45)' },
    'IPC':       { border: '#9b59b6', bg: 'rgba(155, 89, 182, 0.45)' },
    'BufferPin': { border: '#1abc9c', bg: 'rgba(26, 188, 156, 0.45)' },
    'Extension': { border: '#95a5a6', bg: 'rgba(149, 165, 166, 0.45)' },
    'Timeout':   { border: '#fd7e14', bg: 'rgba(253, 126, 20, 0.45)' },
};

var WAIT_EVENT_FALLBACK = { border: '#bdc3c7', bg: 'rgba(189, 195, 199, 0.4)' };

function createWaitEventChart(canvasId, waitData) {
    var ctx = document.getElementById(canvasId).getContext('2d');
    var datasets = [];
    var eventTypes = Object.keys(waitData.event_types);

    eventTypes.forEach(function(eventType) {
        var colors = WAIT_EVENT_COLORS[eventType] || WAIT_EVENT_FALLBACK;
        datasets.push({
            label: eventType,
            data: waitData.event_types[eventType],
            borderColor: colors.border,
            backgroundColor: colors.bg,
            borderWidth: 1.5,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHitRadius: 8,
        });
    });

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: waitData.timestamps,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    title: { display: true, text: 'Elapsed (s)' },
                    ticks: { color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    title: { display: true, text: 'Waiting Processes' },
                    ticks: { color: '#aaa', stepSize: 1 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    beginAtZero: true,
                    stacked: true,
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#ccc',
                        usePointStyle: true,
                        pointStyle: 'rectRounded',
                        padding: 15,
                    },
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    filter: function(item) { return item.raw > 0; },
                    callbacks: {
                        title: function(items) {
                            return 'Elapsed: ' + items[0].label + 's';
                        },
                        footer: function(items) {
                            var total = items.reduce(function(sum, item) {
                                return sum + item.raw;
                            }, 0);
                            return 'Total waiting: ' + total;
                        },
                    },
                },
            },
        },
    });
}

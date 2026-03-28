/* Postgres Learning Studio - SSE client for benchmark progress */

let tpsChart = null;
let latencyChart = null;

function initBenchmarkProgress(runId, currentStatus) {
    tpsChart = createTimeSeriesChart('tpsChart', 'TPS', '#0d6efd', 'TPS');
    latencyChart = createTimeSeriesChart('latencyChart', 'Latency', '#ffc107', 'ms');

    if (currentStatus === 'running') {
        startSSE(runId);
    } else if (currentStatus === 'completed' || currentStatus === 'failed') {
        loadExistingData(runId);
    }
}

function startSSE(runId) {
    const evtSource = new EventSource('/benchmark/run/' + runId + '/stream');

    evtSource.addEventListener('progress', function(e) {
        const data = JSON.parse(e.data);
        addChartPoint(tpsChart, data.elapsed_sec, data.tps);
        addChartPoint(latencyChart, data.elapsed_sec, data.latency_avg_ms);
        addProgressRow(data);
    });

    evtSource.addEventListener('complete', function(e) {
        const data = JSON.parse(e.data);
        evtSource.close();
        showCompletion(data);
    });

    evtSource.addEventListener('error', function(e) {
        if (typeof e.data === 'string') {
            console.error('SSE error:', e.data);
        }
        evtSource.close();
        const badge = document.getElementById('statusBadge');
        badge.textContent = 'disconnected';
        badge.className = 'badge bg-secondary';
    });
}

function loadExistingData(runId) {
    // Fetch existing progress data via API-style call
    fetch('/benchmark/run/' + runId + '/stream')
        .then(function() {
            // SSE will send events then close
        })
        .catch(function(err) {
            console.error('Error loading data:', err);
        });

    // For completed runs, just start SSE which will send all data then complete
    startSSE(runId);
}

function addProgressRow(data) {
    const tbody = document.getElementById('progressTable');
    const tr = document.createElement('tr');
    tr.innerHTML =
        '<td>' + data.elapsed_sec + '</td>' +
        '<td>' + data.tps.toFixed(1) + '</td>' +
        '<td>' + data.latency_avg_ms.toFixed(2) + '</td>' +
        '<td>' + (data.latency_stddev || 0).toFixed(2) + '</td>';
    tbody.appendChild(tr);

    // Auto-scroll
    const container = tbody.closest('.table-responsive');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function showCompletion(data) {
    const badge = document.getElementById('statusBadge');
    badge.classList.remove('progress-pulse');

    if (data.status === 'completed') {
        badge.textContent = 'completed';
        badge.className = 'badge bg-success';
    } else {
        badge.textContent = 'failed';
        badge.className = 'badge bg-danger';
    }

    // Show summary
    const summary = data.summary || {};
    document.getElementById('summaryTps').textContent =
        summary.tps ? summary.tps.toFixed(1) : '-';
    document.getElementById('summaryLatency').textContent =
        summary.latency_avg_ms ? summary.latency_avg_ms.toFixed(2) : '-';
    document.getElementById('summaryTxns').textContent =
        summary.num_transactions || '-';
    document.getElementById('summaryFailed').textContent =
        summary.num_failed !== undefined ? summary.num_failed : '-';

    document.getElementById('summarySection').style.display = '';
}

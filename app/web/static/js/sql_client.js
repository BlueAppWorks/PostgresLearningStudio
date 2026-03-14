/* Postgres Learning Studio - SQL Client */

(function() {
    var editor = document.getElementById('sqlEditor');
    var resultsArea = document.getElementById('resultsArea');
    var resultsHeader = document.getElementById('resultsHeader');
    var resultsInfo = document.getElementById('resultsInfo');
    var resultsTiming = document.getElementById('resultsTiming');
    var resultsBody = document.getElementById('resultsBody');
    var loadingIndicator = document.getElementById('loadingIndicator');
    var btnExecute = document.getElementById('btnExecute');
    var referencePanel = document.getElementById('referencePanel');
    var referenceTitle = document.getElementById('referenceTitle');
    var referenceCode = document.getElementById('referenceCode');
    var execHint = document.getElementById('execHint');

    // ── Keyboard shortcuts ──

    editor.addEventListener('keydown', function(e) {
        // Ctrl+Enter or Cmd+Enter → execute
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            executeSQL('plain');
            return;
        }
        // Tab → insert 2 spaces
        if (e.key === 'Tab') {
            e.preventDefault();
            var start = this.selectionStart;
            var end = this.selectionEnd;
            this.value = this.value.substring(0, start) + '  ' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 2;
        }
    });

    // ── Sample script loading ──

    document.querySelectorAll('.sample-item').forEach(function(item) {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            var sampleId = this.getAttribute('data-sample-id');
            loadSample(sampleId);
        });
    });

    function loadSample(sampleId) {
        fetch('/sql/samples/' + sampleId)
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.sql) {
                    // Show sample in reference panel
                    referenceTitle.textContent = data.title || 'Sample Script';
                    referenceCode.textContent = data.sql;
                    referencePanel.style.display = 'block';

                    // Clear editor and results
                    editor.value = '';
                    editor.placeholder = 'Copy SQL from the reference panel, or type your own query here.';
                    resultsArea.style.display = 'none';
                    editor.focus();
                }
            })
            .catch(function(err) {
                console.error('Failed to load sample:', err);
            });
    }

    // Close reference panel
    window.closeReference = function() {
        referencePanel.style.display = 'none';
        editor.placeholder = "SELECT * FROM pg_stat_activity;  (or try \\dt, \\d tablename ...)";
    };

    // Copy a block from reference to editor
    window.copyToEditor = function() {
        var sel = window.getSelection().toString().trim();
        if (sel) {
            // Append selected text to editor
            if (editor.value.trim()) {
                editor.value += '\n\n' + sel;
            } else {
                editor.value = sel;
            }
            editor.focus();
        }
    };

    // ── SQL execution (supports selection-based partial execution) ──

    window.executeSQL = function(mode) {
        // Use selected text if any, otherwise use full editor content
        var sql;
        var selStart = editor.selectionStart;
        var selEnd = editor.selectionEnd;

        if (selStart !== selEnd) {
            sql = editor.value.substring(selStart, selEnd).trim();
        } else {
            sql = editor.value.trim();
        }

        if (!sql) return;

        // Update hint to show what we're executing
        if (selStart !== selEnd) {
            execHint.textContent = 'Executing selection...';
        } else {
            execHint.textContent = '';
        }

        // Show loading, hide results
        loadingIndicator.style.display = 'block';
        resultsArea.style.display = 'none';
        btnExecute.disabled = true;

        var targetSelect = document.getElementById('targetSelect');
        var targetId = targetSelect ? targetSelect.value : null;

        fetch('/sql/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sql: sql, mode: mode, target_id: targetId })
        })
        .then(function(res) {
            return res.json().then(function(data) {
                return { status: res.status, data: data };
            });
        })
        .then(function(result) {
            loadingIndicator.style.display = 'none';
            btnExecute.disabled = false;
            execHint.textContent = '';
            renderResult(result.data, result.status);
        })
        .catch(function(err) {
            loadingIndicator.style.display = 'none';
            btnExecute.disabled = false;
            execHint.textContent = '';
            renderError('Network error: ' + err.message);
        });
    };

    // ── Result rendering ──

    function renderResult(data, status) {
        resultsArea.style.display = 'block';

        // Error
        if (data.error) {
            resultsInfo.innerHTML = '<span class="text-danger">Error</span>';
            resultsTiming.textContent = data.execution_time_ms != null
                ? data.execution_time_ms + ' ms' : '';
            resultsBody.innerHTML =
                '<div class="alert alert-danger m-3" style="white-space: pre-wrap; font-family: monospace;">'
                + escapeHtml(data.error) + '</div>';
            return;
        }

        // Success message (DDL/DML)
        if (data.message) {
            resultsInfo.textContent = data.message;
            resultsTiming.textContent = data.execution_time_ms + ' ms';
            resultsBody.innerHTML =
                '<div class="alert alert-success m-3">' + escapeHtml(data.message) + '</div>';
            return;
        }

        // Table result
        if (data.columns && data.rows) {
            var info = data.row_count + ' row(s)';
            if (data.truncated) info += ' (truncated to 500)';
            if (data.meta_description) info = data.meta_description;
            resultsInfo.textContent = info;
            resultsTiming.textContent = data.execution_time_ms + ' ms';

            // Detect if this is an EXPLAIN result (single text column)
            if (isExplainResult(data)) {
                renderExplain(data);
            } else {
                renderTable(data.columns, data.rows);
            }
        }
    }

    function isExplainResult(data) {
        if (!data.columns || data.columns.length !== 1) return false;
        var col = data.columns[0].toLowerCase();
        return col === 'query plan' || col === 'query_plan' || col === 'explain';
    }

    function renderExplain(data) {
        var text = data.rows.map(function(r) { return r[0]; }).join('\n');
        resultsBody.innerHTML =
            '<div class="sql-explain p-3"><pre><code>' + escapeHtml(text) + '</code></pre></div>';
    }

    function renderTable(columns, rows) {
        if (rows.length === 0) {
            resultsBody.innerHTML = '<div class="text-muted p-3">No rows returned.</div>';
            return;
        }

        var html = '<div class="table-responsive sql-results">';
        html += '<table class="table table-sm table-hover table-striped mb-0">';
        html += '<thead><tr>';
        columns.forEach(function(col) {
            html += '<th>' + escapeHtml(col) + '</th>';
        });
        html += '</tr></thead><tbody>';

        rows.forEach(function(row) {
            html += '<tr>';
            row.forEach(function(val) {
                if (val === null) {
                    html += '<td class="text-muted fst-italic">NULL</td>';
                } else {
                    html += '<td>' + escapeHtml(val) + '</td>';
                }
            });
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        resultsBody.innerHTML = html;
    }

    function renderError(msg) {
        resultsArea.style.display = 'block';
        resultsInfo.innerHTML = '<span class="text-danger">Error</span>';
        resultsTiming.textContent = '';
        resultsBody.innerHTML =
            '<div class="alert alert-danger m-3">' + escapeHtml(msg) + '</div>';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.toString()
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();

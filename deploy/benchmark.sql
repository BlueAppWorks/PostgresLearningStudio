-- ============================================================
-- Postgres Learning Studio - Benchmark Queue & Results Module
-- Queue-based communication between Streamlit UI and SPCS container.
-- ============================================================

-- ============================================================
-- Queue table (Streamlit -> Application)
-- ============================================================
CREATE TABLE IF NOT EXISTS app_config.benchmark_queue (
    queue_id BIGINT AUTOINCREMENT PRIMARY KEY,
    parameters VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'queued',
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    picked_at TIMESTAMP_NTZ,
    completed_at TIMESTAMP_NTZ,
    result VARCHAR
);

GRANT SELECT ON TABLE app_config.benchmark_queue TO APPLICATION ROLE app_user;

-- ============================================================
-- Results table (Application -> Streamlit)
-- ============================================================
CREATE TABLE IF NOT EXISTS app_config.benchmark_results (
    result_id BIGINT AUTOINCREMENT PRIMARY KEY,
    queue_id BIGINT,
    run_name VARCHAR,
    tool VARCHAR DEFAULT 'pgbench',
    parameters VARCHAR,
    started_at TIMESTAMP_NTZ,
    finished_at TIMESTAMP_NTZ,
    status VARCHAR,
    tps_avg FLOAT,
    latency_avg_ms FLOAT,
    latency_stddev_ms FLOAT,
    num_transactions BIGINT,
    num_failed BIGINT,
    duration_sec FLOAT,
    progress_data VARCHAR,
    summary_json VARCHAR,
    pg_version VARCHAR,
    pg_settings VARCHAR,
    db_spec VARCHAR
);

GRANT SELECT ON TABLE app_config.benchmark_results TO APPLICATION ROLE app_user;

-- ============================================================
-- Procedures
-- ============================================================

CREATE OR REPLACE PROCEDURE app_setup.submit_benchmark(params_json VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    new_id BIGINT;
BEGIN
    INSERT INTO app_config.benchmark_queue (parameters)
    VALUES (:params_json);

    SELECT MAX(queue_id) INTO :new_id FROM app_config.benchmark_queue;

    RETURN :new_id::VARCHAR;
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.submit_benchmark(VARCHAR)
    TO APPLICATION ROLE app_admin;
GRANT USAGE ON PROCEDURE app_setup.submit_benchmark(VARCHAR)
    TO APPLICATION ROLE app_user;

CREATE OR REPLACE PROCEDURE app_setup.get_benchmark_status(queue_id_param BIGINT)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    job_status VARCHAR;
    job_result VARCHAR;
BEGIN
    SELECT status, result
    INTO :job_status, :job_result
    FROM app_config.benchmark_queue
    WHERE queue_id = :queue_id_param;

    RETURN COALESCE(:job_status, 'NOT_FOUND') || '|' || COALESCE(:job_result, '');
EXCEPTION WHEN OTHER THEN
    RETURN 'NOT_FOUND';
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.get_benchmark_status(BIGINT)
    TO APPLICATION ROLE app_admin;
GRANT USAGE ON PROCEDURE app_setup.get_benchmark_status(BIGINT)
    TO APPLICATION ROLE app_user;

CREATE OR REPLACE PROCEDURE app_setup.list_benchmark_results()
RETURNS TABLE (
    result_id BIGINT,
    queue_id BIGINT,
    run_name VARCHAR,
    tool VARCHAR,
    parameters VARCHAR,
    started_at TIMESTAMP_NTZ,
    finished_at TIMESTAMP_NTZ,
    status VARCHAR,
    tps_avg FLOAT,
    latency_avg_ms FLOAT,
    duration_sec FLOAT
)
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
BEGIN
    LET res RESULTSET := (
        SELECT result_id, queue_id, run_name, tool, parameters,
               started_at, finished_at, status, tps_avg, latency_avg_ms, duration_sec
        FROM app_config.benchmark_results
        ORDER BY result_id DESC
        LIMIT 50
    );
    RETURN TABLE(res);
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.list_benchmark_results()
    TO APPLICATION ROLE app_admin;
GRANT USAGE ON PROCEDURE app_setup.list_benchmark_results()
    TO APPLICATION ROLE app_user;

CREATE OR REPLACE PROCEDURE app_setup.get_benchmark_detail(result_id_param BIGINT)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    detail VARCHAR;
BEGIN
    SELECT OBJECT_CONSTRUCT(
        'result_id', result_id,
        'queue_id', queue_id,
        'run_name', run_name,
        'tool', tool,
        'parameters', parameters,
        'started_at', started_at,
        'finished_at', finished_at,
        'status', status,
        'tps_avg', tps_avg,
        'latency_avg_ms', latency_avg_ms,
        'latency_stddev_ms', latency_stddev_ms,
        'num_transactions', num_transactions,
        'num_failed', num_failed,
        'duration_sec', duration_sec,
        'progress_data', progress_data,
        'summary_json', summary_json
    )::VARCHAR INTO :detail
    FROM app_config.benchmark_results
    WHERE result_id = :result_id_param;

    RETURN COALESCE(:detail, '{}');
EXCEPTION WHEN OTHER THEN
    RETURN '{}';
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.get_benchmark_detail(BIGINT)
    TO APPLICATION ROLE app_admin;
GRANT USAGE ON PROCEDURE app_setup.get_benchmark_detail(BIGINT)
    TO APPLICATION ROLE app_user;

CREATE OR REPLACE PROCEDURE app_setup.cancel_pending_jobs()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    cnt INTEGER;
BEGIN
    UPDATE app_config.benchmark_queue
    SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP()
    WHERE status IN ('queued', 'picked');

    SELECT COUNT(*) INTO :cnt
    FROM app_config.benchmark_queue
    WHERE status = 'cancelled' AND completed_at >= DATEADD(SECOND, -5, CURRENT_TIMESTAMP());

    RETURN :cnt || ' job(s) cancelled.';
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.cancel_pending_jobs()
    TO APPLICATION ROLE app_admin;

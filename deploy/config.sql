-- ============================================================
-- Postgres Learning Studio - Configuration Module
-- Manages secrets, EAI references, and PostgreSQL connection settings.
-- ============================================================

-- ============================================================
-- EAI Reference Callbacks
-- ============================================================

CREATE OR REPLACE PROCEDURE app_setup.register_reference(
    ref_name VARCHAR,
    operation VARCHAR,
    ref_or_alias VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
BEGIN
    CASE (operation)
        WHEN 'ADD' THEN
            SELECT SYSTEM$SET_REFERENCE(:ref_name, :ref_or_alias);
        WHEN 'REMOVE' THEN
            SELECT SYSTEM$REMOVE_REFERENCE(:ref_name, :ref_or_alias);
        WHEN 'CLEAR' THEN
            SELECT SYSTEM$REMOVE_ALL_REFERENCES(:ref_name);
        ELSE
            RETURN 'Unknown operation: ' || operation;
    END CASE;
    RETURN 'OK';
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.register_reference(VARCHAR, VARCHAR, VARCHAR)
    TO APPLICATION ROLE app_admin;

-- Called by platform to get EAI configuration (host_ports, allowed_secrets)
CREATE OR REPLACE PROCEDURE app_setup.get_eai_configuration(ref_name VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    pg_host VARCHAR;
    pg_port VARCHAR;
    config_json VARCHAR;
BEGIN
    SELECT value INTO :pg_host FROM app_config.settings WHERE key = 'pg_host';
    SELECT value INTO :pg_port FROM app_config.settings WHERE key = 'pg_port';

    IF (:pg_host IS NULL OR :pg_host = '') THEN
        RETURN '{"type": "ERROR", "payload": {"message": "Postgres host not configured"}}';
    END IF;

    pg_port := COALESCE(:pg_port, '5432');

    pg_host := REPLACE(:pg_host, '"', '');
    pg_port := REPLACE(:pg_port, '"', '');

    config_json := '{' ||
        '"type": "CONFIGURATION",' ||
        '"payload": {' ||
            '"host_ports": ["' || :pg_host || ':' || :pg_port || '"],' ||
            '"allowed_secrets": "ALL"' ||
        '}' ||
    '}';

    RETURN config_json;
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.get_eai_configuration(VARCHAR)
    TO APPLICATION ROLE app_admin;

-- ============================================================
-- PostgreSQL Connection Configuration
-- ============================================================

CREATE OR REPLACE PROCEDURE app_setup.configure_postgres(
    pg_host VARCHAR,
    pg_port VARCHAR DEFAULT '5432',
    pg_admin_user VARCHAR DEFAULT 'snowflake_admin',
    pg_admin_pass VARCHAR DEFAULT ''
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    safe_user VARCHAR;
    safe_pass VARCHAR;
BEGIN
    IF (:pg_host IS NULL OR :pg_host = '') THEN
        RETURN 'ERROR: Postgres host is required';
    END IF;
    IF (:pg_admin_pass IS NULL OR :pg_admin_pass = '') THEN
        RETURN 'ERROR: Postgres password is required';
    END IF;

    safe_user := REPLACE(:pg_admin_user, '''', '''''');
    safe_pass := REPLACE(:pg_admin_pass, '''', '''''');

    EXECUTE IMMEDIATE
        'CREATE OR REPLACE SECRET app_config.postgres_secret '
        || 'TYPE = PASSWORD '
        || 'USERNAME = ''' || :safe_user || ''' '
        || 'PASSWORD = ''' || :safe_pass || '''';

    MERGE INTO app_config.settings AS t
    USING (
        SELECT column1 AS key, column2 AS value FROM VALUES
            ('pg_host', :pg_host),
            ('pg_port', :pg_port),
            ('pg_admin_user', :pg_admin_user),
            ('configured', 'true')
    ) AS s
    ON t.key = s.key
    WHEN MATCHED THEN UPDATE SET value = s.value, updated_at = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN INSERT (key, value) VALUES (s.key, s.value);

    RETURN 'Postgres connection configured. Please approve the External Access Integration in the app settings.';
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.configure_postgres(VARCHAR, VARCHAR, VARCHAR, VARCHAR)
    TO APPLICATION ROLE app_admin;

-- ============================================================
-- Status & Diagnostics
-- ============================================================

CREATE OR REPLACE PROCEDURE app_setup.get_config_status()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    configured VARCHAR DEFAULT 'false';
    pg_host VARCHAR DEFAULT '';
    pg_port VARCHAR DEFAULT '5432';
    pg_user VARCHAR DEFAULT '';
    pool_name VARCHAR DEFAULT '';
    result VARCHAR;
BEGIN
    BEGIN SELECT value INTO :configured FROM app_config.settings WHERE key = 'configured';
    EXCEPTION WHEN OTHER THEN configured := 'false'; END;
    BEGIN SELECT value INTO :pg_host FROM app_config.settings WHERE key = 'pg_host';
    EXCEPTION WHEN OTHER THEN NULL; END;
    BEGIN SELECT value INTO :pg_port FROM app_config.settings WHERE key = 'pg_port';
    EXCEPTION WHEN OTHER THEN NULL; END;
    BEGIN SELECT value INTO :pg_user FROM app_config.settings WHERE key = 'pg_admin_user';
    EXCEPTION WHEN OTHER THEN NULL; END;
    BEGIN SELECT value INTO :pool_name FROM app_config.settings WHERE key = 'compute_pool';
    EXCEPTION WHEN OTHER THEN NULL; END;

    result := '{' ||
        '"configured": "' || COALESCE(:configured, 'false') || '",' ||
        '"pg_host": "' || COALESCE(:pg_host, '') || '",' ||
        '"pg_port": "' || COALESCE(:pg_port, '5432') || '",' ||
        '"pg_user": "' || COALESCE(:pg_user, '') || '",' ||
        '"compute_pool": "' || COALESCE(:pool_name, '') || '"' ||
    '}';

    RETURN result;
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.get_config_status()
    TO APPLICATION ROLE app_admin;
GRANT USAGE ON PROCEDURE app_setup.get_config_status()
    TO APPLICATION ROLE app_user;

CREATE OR REPLACE PROCEDURE app_setup.check_eai_status()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    ref_status VARCHAR DEFAULT 'UNKNOWN';
    secret_exists BOOLEAN DEFAULT FALSE;
    service_status VARCHAR DEFAULT 'NOT_FOUND';
    result VARCHAR;
BEGIN
    BEGIN
        SELECT SYSTEM$GET_ALL_REFERENCES('postgres_eai') INTO :ref_status;
    EXCEPTION WHEN OTHER THEN ref_status := 'NOT_BOUND'; END;

    BEGIN
        EXECUTE IMMEDIATE 'DESCRIBE SECRET app_config.postgres_secret';
        secret_exists := TRUE;
    EXCEPTION WHEN OTHER THEN secret_exists := FALSE; END;

    result := '{' ||
        '"eai_reference": "' || COALESCE(:ref_status, 'UNKNOWN') || '",' ||
        '"secret_exists": ' || :secret_exists::VARCHAR ||
    '}';

    RETURN result;
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.check_eai_status()
    TO APPLICATION ROLE app_admin;

-- ============================================================
-- Reset Configuration
-- ============================================================

CREATE OR REPLACE PROCEDURE app_setup.reset_config()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
BEGIN
    BEGIN
        ALTER SERVICE IF EXISTS app_services.postgres_learning_studio_service SUSPEND;
    EXCEPTION WHEN OTHER THEN NULL; END;

    BEGIN
        DROP SECRET IF EXISTS app_config.postgres_secret;
    EXCEPTION WHEN OTHER THEN NULL; END;

    DELETE FROM app_config.settings
    WHERE key IN ('pg_host', 'pg_port', 'pg_admin_user', 'configured',
                  'pg_connection_type', 'pg_instance_name');

    RETURN 'Configuration reset. You can reconfigure Postgres connection.';
END;
$$;

GRANT USAGE ON PROCEDURE app_setup.reset_config()
    TO APPLICATION ROLE app_admin;

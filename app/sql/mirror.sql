-- ============================================================
-- mirror schema: Auto-mirror PostgreSQL tables to pg_lake Iceberg
-- ============================================================
-- Usage:
--   SELECT mirror.setup('app', 'app_mirror');
--   -- All tables in 'app' are now mirrored as Iceberg tables
--   -- in 'app_mirror', with pg_incremental INSERT pipelines.
--
-- Prerequisites: pg_lake, pg_incremental
-- ============================================================

CREATE SCHEMA IF NOT EXISTS mirror;

CREATE TABLE IF NOT EXISTS mirror._tables (
    src_schema      TEXT NOT NULL,
    src_table       TEXT NOT NULL,
    dst_schema      TEXT NOT NULL,
    ts_column       TEXT NOT NULL,
    pk_columns      TEXT[] NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    last_reconcile  TIMESTAMPTZ,
    PRIMARY KEY (src_schema, src_table)
);

CREATE OR REPLACE FUNCTION mirror._detect_pk(p_schema TEXT, p_table TEXT)
RETURNS TEXT[] LANGUAGE sql STABLE AS $$
    SELECT array_agg(a.attname ORDER BY a.attnum)
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid
                       AND a.attnum = ANY(i.indkey)
    WHERE i.indrelid = format('%I.%I', p_schema, p_table)::regclass
      AND i.indisprimary;
$$;

CREATE OR REPLACE FUNCTION mirror._detect_ts_column(p_schema TEXT, p_table TEXT)
RETURNS TEXT LANGUAGE sql STABLE AS $$
    SELECT column_name::text
    FROM information_schema.columns
    WHERE table_schema = p_schema
      AND table_name = p_table
      AND data_type IN ('timestamp with time zone', 'timestamp without time zone')
    ORDER BY
        (column_name = 'created_at') DESC,
        (column_name LIKE '%created%') DESC,
        (column_name LIKE '%insert%') DESC,
        (column_name LIKE '%time%') DESC,
        (column_name LIKE '%date%') DESC,
        ordinal_position
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION mirror._col_defs(p_schema TEXT, p_table TEXT)
RETURNS TEXT LANGUAGE sql STABLE AS $$
    SELECT string_agg(
        format('%I %s', a.attname, format_type(a.atttypid, a.atttypmod)),
        ', ' ORDER BY a.attnum
    )
    FROM pg_attribute a
    WHERE a.attrelid = format('%I.%I', p_schema, p_table)::regclass
      AND a.attnum > 0
      AND NOT a.attisdropped;
$$;

CREATE OR REPLACE FUNCTION mirror._col_list(p_schema TEXT, p_table TEXT)
RETURNS TEXT LANGUAGE sql STABLE AS $$
    SELECT string_agg(format('%I', a.attname), ', ' ORDER BY a.attnum)
    FROM pg_attribute a
    WHERE a.attrelid = format('%I.%I', p_schema, p_table)::regclass
      AND a.attnum > 0
      AND NOT a.attisdropped;
$$;

CREATE OR REPLACE FUNCTION mirror.add_table(
    p_src_schema TEXT,
    p_dst_schema TEXT,
    p_table      TEXT,
    p_ts_column  TEXT DEFAULT NULL,
    p_pk         TEXT[] DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    v_ts  TEXT;
    v_pk  TEXT[];
    v_cols TEXT;
    v_defs TEXT;
    v_pipe TEXT;
    v_cnt  bigint;
BEGIN
    v_pk := coalesce(p_pk, mirror._detect_pk(p_src_schema, p_table));
    IF v_pk IS NULL THEN
        RETURN jsonb_build_object('table', p_table, 'status', 'skipped',
                                  'reason', 'no primary key');
    END IF;

    v_ts := coalesce(p_ts_column, mirror._detect_ts_column(p_src_schema, p_table));
    IF v_ts IS NULL THEN
        RETURN jsonb_build_object('table', p_table, 'status', 'skipped',
                                  'reason', 'no timestamp column');
    END IF;

    v_defs := mirror._col_defs(p_src_schema, p_table);
    v_cols := mirror._col_list(p_src_schema, p_table);

    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', p_dst_schema);

    EXECUTE format('DROP TABLE IF EXISTS %I.%I', p_dst_schema, p_table);
    EXECUTE format('CREATE TABLE %I.%I (%s) USING iceberg',
                   p_dst_schema, p_table, v_defs);

    EXECUTE format('INSERT INTO %I.%I (%s) SELECT %s FROM %I.%I',
                   p_dst_schema, p_table, v_cols, v_cols,
                   p_src_schema, p_table);
    GET DIAGNOSTICS v_cnt = ROW_COUNT;

    v_pipe := format('mirror_%s_%s', p_src_schema, p_table);

    DELETE FROM incremental.time_interval_pipelines WHERE pipeline_name = v_pipe;
    DELETE FROM incremental.pipelines WHERE pipeline_name = v_pipe;

    PERFORM incremental.create_time_interval_pipeline(
        pipeline_name := v_pipe,
        time_interval := '1 minute'::interval,
        command       := format(
            'INSERT INTO %I.%I (%s) SELECT %s FROM %I.%I WHERE %I >= $1 AND %I < $2',
            p_dst_schema, p_table, v_cols, v_cols,
            p_src_schema, p_table, v_ts, v_ts
        ),
        schedule   := NULL,
        start_time := now()::timestamptz
    );

    INSERT INTO mirror._tables (src_schema, src_table, dst_schema, ts_column, pk_columns)
    VALUES (p_src_schema, p_table, p_dst_schema, v_ts, v_pk)
    ON CONFLICT (src_schema, src_table) DO UPDATE SET
        dst_schema = EXCLUDED.dst_schema,
        ts_column  = EXCLUDED.ts_column,
        pk_columns = EXCLUDED.pk_columns,
        created_at = now();

    RETURN jsonb_build_object(
        'table', p_table, 'status', 'ok',
        'pk', to_jsonb(v_pk), 'ts_column', v_ts,
        'rows_loaded', v_cnt
    );
END;
$$;

CREATE OR REPLACE FUNCTION mirror.setup(
    p_src_schema TEXT DEFAULT 'app',
    p_dst_schema TEXT DEFAULT 'app_mirror'
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    v_tbl  RECORD;
    v_results jsonb := '[]'::jsonb;
    v_r    jsonb;
BEGIN
    FOR v_tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = p_src_schema
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    LOOP
        v_r := mirror.add_table(p_src_schema, p_dst_schema, v_tbl.table_name);
        v_results := v_results || jsonb_build_array(v_r);
    END LOOP;
    RETURN v_results;
END;
$$;

CREATE OR REPLACE FUNCTION mirror.reconcile(
    p_src_schema TEXT,
    p_dst_schema TEXT,
    p_table      TEXT
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    v_reg       mirror._tables;
    v_pk_join   TEXT;
    v_set       TEXT;
    v_cmp_m     TEXT;
    v_cmp_s     TEXT;
    v_scope     TEXT;
    v_n_upd     INT := 0;
    v_n_del     INT := 0;
    v_non_pk    TEXT[];
BEGIN
    SELECT * INTO v_reg FROM mirror._tables
    WHERE src_schema = p_src_schema AND src_table = p_table;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', format('%s.%s not registered', p_src_schema, p_table));
    END IF;

    v_scope := format(
        '%I >= now() - interval ''1 day'' AND %I < now() - interval ''2 minutes''',
        v_reg.ts_column, v_reg.ts_column
    );

    SELECT string_agg(format('s.%I = m.%I', pk, pk), ' AND ')
    INTO v_pk_join FROM unnest(v_reg.pk_columns) pk;

    SELECT array_agg(a.attname ORDER BY a.attnum)
    INTO v_non_pk
    FROM pg_attribute a
    WHERE a.attrelid = format('%I.%I', p_src_schema, p_table)::regclass
      AND a.attnum > 0 AND NOT a.attisdropped
      AND a.attname <> ALL(v_reg.pk_columns);

    IF v_non_pk IS NOT NULL AND array_length(v_non_pk, 1) > 0 THEN
        SELECT string_agg(format('%I = s.%I', c, c), ', ')
        INTO v_set FROM unnest(v_non_pk) c;

        SELECT string_agg(format('m.%I', c), ', '),
               string_agg(format('s.%I', c), ', ')
        INTO v_cmp_m, v_cmp_s FROM unnest(v_non_pk) c;

        EXECUTE format($SQL$
            UPDATE %I.%I m SET %s
            FROM (SELECT * FROM %I.%I WHERE %s) s
            WHERE %s AND m.%s AND (%s) IS DISTINCT FROM (%s)
        $SQL$,
            p_dst_schema, p_table, v_set,
            p_src_schema, p_table, v_scope,
            v_pk_join, v_scope, v_cmp_m, v_cmp_s
        );
        GET DIAGNOSTICS v_n_upd = ROW_COUNT;
    END IF;

    EXECUTE format($SQL$
        DELETE FROM %I.%I m
        WHERE m.%s
          AND NOT EXISTS (
              SELECT 1 FROM %I.%I s WHERE %s
          )
    $SQL$,
        p_dst_schema, p_table,
        v_scope,
        p_src_schema, p_table,
        v_pk_join
    );
    GET DIAGNOSTICS v_n_del = ROW_COUNT;

    UPDATE mirror._tables SET last_reconcile = now()
    WHERE src_schema = p_src_schema AND src_table = p_table;

    RETURN jsonb_build_object(
        'table', p_table, 'updated', v_n_upd, 'deleted', v_n_del
    );
END;
$$;

CREATE OR REPLACE FUNCTION mirror.reconcile_all()
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    v_tbl     mirror._tables;
    v_results jsonb := '[]'::jsonb;
BEGIN
    FOR v_tbl IN SELECT * FROM mirror._tables LOOP
        v_results := v_results || jsonb_build_array(
            mirror.reconcile(v_tbl.src_schema, v_tbl.dst_schema, v_tbl.src_table)
        );
    END LOOP;
    RETURN v_results;
END;
$$;

CREATE OR REPLACE FUNCTION mirror.status()
RETURNS TABLE (
    src        TEXT,
    dst        TEXT,
    pk         TEXT,
    ts_col     TEXT,
    last_sync  TIMESTAMPTZ,
    src_rows   BIGINT,
    dst_rows   BIGINT
) LANGUAGE plpgsql AS $$
DECLARE
    v mirror._tables;
BEGIN
    FOR v IN SELECT * FROM mirror._tables ORDER BY src_schema, src_table LOOP
        src     := format('%I.%I', v.src_schema, v.src_table);
        dst     := format('%I.%I', v.dst_schema, v.src_table);
        pk      := array_to_string(v.pk_columns, ', ');
        ts_col  := v.ts_column;
        last_sync := v.last_reconcile;
        EXECUTE format('SELECT count(*) FROM %I.%I', v.src_schema, v.src_table) INTO src_rows;
        EXECUTE format('SELECT count(*) FROM %I.%I', v.dst_schema, v.src_table) INTO dst_rows;
        RETURN NEXT;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION mirror.teardown(
    p_src_schema TEXT DEFAULT 'app',
    p_dst_schema TEXT DEFAULT 'app_mirror'
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    v mirror._tables;
    v_pipe TEXT;
    v_cnt INT := 0;
BEGIN
    FOR v IN
        SELECT * FROM mirror._tables
        WHERE src_schema = p_src_schema AND dst_schema = p_dst_schema
    LOOP
        v_pipe := format('mirror_%s_%s', v.src_schema, v.src_table);
        DELETE FROM incremental.time_interval_pipelines WHERE pipeline_name = v_pipe;
        DELETE FROM incremental.pipelines WHERE pipeline_name = v_pipe;
        EXECUTE format('DROP TABLE IF EXISTS %I.%I', v.dst_schema, v.src_table);
        DELETE FROM mirror._tables
        WHERE src_schema = v.src_schema AND src_table = v.src_table;
        v_cnt := v_cnt + 1;
    END LOOP;
    EXECUTE format('DROP SCHEMA IF EXISTS %I', p_dst_schema);
    RETURN jsonb_build_object('removed', v_cnt);
END;
$$;

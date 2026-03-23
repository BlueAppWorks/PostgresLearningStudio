"""
Postgres Learning Studio - Setup UI
5-step guided wizard with progress tracking and auto-expand.
Sidebar navigation: Overview / Setup / Advanced Settings.
"""

import time

import streamlit as st
from snowflake.snowpark.context import get_active_session

session = get_active_session()
APP_NAME = session.sql("SELECT CURRENT_DATABASE()").collect()[0][0]

st.set_page_config(page_title=f"{APP_NAME} Setup", layout="wide")

# ============================================================
# App-specific configuration
# ============================================================
EAI_REF_NAME = "postgres_eai"
EAI_DISPLAY_LABEL = "PostgreSQL External Access"
DEFAULT_DB_PORT = "5432"
DEFAULT_DB_USER = "snowflake_admin"
DB_HOST_PLACEHOLDER = "your-postgres.snowflake.app"
RESOURCE_TYPE_LABEL = "PostgreSQL"


# ============================================================
# Helper Functions
# ============================================================
def get_setting(key: str, default: str = "") -> str:
    """Read a value from app_config.settings."""
    try:
        rows = session.sql(
            f"SELECT value FROM app_config.settings WHERE key = '{key}'"
        ).collect()
        return rows[0]["VALUE"] if rows else default
    except Exception:
        return default


def get_all_settings() -> dict:
    """Load all settings from app_config.settings."""
    try:
        rows = session.sql("SELECT key, value FROM app_config.settings").collect()
        return {row["KEY"]: row["VALUE"] for row in rows}
    except Exception:
        return {}


def call_procedure(proc: str, *args) -> str:
    """Call a stored procedure and return the result string."""
    if args:
        arg_str = ", ".join(
            f"'{a}'" if isinstance(a, str) else str(a) for a in args
        )
        result = session.sql(f"CALL app_setup.{proc}({arg_str})").collect()
    else:
        result = session.sql(f"CALL app_setup.{proc}()").collect()
    return str(result[0][0]) if result else ""


def upsert_setting(key: str, value: str):
    """Save a setting to app_config.settings."""
    safe_key = key.replace("'", "''")
    safe_value = value.replace("'", "''")
    session.sql(
        f"MERGE INTO app_config.settings AS t "
        f"USING (SELECT '{safe_key}' AS key, '{safe_value}' AS value) AS s ON t.key = s.key "
        f"WHEN MATCHED THEN UPDATE SET value = s.value, updated_at = CURRENT_TIMESTAMP() "
        f"WHEN NOT MATCHED THEN INSERT (key, value) VALUES (s.key, s.value)"
    ).collect()


def get_service_status() -> str:
    """Get the current service status string."""
    try:
        result = call_procedure("service_status")
        if result and "ERROR" not in str(result):
            return str(result).strip()
    except Exception:
        pass
    return "NOT_FOUND"


# ============================================================
# Step header with color-coded status badge
# ============================================================
def _step_header(step_num: int, title: str, state: str) -> str:
    """Return step header with status badge.

    state: 'done', 'current', 'future'
    """
    if state == "done":
        icon = "\u2705"
        color = "#0d6"
        label = "Done"
    elif state == "current":
        icon = "\u25b6\ufe0f"
        color = "#f55"
        label = "Action Required"
    else:
        icon = "\u23f3"
        color = "#888"
        label = "Pending"
    return (
        f"{icon}  **Step {step_num}: {title}**"
        f"  &nbsp; <span style='font-size:0.75rem;padding:2px 8px;border-radius:4px;"
        f"background:{color}22;color:{color};font-weight:600'>{label}</span>"
    )


def _done_badge(text: str) -> str:
    """Green summary badge for completed steps."""
    return (
        f'<div style="font-size:0.82rem;padding:6px 10px;border-radius:6px;'
        f'background:#0d662222;border:1px solid #0d663333">'
        f'<span style="color:#0d6;font-weight:600">{text}</span></div>'
    )


# ============================================================
# Sidebar Navigation
# ============================================================
pages = ["Overview", "Setup", "Advanced Settings"]
selected_page = st.sidebar.radio("Navigation", pages)


# ============================================================
# Shared State (read once, used across all pages/steps)
# ============================================================
settings = get_all_settings()
pool_name = get_setting("compute_pool")
db_configured = get_setting("configured", "false")
svc_status = get_service_status()

# Step 1: Compute Pool created
step1_done = bool(pool_name)

# Step 2: Database configured
step2_done = db_configured == "true"

# Step 3: EAI approved — verify reference is actually bound and valid
step3_done = False
eai_stale = False
try:
    ref_result = session.sql(
        f"SELECT SYSTEM$GET_ALL_REFERENCES('{EAI_REF_NAME}')"
    ).collect()[0][0]
    if ref_result and ref_result.strip() not in ("", "[]"):
        # Reference appears bound — verify it is actually valid by checking
        # that the reference can resolve. After DROP/CREATE APPLICATION,
        # stale references may still appear in SYSTEM$GET_ALL_REFERENCES
        # but fail at service creation time.
        try:
            import json
            refs = json.loads(ref_result)
            if isinstance(refs, list) and len(refs) > 0:
                # Check if the referenced EAI actually exists by trying
                # to use it in a configuration callback
                eai_check = session.sql(
                    f"CALL app_setup.get_eai_configuration('{EAI_REF_NAME}')"
                ).collect()[0][0]
                if eai_check and '"host_ports"' in eai_check and '"placeholder"' not in eai_check:
                    step3_done = True
                else:
                    eai_stale = True
            else:
                eai_stale = True
        except Exception:
            # If the callback fails, the reference is likely stale
            eai_stale = True
except Exception:
    pass

# Step 4: Service created (any state except NOT_FOUND)
step4_done = svc_status != "NOT_FOUND"
step4_running = svc_status in ("READY", "RUNNING")

# Step 5: Gallery Operator detected
step5_done = False
try:
    rows = session.sql(
        "SELECT app_name FROM BLUE_APP_GALLERY_REGISTRY.PUBLIC.OPERATOR "
        "WHERE app_name = 'BLUE_APP_GALLERY' LIMIT 1"
    ).collect()
    step5_done = len(rows) > 0
except Exception:
    pass

# Determine current step (first incomplete)
step_states = [step1_done, step2_done, step3_done, step4_done, step5_done]
done_count = sum(step_states)
all_done = done_count == 5

if not step1_done:
    current_step = 1
elif not step2_done:
    current_step = 2
elif not step3_done:
    current_step = 3
elif not step4_done:
    current_step = 4
elif not step5_done:
    current_step = 5
else:
    current_step = 0  # All done


def step_state(step_num: int, done: bool) -> str:
    if done:
        return "done"
    if step_num == current_step:
        return "current"
    return "future"


# ============================================================
# Page: Overview
# ============================================================
if selected_page == "Overview":
    st.title(f"{APP_NAME}")

    if step5_done:
        st.success(
            "Gallery Operator detected. "
            "This app is managed by Gallery — start and stop from the Gallery UI."
        )
    elif all_done:
        st.success("All setup steps are complete. Your app is ready to use.")
    else:
        st.info("Setup is not complete. Go to the **Setup** page to continue.")

    # Service status
    if step4_running:
        url = call_procedure("service_url")
        st.success(f"Service is **{svc_status}**")
        if url:
            st.markdown(
                f'<a href="https://{url}" target="_blank" '
                f'style="display:inline-block;margin-top:8px;padding:10px 20px;'
                f'background:#0d6efd;color:white;border-radius:8px;'
                f'text-decoration:none;font-weight:bold;">'
                f'Open {APP_NAME}</a>',
                unsafe_allow_html=True,
            )
            st.caption(f"URL: https://{url}")
    elif svc_status == "NOT_FOUND":
        st.warning("Service not yet created. Complete the Setup wizard first.")
    else:
        st.info(f"Service status: **{svc_status}**")


# ============================================================
# Page: Setup (5-step guided wizard)
# ============================================================
elif selected_page == "Setup":
    st.title("Setup Wizard")
    st.caption("Setup & Configuration")

    # Overall progress
    if all_done:
        st.success("All setup steps are complete. Your app is ready to use.")
    else:
        st.progress(done_count / 5)
        st.caption(f"Setup progress: **{done_count}/5** steps complete")

    # Quick status bar
    step_labels = ["Compute Pool", "PostgreSQL", "EAI", "Service", "Gallery"]
    qs_cols = st.columns(5)
    for i, (label, done) in enumerate(zip(step_labels, step_states)):
        with qs_cols[i]:
            color = "#0d6" if done else "#f55" if (i + 1) == current_step else "#888"
            st.markdown(
                f'<div style="text-align:center;font-size:0.78rem">'
                f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
                f'background:{color};margin-right:4px"></span>{label}</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ----------------------------------------------------------
    # Step 1: Compute Pool
    # ----------------------------------------------------------
    s1 = step_state(1, step1_done)
    st.markdown(_step_header(1, "Compute Pool", s1), unsafe_allow_html=True)

    with st.expander("Create compute pool for containers", expanded=(s1 == "current")):
        if step1_done:
            pool_status = "UNKNOWN"
            try:
                rows = session.sql(
                    f"SHOW COMPUTE POOLS LIKE '{pool_name}'"
                ).collect()
                if rows:
                    pool_status = rows[0]["state"]
            except Exception:
                pass
            st.markdown(
                _done_badge(f"Compute Pool: {pool_name} ({pool_status})"),
                unsafe_allow_html=True,
            )
        else:
            has_privilege = False
            try:
                rows = session.sql(
                    f"SHOW GRANTS TO APPLICATION {APP_NAME}"
                ).collect()
                for row in rows:
                    if row["privilege"] == "CREATE COMPUTE POOL":
                        has_privilege = True
                        break
            except Exception:
                pass

            if has_privilege:
                st.info(
                    "**CREATE COMPUTE POOL** privilege is granted. "
                    "Click the button below to create the compute pool."
                )
                if st.button("Create Compute Pool", type="primary", key="create_pool"):
                    with st.spinner("Creating compute pool..."):
                        result = call_procedure("ensure_compute_pool")
                    st.success(f"Compute pool created: **{result}**")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("**CREATE COMPUTE POOL** privilege is required.")
                st.markdown(
                    "**How to grant:**\n"
                    "1. Click the app name **in the top navigation bar** of this page\n"
                    "2. Click the **Security** tab (or the shield icon next to the app name)\n"
                    "3. Find **CREATE COMPUTE POOL** and click **Grant**\n"
                    "4. Come back to this Setup page and **refresh**"
                )

    st.divider()

    # ----------------------------------------------------------
    # Step 2: PostgreSQL Connection
    # ----------------------------------------------------------
    s2 = step_state(2, step2_done)
    st.markdown(
        _step_header(2, f"{RESOURCE_TYPE_LABEL} Connection", s2),
        unsafe_allow_html=True,
    )

    with st.expander(
        f"Configure {RESOURCE_TYPE_LABEL} connection",
        expanded=(s2 == "current"),
    ):
        if not step1_done:
            st.caption("Complete Step 1 first.")
        elif step2_done:
            conn_type_label = (
                "Snowflake Postgres"
                if settings.get("pg_connection_type") == "snowflake_postgres"
                else "External PostgreSQL"
            )
            instance_info = ""
            if settings.get("pg_instance_name"):
                instance_info = f" / {settings.get('pg_instance_name')}"
            conn_detail = (
                f"{settings.get('pg_admin_user', '')}@"
                f"{settings.get('pg_host', '')}:{settings.get('pg_port', '5432')}"
            )
            st.markdown(
                _done_badge(
                    f"{conn_type_label}{instance_info}"
                    f'<br><span style="color:#888;font-size:0.75rem">{conn_detail}</span>'
                ),
                unsafe_allow_html=True,
            )
            st.caption("")
            if st.button("Reset Connection", type="secondary", key="reset_db"):
                call_procedure("reset_config")
                time.sleep(1)
                st.rerun()
        else:
            st.info(
                f"Configure the {RESOURCE_TYPE_LABEL} connection. "
                "Credentials are stored securely in a Snowflake SECRET."
            )

            # Connection type selector
            saved_conn_type = settings.get("pg_connection_type", "")
            conn_type_options = ["Snowflake Postgres", "External PostgreSQL"]
            default_idx = (
                0 if saved_conn_type == "snowflake_postgres"
                else 1 if saved_conn_type else 0
            )
            conn_type = st.radio(
                "Connection Type",
                conn_type_options,
                index=default_idx,
                horizontal=True,
                help="Snowflake Postgres: managed instance / External: any PostgreSQL",
            )

            if conn_type == "Snowflake Postgres":
                # Discover Postgres instances
                instance_map = {}
                try:
                    pg_instances = session.sql("SHOW POSTGRES INSTANCES").collect()
                    for row in pg_instances:
                        name = row.get("name", row.get("NAME", ""))
                        host = row.get("host", row.get("HOST", ""))
                        state = row.get("state", row.get("STATE", ""))
                        instance_map[name] = {"host": host, "state": state}
                except Exception:
                    pass

                if instance_map:
                    instance_names = list(instance_map.keys())
                    saved_instance = settings.get("pg_instance_name", "")
                    default_instance_idx = (
                        instance_names.index(saved_instance)
                        if saved_instance in instance_names
                        else 0
                    )
                    selected_instance = st.selectbox(
                        "Postgres Instance",
                        instance_names,
                        index=default_instance_idx,
                    )
                    inst_host = instance_map[selected_instance]["host"]
                    inst_state = instance_map[selected_instance]["state"]
                    st.caption(f"Host: `{inst_host}` / State: **{inst_state}**")
                else:
                    selected_instance = st.text_input(
                        "Postgres Instance Name",
                        value=settings.get("pg_instance_name", ""),
                        help="e.g. PLEASANTER_APP_DB",
                    )
                    inst_host = ""
                    st.caption(
                        "Auto-discovery unavailable inside Native Apps. "
                        "Run `SHOW POSTGRES INSTANCES;` in Snowsight to find the host."
                    )

                with st.form("sf_postgres_config"):
                    pg_host_sf = st.text_input(
                        "Postgres Host",
                        value=settings.get("pg_host", ""),
                        help="Run SHOW POSTGRES INSTANCES and paste the host value",
                    )
                    pg_port_sf = st.text_input("Port", value="5432", disabled=True)
                    pg_user_sf = st.text_input(
                        "Username",
                        value=settings.get("pg_admin_user", "snowflake_admin"),
                    )
                    pg_pass_sf = st.text_input("Password", type="password")

                    submitted_sf = st.form_submit_button(
                        "Save Configuration", type="primary"
                    )

                if submitted_sf:
                    if not pg_host_sf or not pg_pass_sf or not selected_instance:
                        st.error("Instance Name, Host, and Password are required.")
                    else:
                        result = call_procedure(
                            "configure_postgres",
                            pg_host_sf, "5432", pg_user_sf, pg_pass_sf,
                        )
                        if "ERROR" in result:
                            st.error(result)
                        else:
                            upsert_setting("pg_connection_type", "snowflake_postgres")
                            upsert_setting("pg_instance_name", selected_instance)
                            st.success(result)
                            time.sleep(1)
                            st.rerun()

            else:
                # External PostgreSQL
                with st.form("postgres_config"):
                    pg_host = st.text_input(
                        "Postgres Host",
                        value=settings.get("pg_host", ""),
                        placeholder=DB_HOST_PLACEHOLDER,
                    )
                    pg_port = st.text_input(
                        "Port", value=settings.get("pg_port", DEFAULT_DB_PORT)
                    )
                    pg_user = st.text_input(
                        "Username",
                        value=settings.get("pg_admin_user", ""),
                    )
                    pg_pass = st.text_input("Password", type="password")

                    submitted = st.form_submit_button(
                        "Save Configuration", type="primary"
                    )

                if submitted:
                    if not pg_host or not pg_pass or not pg_user:
                        st.error("Host, Username, and Password are required.")
                    else:
                        result = call_procedure(
                            "configure_postgres",
                            pg_host, pg_port, pg_user, pg_pass,
                        )
                        if "ERROR" in result:
                            st.error(result)
                        else:
                            upsert_setting("pg_connection_type", "external")
                            upsert_setting("pg_instance_name", "")
                            st.success(result)
                            time.sleep(1)
                            st.rerun()

    st.divider()

    # ----------------------------------------------------------
    # Step 3: External Access Integration (EAI)
    # ----------------------------------------------------------
    s3 = step_state(3, step3_done)
    st.markdown(
        _step_header(3, "External Access Integration (EAI)", s3),
        unsafe_allow_html=True,
    )

    with st.expander(
        f"Approve EAI for {RESOURCE_TYPE_LABEL} connectivity",
        expanded=(s3 == "current"),
    ):
        if not step1_done or not step2_done:
            st.caption("Complete Steps 1 and 2 first.")
        elif step3_done:
            st.markdown(
                _done_badge(f"EAI Approved — {RESOURCE_TYPE_LABEL} access enabled"),
                unsafe_allow_html=True,
            )
        elif eai_stale:
            st.error(
                "**EAI reference appears stale.** The previous approval may no longer be valid "
                "(this can happen after the application is reinstalled).\n\n"
                "**Please re-approve the EAI** by following the steps below."
            )

            db_host_display = get_setting("pg_host", "your-database-host")
            db_port_display = get_setting("pg_port", DEFAULT_DB_PORT)

            st.markdown(
                "**How to re-approve:**\n\n"
                f"1. Open **Snowsight** and navigate to **Data Products → Apps → {APP_NAME}**\n"
                "2. In the app detail page, click the **Security** tab "
                "(look for the shield icon or the ⋮ menu → Manage Access)\n"
                f"3. Find **\"{EAI_DISPLAY_LABEL}\"** listed under **External Access**\n"
                "4. If it shows as \"Approved\" from a previous installation, "
                "click **Review** to verify the connection details:\n"
                f"   - Allowed host: `{db_host_display}:{db_port_display}`\n"
                "5. Click **Approve** (or re-approve) to activate the integration\n"
                "6. Return to this Setup page and click **Check EAI Status** below"
            )

            st.info(
                "💡 **Tip:** The Security tab can be hard to find. "
                "In Snowsight, go to **Data Products → Apps**, click your app name, "
                "then look for **Security** in the top tab bar or under the ⋮ menu."
            )
        if not step3_done and (step1_done and step2_done):
            if not eai_stale:
                st.warning(
                    f"**EAI approval is required** before the service can connect to "
                    f"{RESOURCE_TYPE_LABEL}.\n\n"
                    "The service will **fail to start** without this approval."
                )
            st.markdown(
                "**What is EAI?**\n\n"
                "External Access Integration (EAI) is a Snowflake security control that "
                "allows containers to make outbound network connections. "
                f"This app needs EAI to connect to your {RESOURCE_TYPE_LABEL} instance."
            )

            db_host_display = get_setting("pg_host", "your-database-host")
            db_port_display = get_setting("pg_port", DEFAULT_DB_PORT)

            st.markdown(
                "**How to approve (step-by-step):**\n\n"
                "1. Look at the **very top of this page** — you should see a navigation bar "
                f"with the app name **{APP_NAME}**\n"
                "2. Click the app name to go to the **Native App detail page** in Snowsight\n"
                "3. You will see a row of tabs: **Readme / Security / Manage Versions / ...**\n"
                "4. Click the **Security** tab (it may show a shield icon or just say \"Security\")\n"
                f"5. Scroll down to the **External Access** section\n"
                f"6. Find the row labeled **\"{EAI_DISPLAY_LABEL}\"**\n"
                "7. Click the **Review** button on that row — a panel will open showing:\n"
                f"   - Allowed host: `{db_host_display}:{db_port_display}`\n"
                "   - Allowed secrets\n"
                "8. Click the **Allow** or **Approve** button (blue button at the bottom of the panel)\n"
                "9. Return to this Setup page (use the browser back button or navigate to the app)\n"
                "10. Click **Check EAI Status** below to verify"
            )

            st.info(
                "**Can't find the Security tab?**\n\n"
                "The Security tab is on the **Snowsight Native App management page**, "
                "not inside this Streamlit UI. "
                "If you are viewing the Streamlit app in full screen, "
                "look for a small bar at the very top with the app name — click it to navigate "
                "to the management page where the Security tab is visible."
            )

            if st.button("Check EAI Status", type="primary", key="check_eai"):
                st.rerun()

    st.divider()

    # ----------------------------------------------------------
    # Step 4: Service
    # ----------------------------------------------------------
    s4 = step_state(4, step4_done)
    st.markdown(_step_header(4, "Service", s4), unsafe_allow_html=True)

    with st.expander("Service status and Web UI", expanded=(s4 == "current")):
        if not step1_done or not step2_done or not step3_done:
            missing = []
            if not step1_done:
                missing.append("Step 1 (Compute Pool)")
            if not step2_done:
                missing.append("Step 2 (PostgreSQL Connection)")
            if not step3_done:
                missing.append("Step 3 (EAI Approval)")
            st.caption(f"Complete {', '.join(missing)} first.")
        elif step4_running:
            st.markdown(
                _done_badge(f"Service: {svc_status}"),
                unsafe_allow_html=True,
            )
            url = call_procedure("service_url")
            if url and url.strip():
                st.markdown(
                    f'<a href="https://{url}" target="_blank" '
                    f'style="display:inline-block;margin-top:8px;padding:10px 20px;'
                    f'background:#0d6efd;color:white;border-radius:8px;'
                    f'text-decoration:none;font-weight:bold;">'
                    f'Open {APP_NAME}</a>',
                    unsafe_allow_html=True,
                )
                st.caption(f"URL: https://{url}")
            else:
                st.info("Endpoint URL is being provisioned. Refresh in a moment.")
        elif step4_done:
            st.markdown(
                _done_badge(f"Service created (status: {svc_status})"),
                unsafe_allow_html=True,
            )
            st.caption(
                "Start/stop is managed by Gallery Operator. "
                "Use the Gallery UI to start the app."
            )
        else:
            st.info(
                "**Create the service for the first time.**\n\n"
                "This is a one-time action. After creation, Gallery Operator "
                "will manage start/stop."
            )
            if st.button("Create Service", type="primary", key="create_svc"):
                with st.spinner("Starting service..."):
                    result = call_procedure("start_service")
                if "ERROR" in str(result):
                    st.error(result)
                else:
                    st.success(result)
                    time.sleep(2)
                    st.rerun()

        # Troubleshooting (available when service has been created)
        if step2_done and step4_done:
            st.markdown("---")
            st.caption(
                "If the service is stuck or unreachable, you can recreate it here."
            )
            t_cols = st.columns(2)
            with t_cols[0]:
                if st.button("Recreate Service", key="recreate_svc"):
                    call_procedure("drop_service")
                    result = call_procedure("start_service")
                    st.info(result)
                    time.sleep(2)
                    st.rerun()
            with t_cols[1]:
                if st.button("Fetch Logs", key="fetch_logs"):
                    logs = call_procedure("service_logs", 100)
                    if "ERROR" in str(logs):
                        st.error(logs)
                    else:
                        st.code(logs, language="text")

    st.divider()

    # ----------------------------------------------------------
    # Step 5: Gallery Operator Integration
    # ----------------------------------------------------------
    s5 = step_state(5, step5_done)
    st.markdown(
        _step_header(5, "Gallery Operator Integration", s5),
        unsafe_allow_html=True,
    )

    with st.expander("Connect to Gallery Operator", expanded=(s5 == "current")):
        if step5_done:
            st.markdown(
                _done_badge("Gallery Operator Connected"),
                unsafe_allow_html=True,
            )
        else:
            st.info(
                "Run the following GRANTs in a **Snowsight SQL Worksheet** as **ACCOUNTADMIN** "
                "to connect this app with Gallery Operator."
            )

        # Build GRANT SQL with actual or placeholder names
        pool_display = pool_name if pool_name else "<COMPUTE_POOL_NAME>"
        pg_instance = settings.get("pg_instance_name", "")
        pg_display = pg_instance if pg_instance else "<POSTGRES_INSTANCE_NAME>"

        grant_sql = (
            f"-- Run in Snowsight Worksheet as ACCOUNTADMIN\n\n"
            f"-- 1. Registry access (Gallery Operator detection)\n"
            f"GRANT USAGE ON DATABASE BLUE_APP_GALLERY_REGISTRY\n"
            f"    TO APPLICATION {APP_NAME};\n"
            f"GRANT USAGE ON SCHEMA BLUE_APP_GALLERY_REGISTRY.PUBLIC\n"
            f"    TO APPLICATION {APP_NAME};\n"
            f"GRANT SELECT ON TABLE BLUE_APP_GALLERY_REGISTRY.PUBLIC.OPERATOR\n"
            f"    TO APPLICATION {APP_NAME};\n"
            f"\n"
            f"-- 2. App role (allows Gallery Operator to manage this app)\n"
            f"GRANT APPLICATION ROLE {APP_NAME}.app_admin\n"
            f"    TO APPLICATION BLUE_APP_GALLERY;\n"
            f"\n"
            f"-- 3. Compute Pool (start/stop control)\n"
            f"GRANT OPERATE ON COMPUTE POOL {pool_display}\n"
            f"    TO APPLICATION BLUE_APP_GALLERY;\n"
            f"GRANT MONITOR ON COMPUTE POOL {pool_display}\n"
            f"    TO APPLICATION BLUE_APP_GALLERY;\n"
        )

        if settings.get("pg_connection_type") == "snowflake_postgres":
            grant_sql += (
                f"\n"
                f"-- 4. Postgres Instance (resumed/suspended by Operator)\n"
                f"GRANT OPERATE ON POSTGRES INSTANCE {pg_display}\n"
                f"    TO APPLICATION BLUE_APP_GALLERY;\n"
            )

        st.code(grant_sql, language="sql")

        placeholders = []
        if not pool_name:
            placeholders.append("`<COMPUTE_POOL_NAME>`")
        if settings.get("pg_connection_type") == "snowflake_postgres" and not pg_instance:
            placeholders.append("`<POSTGRES_INSTANCE_NAME>`")
        if placeholders:
            st.caption(
                f"Placeholders {', '.join(placeholders)} will be replaced "
                "when resources are configured."
            )

        if not step5_done:
            if st.button("Check Gallery Operator", type="primary", key="check_gallery"):
                st.rerun()


# ============================================================
# Page: Advanced Settings
# ============================================================
elif selected_page == "Advanced Settings":
    st.title("Advanced Settings")

    # Resource sizing
    with st.expander("Service Resource Limits", expanded=False):
        st.caption(
            "Default settings are sufficient for most use cases. "
            "Changes take effect on next service start."
        )
        with st.form("resource_config"):
            col1, col2 = st.columns(2)
            with col1:
                cpu_req = st.text_input(
                    "CPU Request", value=get_setting("cpu_request", "0.5")
                )
                mem_req = st.text_input(
                    "Memory Request", value=get_setting("memory_request", "1Gi")
                )
            with col2:
                cpu_lim = st.text_input(
                    "CPU Limit", value=get_setting("cpu_limit", "2")
                )
                mem_lim = st.text_input(
                    "Memory Limit", value=get_setting("memory_limit", "4Gi")
                )

            if st.form_submit_button("Save Resource Settings"):
                upsert_setting("cpu_request", cpu_req)
                upsert_setting("cpu_limit", cpu_lim)
                upsert_setting("memory_request", mem_req)
                upsert_setting("memory_limit", mem_lim)
                st.success("Resource settings saved. Restart the service to apply.")

    # PostgreSQL Extensions (Snowflake Postgres only)
    saved_instance_name = settings.get("pg_instance_name", "")
    is_sf_postgres = settings.get("pg_connection_type") == "snowflake_postgres"

    if is_sf_postgres and saved_instance_name:
        with st.expander("PostgreSQL Extensions", expanded=False):
            st.caption(f"Target Instance: **{saved_instance_name}**")
            st.info(
                "To load extension libraries, use `ALTER POSTGRES INSTANCE` "
                "(PostgreSQL's internal `ALTER SYSTEM` is restricted)."
            )
            st.warning(
                "Currently only **`auto_explain`** is supported in "
                "`session_preload_libraries`."
            )

            if st.button("Check Instance Settings", key="check_pg_settings"):
                try:
                    rows = session.sql(
                        f"DESCRIBE POSTGRES INSTANCE {saved_instance_name}"
                    ).collect()
                    st.dataframe(rows)
                except Exception as e:
                    st.error(f"Failed: {e}")

            AVAILABLE_PRELOAD_LIBS = ["auto_explain"]
            preload_libs = st.multiselect(
                "Libraries to add to session_preload_libraries",
                AVAILABLE_PRELOAD_LIBS,
                default=[],
            )

            if st.button(
                "Apply session_preload_libraries",
                type="primary",
                key="apply_preload",
            ):
                if not preload_libs:
                    st.warning("Select at least one library.")
                else:
                    lib_value = ",".join(preload_libs)
                    alter_sql = (
                        f"ALTER POSTGRES INSTANCE {saved_instance_name} "
                        f'SET POSTGRES_SETTINGS = \'{{"postgres:session_preload_libraries": "{lib_value}"}}\''
                    )
                    st.code(alter_sql, language="sql")
                    try:
                        session.sql(alter_sql).collect()
                        st.success(
                            f"`session_preload_libraries = '{lib_value}'` set."
                        )
                    except Exception as e:
                        st.error(f"Failed: {e}")

    elif not is_sf_postgres and step2_done:
        with st.expander("PostgreSQL Extensions", expanded=False):
            st.caption(
                "Using external PostgreSQL. Configure extensions via "
                "`shared_preload_libraries` on the PostgreSQL side."
            )

    # Additional targets
    with st.expander("Additional Target Connections", expanded=False):
        st.info(
            "Register additional benchmark/learning targets from the **Connections** "
            "page in the Web UI.\n\n"
            "**Note:** When adding a new host, the EAI network rule must include "
            "that host."
        )

    # Service logs
    with st.expander("Service Logs", expanded=False):
        if st.button("Fetch Logs", key="adv_fetch_logs"):
            logs = call_procedure("service_logs", 100)
            if "ERROR" in str(logs):
                st.error(logs)
            else:
                st.code(logs, language="text")

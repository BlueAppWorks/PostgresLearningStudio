#!/bin/bash
# ============================================================
# Postgres Learning Studio — Deploy Script
# ============================================================
# Usage:
#   ./deploy.sh dev v1            # Deploy to dev account
#   ./deploy.sh prod v1           # Deploy to production account
#   ./deploy.sh both v1 v1        # Deploy to both
#
# Prerequisites:
#   - Docker Desktop running
#   - snow CLI installed and configured
#   - deploy/deploy.env created (see deploy.env.example)
#   - Snowflake image repositories already created
# ============================================================

set -e

# Load environment-specific settings from deploy.env (gitignored)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/deploy.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: ${ENV_FILE} not found."
    echo "Create it from deploy.env.example:"
    echo "  cp deploy/deploy.env.example deploy/deploy.env"
    exit 1
fi

source "$ENV_FILE"

# ── Functions ──

build_image() {
    echo "=== Building Docker image ==="
    docker build -t postgres-learning-studio:latest -f docker/Dockerfile .
}

push_image() {
    local registry=$1
    local tag=$2
    local connection=$3

    echo "=== Tagging and pushing ${registry}:${tag} ==="
    docker tag postgres-learning-studio:latest "${registry}:${tag}"

    if [ -z "$connection" ]; then
        snow spcs image-registry token --format=JSON 2>/dev/null | \
            docker login "$(echo $registry | cut -d/ -f1)" --username 0sessiontoken --password-stdin
    else
        snow spcs image-registry token -c "$connection" --format=JSON 2>/dev/null | \
            docker login "$(echo $registry | cut -d/ -f1)" --username 0sessiontoken --password-stdin
    fi

    docker push "${registry}:${tag}"
}

update_stage() {
    local connection_flag=$1
    local tag=$2

    echo "=== Updating manifest/spec to :${tag} ==="
    sed -i "s/postgres-learning-studio:v[0-9]*/postgres-learning-studio:${tag}/g" \
        deploy/manifest.yml deploy/service_spec.yml

    echo "=== Uploading files to stage ==="
    local files=(
        "deploy/manifest.yml"
        "deploy/service_spec.yml"
        "deploy/setup.sql"
        "deploy/config.sql"
        "deploy/services.sql"
        "deploy/benchmark.sql"
        "deploy/README.md"
    )

    for f in "${files[@]}"; do
        snow sql $connection_flag -q "PUT 'file://${f}' ${STAGE}/ OVERWRITE=TRUE AUTO_COMPRESS=FALSE" 2>&1 | tail -1
    done

    # Streamlit files go to streamlit/ subdirectory
    snow sql $connection_flag -q "PUT 'file://deploy/streamlit/setup_ui.py' ${STAGE}/streamlit/ OVERWRITE=TRUE AUTO_COMPRESS=FALSE" 2>&1 | tail -1
    snow sql $connection_flag -q "PUT 'file://deploy/streamlit/environment.yml' ${STAGE}/streamlit/ OVERWRITE=TRUE AUTO_COMPRESS=FALSE" 2>&1 | tail -1
}

register_version() {
    local connection_flag=$1
    local version=$2

    echo "=== Registering version ${version} ==="

    # Deregister if exists (ignore errors)
    snow sql $connection_flag -q "ALTER APPLICATION PACKAGE POSTGRES_LEARNING_STUDIO_PKG DEREGISTER VERSION ${version}" 2>&1 | tail -1 || true

    # Register
    snow sql $connection_flag -q "ALTER APPLICATION PACKAGE POSTGRES_LEARNING_STUDIO_PKG REGISTER VERSION ${version} USING '${STAGE}'" 2>&1 | tail -1
}

create_or_upgrade_app() {
    local connection_flag=$1
    local version=$2

    echo "=== Deploying application (version ${version}) ==="

    # Try UPGRADE first (preserves settings, EAI, compute pool)
    snow sql $connection_flag -q "USE ROLE ACCOUNTADMIN; ALTER APPLICATION PACKAGE POSTGRES_LEARNING_STUDIO_PKG SET DEFAULT RELEASE DIRECTIVE VERSION = ${version} PATCH = 0" 2>&1 | tail -1

    local upgrade_result
    upgrade_result=$(snow sql $connection_flag -q "USE ROLE ACCOUNTADMIN; ALTER APPLICATION POSTGRES_LEARNING_STUDIO UPGRADE" 2>&1)

    if echo "$upgrade_result" | grep -q "error\|Error\|does not exist"; then
        echo "  UPGRADE not available — creating fresh application"
        snow sql $connection_flag -q "USE ROLE ACCOUNTADMIN; CREATE WAREHOUSE IF NOT EXISTS SETUP_WH WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE; USE WAREHOUSE SETUP_WH; CREATE APPLICATION POSTGRES_LEARNING_STUDIO FROM APPLICATION PACKAGE POSTGRES_LEARNING_STUDIO_PKG USING VERSION ${version}" 2>&1 | tail -3
    else
        echo "  UPGRADE succeeded — settings preserved"
        echo "$upgrade_result" | tail -1
    fi
}

verify_app() {
    local connection_flag=$1

    echo "=== Verifying ==="
    snow sql $connection_flag -q "SHOW APPLICATIONS LIKE 'POSTGRES_LEARNING_STUDIO'" 2>&1 | head -5
}

deploy_to_account() {
    local account=$1      # "dev" or "prod"
    local tag=$2           # e.g. "v1"
    local version=$(echo "$tag" | tr '[:lower:]' '[:upper:]')  # e.g. "V1"

    if [ "$account" = "dev" ]; then
        local connection_flag="${DEV_CONNECTION_FLAG:-}"
        local registry=$DEV_REGISTRY
    elif [ "$account" = "prod" ]; then
        local connection_flag="${PROD_CONNECTION_FLAG:-}"
        local registry=$PROD_REGISTRY
    else
        echo "Unknown account: $account (use 'dev' or 'prod')"
        exit 1
    fi

    echo ""
    echo "============================================"
    echo "  Deploying to ${account} as ${version}"
    echo "============================================"

    push_image "$registry" "$tag" "$(echo $connection_flag | sed 's/-c //')"
    update_stage "$connection_flag" "$tag"
    register_version "$connection_flag" "$version"
    create_or_upgrade_app "$connection_flag" "$version"
    verify_app "$connection_flag"

    echo "=== ${account} ${version} DONE ==="
}

# ── Main ──

case "${1}" in
    dev)
        build_image
        deploy_to_account "dev" "${2:?Usage: deploy.sh dev <tag>}"
        ;;
    prod)
        build_image
        deploy_to_account "prod" "${2:?Usage: deploy.sh prod <tag>}"
        ;;
    both)
        build_image
        deploy_to_account "dev" "${2:?Usage: deploy.sh both <dev-tag> <prod-tag>}"
        deploy_to_account "prod" "${3:?Usage: deploy.sh both <dev-tag> <prod-tag>}"
        ;;
    *)
        echo "Usage:"
        echo "  ./deploy.sh dev v1            # Deploy to dev account"
        echo "  ./deploy.sh prod v1           # Deploy to production account"
        echo "  ./deploy.sh both v1 v1        # Deploy to both"
        exit 1
        ;;
esac

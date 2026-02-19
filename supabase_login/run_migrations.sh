#!/bin/bash
# Run all supabase_login migrations against local Supabase via psql.
# Uses psql directly instead of supabase CLI to avoid conflicts with
# the main project's supabase instance on the same localhost.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="$SCRIPT_DIR/supabase/migrations"

# Local Supabase default connection (port 54322, password from supabase start)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-54322}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

export PGPASSWORD="$DB_PASSWORD"

echo "Applying supabase_login migrations to $DB_HOST:$DB_PORT/$DB_NAME"

# Create a tracking table so we don't re-apply migrations
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q <<'SQL'
CREATE TABLE IF NOT EXISTS supabase_login_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);
SQL

# Apply each migration file in sorted order, skipping already-applied ones
applied=0
skipped=0
for migration in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
    version=$(basename "$migration")
    already_applied=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT 1 FROM supabase_login_migrations WHERE version = '$version'" 2>/dev/null || true)

    if [ "$already_applied" = "1" ]; then
        echo "  SKIP  $version (already applied)"
        skipped=$((skipped + 1))
        continue
    fi

    echo "  APPLY $version"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration" -q

    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q -c \
        "INSERT INTO supabase_login_migrations (version) VALUES ('$version')"
    applied=$((applied + 1))
done

echo "Done. Applied: $applied, Skipped: $skipped"

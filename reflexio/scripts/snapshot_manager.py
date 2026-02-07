#!/usr/bin/env python3
"""
Local Supabase snapshot manager — create, restore, and list data snapshots.

Allows you to save all local Supabase table data and later restore it,
even after a `supabase db reset` that drops and re-creates the schema.
Only public-schema data is captured; the supabase_migrations schema is
managed by the Supabase CLI and left untouched.

Usage:
    python -m reflexio.scripts.snapshot_manager create [--name NAME]
    python -m reflexio.scripts.snapshot_manager restore <snapshot_dir>
    python -m reflexio.scripts.snapshot_manager list
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:54322/postgres"
SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshots"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_applied_migrations(db_url: str) -> list[str]:
    """
    Query supabase_migrations.schema_migrations for all applied migration versions.

    Args:
        db_url (str): PostgreSQL connection URL

    Returns:
        list[str]: Sorted list of migration version strings
    """
    conn = psycopg2.connect(db_url)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT version FROM supabase_migrations.schema_migrations ORDER BY version"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def _public_tables_are_empty(db_url: str) -> tuple[bool, list[str]]:
    """
    Check whether all public-schema tables are empty.

    Args:
        db_url (str): PostgreSQL connection URL

    Returns:
        tuple[bool, list[str]]: (all_empty, list_of_non_empty_table_names)
    """
    conn = psycopg2.connect(db_url)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = [row[0] for row in cursor.fetchall()]

        non_empty: list[str] = []
        for table in tables:
            cursor.execute(
                f'SELECT EXISTS (SELECT 1 FROM public."{table}" LIMIT 1)'
            )  # noqa: S608
            if cursor.fetchone()[0]:
                non_empty.append(table)

        return len(non_empty) == 0, non_empty
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_create(args: argparse.Namespace) -> int:
    """
    Create a snapshot of local Supabase data.

    Dumps all public-schema table data using pg_dump (custom format) and
    writes a metadata.json alongside it with the current applied migrations.

    Args:
        args: Parsed CLI arguments (name, db_url)

    Returns:
        int: 0 on success, 1 on failure
    """
    db_url = args.db_url
    name = args.name or "snapshot"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_dir = SNAPSHOTS_DIR / f"{name}_{timestamp}"

    logger.info("Creating snapshot '%s' ...", snapshot_dir.name)

    # 1. Get applied migrations
    try:
        migrations = _get_applied_migrations(db_url)
    except Exception as e:
        logger.error("Failed to read migrations: %s", e)
        return 1

    logger.info("Found %d applied migrations", len(migrations))

    # 2. Create snapshot directory
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 3. pg_dump --data-only for public schema
    dump_file = snapshot_dir / "data.dump"

    # Parse connection details from URL for pg_dump CLI flags
    from urllib.parse import urlparse

    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 54322)
    user = parsed.username or "postgres"
    dbname = parsed.path.lstrip("/") or "postgres"

    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password or "postgres"

    cmd = [
        "pg_dump",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        dbname,
        "--data-only",
        "--schema=public",
        "-Fc",  # custom format
        "-f",
        str(dump_file),
    ]

    logger.info("Running pg_dump ...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("pg_dump failed:\n%s", result.stderr)
        return 1

    # 4. Write metadata
    metadata = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied_migrations": migrations,
    }
    metadata_file = snapshot_dir / "metadata.json"
    metadata_file.write_text(json.dumps(metadata, indent=2))

    dump_size_mb = dump_file.stat().st_size / (1024 * 1024)
    logger.info(
        "Snapshot created: %s (%.1f MB dump, %d migrations recorded)",
        snapshot_dir,
        dump_size_mb,
        len(migrations),
    )
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    """
    Restore a snapshot into the local Supabase database.

    Expects the database to have been reset via `supabase db reset` first
    (schema applied, tables empty). Restores public-schema data with
    pg_restore, then runs any DATA_MIGRATIONS added after the snapshot.

    Args:
        args: Parsed CLI arguments (snapshot_dir, db_url, force)

    Returns:
        int: 0 on success, 1 on failure
    """
    db_url = args.db_url
    snapshot_path = Path(args.snapshot_dir).resolve()

    if not snapshot_path.is_dir():
        logger.error("Snapshot directory not found: %s", snapshot_path)
        return 1

    dump_file = snapshot_path / "data.dump"
    metadata_file = snapshot_path / "metadata.json"

    if not dump_file.exists() or not metadata_file.exists():
        logger.error("Invalid snapshot — missing data.dump or metadata.json")
        return 1

    # 1. Safety check: tables should be empty (post supabase db reset)
    try:
        all_empty, non_empty = _public_tables_are_empty(db_url)
    except Exception as e:
        logger.error("Failed to check table state: %s", e)
        return 1

    if not all_empty and not args.force:
        logger.error(
            "Tables are not empty: %s\n"
            "Run `supabase db reset` first, or use --force to skip this check.",
            ", ".join(non_empty),
        )
        return 1
    elif not all_empty:
        logger.warning(
            "Tables not empty (--force): %s. Existing data may conflict.",
            ", ".join(non_empty),
        )

    # 2. pg_restore
    from urllib.parse import urlparse

    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 54322)
    user = parsed.username or "postgres"
    dbname = parsed.path.lstrip("/") or "postgres"

    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password or "postgres"

    cmd = [
        "pg_restore",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        dbname,
        "--data-only",
        "--disable-triggers",
        "--schema=public",
        str(dump_file),
    ]

    logger.info("Running pg_restore ...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        # pg_restore returns non-zero for warnings too; check stderr
        stderr = result.stderr.strip()
        if stderr:
            logger.warning("pg_restore stderr:\n%s", stderr)
        # Only fail on actual errors (exit code 1 = errors, not just warnings)
        if result.returncode == 1 and "error" in stderr.lower():
            logger.error("pg_restore failed with errors")
            return 1

    logger.info("Data restored successfully")

    # 3. Run data migrations added after the snapshot
    metadata = json.loads(metadata_file.read_text())
    snapshot_migrations = set(metadata.get("applied_migrations", []))

    from reflexio.server.services.storage.supabase_migrations import DATA_MIGRATIONS

    new_versions = sorted(v for v in DATA_MIGRATIONS if v not in snapshot_migrations)

    if new_versions:
        logger.info(
            "Running %d new data migration(s): %s",
            len(new_versions),
            ", ".join(new_versions),
        )
        conn = psycopg2.connect(db_url)
        try:
            cursor = conn.cursor()
            for version in new_versions:
                logger.info("  Running data migration %s ...", version)
                DATA_MIGRATIONS[version](conn, cursor)
            conn.commit()
            logger.info("Data migrations completed")
        except Exception as e:
            conn.rollback()
            logger.error("Data migration failed: %s", e)
            return 1
        finally:
            conn.close()
    else:
        logger.info("No new data migrations to run")

    logger.info("Restore complete")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """
    List available snapshots with their metadata.

    Args:
        args: Parsed CLI arguments (unused)

    Returns:
        int: Always 0
    """
    if not SNAPSHOTS_DIR.exists():
        print("No snapshots directory found.")
        return 0

    snapshot_dirs = sorted(
        [d for d in SNAPSHOTS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    if not snapshot_dirs:
        print("No snapshots found.")
        return 0

    print(f"\nAvailable snapshots ({len(snapshot_dirs)}):")
    print("-" * 70)

    for snap_dir in snapshot_dirs:
        metadata_file = snap_dir / "metadata.json"
        dump_file = snap_dir / "data.dump"

        if not metadata_file.exists():
            print(f"  {snap_dir.name}  (missing metadata.json)")
            continue

        metadata = json.loads(metadata_file.read_text())
        name = metadata.get("name", "?")
        created_at = metadata.get("created_at", "?")
        migrations = metadata.get("applied_migrations", [])
        latest_migration = migrations[-1] if migrations else "none"

        dump_size = ""
        if dump_file.exists():
            size_mb = dump_file.stat().st_size / (1024 * 1024)
            dump_size = f"{size_mb:.1f} MB"

        print(f"  {snap_dir.name}")
        print(f"    Name: {name}")
        print(f"    Created: {created_at}")
        print(f"    Migrations: {len(migrations)} (latest: {latest_migration})")
        if dump_size:
            print(f"    Size: {dump_size}")
        print()

    print("-" * 70)
    print(
        f"Restore with: python -m reflexio.scripts.snapshot_manager restore <snapshot_dir>"
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local Supabase snapshot manager — create, restore, and list data snapshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m reflexio.scripts.snapshot_manager create --name before_reset\n"
            "  python -m reflexio.scripts.snapshot_manager list\n"
            "  python -m reflexio.scripts.snapshot_manager restore reflexio/data/snapshots/before_reset_20260207_120000\n"
        ),
    )

    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_URL,
        help=f"PostgreSQL connection URL (default: {DEFAULT_DB_URL})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_parser = subparsers.add_parser("create", help="Create a new snapshot")
    create_parser.add_argument(
        "--name",
        default="snapshot",
        help="Name prefix for the snapshot directory (default: snapshot)",
    )

    # restore
    restore_parser = subparsers.add_parser("restore", help="Restore a snapshot")
    restore_parser.add_argument(
        "snapshot_dir",
        help="Path to the snapshot directory to restore",
    )
    restore_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip empty-tables safety check",
    )

    # list
    subparsers.add_parser("list", help="List available snapshots")

    args = parser.parse_args()

    if args.command == "create":
        return cmd_create(args)
    elif args.command == "restore":
        return cmd_restore(args)
    elif args.command == "list":
        return cmd_list(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Data migration functions that run alongside SQL schema migrations.

Each function receives (conn, cursor) and must NOT commit or rollback —
the caller (execute_migration) manages the transaction.
"""

import logging
import re
from typing import Callable, Optional

import psycopg2.extensions

logger = logging.getLogger(__name__)

DataMigrationFn = Callable[
    [psycopg2.extensions.connection, psycopg2.extensions.cursor], None
]

# Pattern 1: Structured format produced by _format_structured_feedback_content
#   When: "condition"
#   Do: "action"
#   Don't: "avoid action"
_STRUCTURED_RE = re.compile(
    r'When:\s*"(?P<when>.+?)"'
    r'(?:\s*Do:\s*"(?P<do>.+?)")?'
    r"(?:\s*Don'?t:\s*\"(?P<dont>.+?)\")?",
    re.DOTALL,
)

# Pattern 2: Plain-text sentence form
#   <do_action> instead of <do_not_action> when <when_condition>.
_SENTENCE_RE = re.compile(
    r"^[-\s\"']*(.+?)\s+instead of\s+(.+?)\s+when\s+(.+?)\.?\s*[\"']*$",
    re.IGNORECASE | re.DOTALL,
)


def _parse_feedback_content(
    text: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse feedback_content text into structured fields.

    Tries two formats:
    1. Structured (When/Do/Don't) format
    2. Plain-text sentence ("X instead of Y when Z")

    Args:
        text (str): The feedback_content string to parse

    Returns:
        tuple[str|None, str|None, str|None]: (do_action, do_not_action, when_condition),
            all None if no pattern matches
    """
    # Try structured format first
    m = _STRUCTURED_RE.search(text)
    if m and m.group("when"):
        return (
            _strip_trailing_dot(m.group("do")),
            _strip_trailing_dot(m.group("dont")),
            _strip_trailing_dot(m.group("when")),
        )

    # Try sentence format
    m = _SENTENCE_RE.match(text.strip())
    if m:
        return (
            _strip_trailing_dot(m.group(1)),
            _strip_trailing_dot(m.group(2)),
            _strip_trailing_dot(m.group(3)),
        )

    return None, None, None


def _strip_trailing_dot(s: Optional[str]) -> Optional[str]:
    """Strip trailing period and whitespace from a string, if present."""
    if s is None:
        return None
    return s.strip().rstrip(".")


def _backfill_table(
    cursor: psycopg2.extensions.cursor,
    table: str,
    id_column: str,
) -> tuple[int, int]:
    """
    Backfill do_action, do_not_action, when_condition for one table.

    Args:
        cursor: Database cursor
        table (str): Table name ('raw_feedbacks' or 'feedbacks')
        id_column (str): Primary key column name

    Returns:
        tuple[int, int]: (parsed_count, skipped_count)
    """
    cursor.execute(
        f"SELECT {id_column}, feedback_content FROM {table} "  # noqa: S608
        f"WHERE feedback_content IS NOT NULL "
        f"AND do_action IS NULL AND when_condition IS NULL"
    )
    rows = cursor.fetchall()

    parsed = 0
    skipped = 0

    for row_id, content in rows:
        do_action, do_not_action, when_condition = _parse_feedback_content(content)

        if do_action is not None or when_condition is not None:
            cursor.execute(
                f"UPDATE {table} SET do_action = %s, do_not_action = %s, when_condition = %s "  # noqa: S608
                f"WHERE {id_column} = %s",
                (do_action, do_not_action, when_condition, row_id),
            )
            parsed += 1
        else:
            skipped += 1

    return parsed, skipped


def migrate_20260124120000_structured_feedback_fields(
    conn: psycopg2.extensions.connection,
    cursor: psycopg2.extensions.cursor,
) -> None:
    """
    Backfill structured feedback fields (do_action, do_not_action, when_condition)
    by parsing existing feedback_content in raw_feedbacks and feedbacks tables.

    Only updates rows where feedback_content is present but the structured fields
    are NULL. Rows whose content doesn't match known patterns are left unchanged.

    Args:
        conn: Active database connection (do not commit/rollback)
        cursor: Cursor bound to conn
    """
    for table, id_col in [
        ("raw_feedbacks", "raw_feedback_id"),
        ("feedbacks", "feedback_id"),
    ]:
        parsed, skipped = _backfill_table(cursor, table, id_col)
        logger.info(
            "Migration backfill %s: parsed=%d, skipped=%d", table, parsed, skipped
        )


DATA_MIGRATIONS: dict[str, DataMigrationFn] = {
    "20260124120000": migrate_20260124120000_structured_feedback_fields,
}

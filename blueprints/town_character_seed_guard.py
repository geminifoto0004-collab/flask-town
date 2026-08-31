"""One-time seed guard for TiDB-backed town characters.

Active/core status is user data.  A world with zero active characters is valid
and must not be interpreted as a brand-new installation.
"""

from database import execute_sql, get_db_connection
from .town_character_tidb_runtime import ensure_character_table


def character_table_is_empty():
    ensure_character_table()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, "SELECT COUNT(*) AS row_count FROM town_characters")
        row = cur.fetchone()
        if isinstance(row, dict):
            count = int(row.get("row_count") or 0)
        else:
            count = int((row or [0])[0] or 0)
        return count == 0
    finally:
        conn.close()

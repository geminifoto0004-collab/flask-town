"""Minimal TiDB/MySQL database adapter for standalone TOWN.

This module intentionally has no dependency on the main Flask application's
config, auth, email, ORDER, or other services. TOWN and the main service may
point at the same TiDB database through Render environment variables.
"""

from __future__ import annotations

import os
import urllib.parse

import pymysql
import pymysql.cursors

try:
    from DBUtils.PooledDB import PooledDB
except ImportError:  # pragma: no cover - requirements-town installs DBUtils
    PooledDB = None

_POOL = None


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _connection_config() -> dict:
    database_url = _env("DATABASE_URL")

    if database_url:
        parsed = urllib.parse.urlparse(database_url)
        if parsed.scheme not in {"mysql", "mysql+pymysql", "tidb"}:
            raise ValueError("TOWN DATABASE_URL must use mysql://, mysql+pymysql://, or tidb://")

        query = urllib.parse.parse_qs(parsed.query or "")
        config = {
            "host": parsed.hostname or _env("MYSQL_HOST", "DB_HOST"),
            "port": parsed.port or int(_env("MYSQL_PORT", "DB_PORT", default="4000")),
            "user": urllib.parse.unquote(parsed.username or _env("MYSQL_USER", "DB_USER")),
            "password": urllib.parse.unquote(parsed.password or _env("MYSQL_PASSWORD", "DB_PASSWORD")),
            "database": urllib.parse.unquote((parsed.path or "").lstrip("/")) or _env("MYSQL_DATABASE", "DB_NAME"),
        }
        ssl_required = (query.get("ssl_mode") or query.get("ssl-mode") or [""])[0].upper() == "REQUIRED"
    else:
        config = {
            "host": _env("MYSQL_HOST", "DB_HOST"),
            "port": int(_env("MYSQL_PORT", "DB_PORT", default="4000")),
            "user": _env("MYSQL_USER", "DB_USER"),
            "password": _env("MYSQL_PASSWORD", "DB_PASSWORD"),
            "database": _env("MYSQL_DATABASE", "DB_NAME"),
        }
        ssl_required = _env("DB_SSL_MODE", "MYSQL_SSL_MODE", default="").upper() == "REQUIRED"

    missing = [key for key in ("host", "user", "database") if not config.get(key)]
    if missing:
        raise ValueError("Missing TiDB configuration: " + ", ".join(missing))

    # Match the proven main Flask/TiDB adapter bounds. The admin command already
    # has its own 12-second DeepSeek read limit; database operations must not add
    # another 15 seconds per phase and push the whole request into Gunicorn's
    # worker timeout window.
    config.update(
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10,
    )

    host = str(config.get("host") or "").lower()
    if ssl_required or "tidbcloud.com" in host:
        config["ssl"] = {"check_hostname": False}

    return config


def get_db_connection():
    """Return a pooled PyMySQL connection to the shared TiDB database."""
    global _POOL
    config = _connection_config()

    if PooledDB is None:
        return pymysql.connect(**config)

    if _POOL is None:
        # Same sizing strategy as the stable main Flask service. A warm minimum
        # connection avoids paying a fresh TLS/TiDB connect cost on an admin
        # story request, while ten total connections leave room for browser
        # polling, current-context refresh and background town activity.
        _POOL = PooledDB(
            creator=pymysql,
            mincached=1,
            maxcached=5,
            maxconnections=10,
            blocking=True,
            ping=1,
            **config,
        )
    return _POOL.connection()


def adapt_sql(sql: str) -> str:
    """Convert the TOWN runtime's portable '?' placeholders for PyMySQL."""
    return sql.replace("?", "%s")


def execute_sql(cursor, sql: str, params=None):
    statement = adapt_sql(sql)
    if params is None:
        return cursor.execute(statement)
    return cursor.execute(statement, params)


def executemany_sql(cursor, sql: str, params_list):
    return cursor.executemany(adapt_sql(sql), params_list)

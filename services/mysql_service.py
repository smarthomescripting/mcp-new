"""MySQL tools for working with the local ``llm_playground`` database.

This service connects to a MySQL server on ``localhost`` using the
``llm_playground`` database. Credentials default to the dedicated service
account and can be overridden via environment variables:

* ``LLM_PLAYGROUND_DB_USER`` (defaults to ``"llm_playground"``)
* ``LLM_PLAYGROUND_DB_PASSWORD`` (defaults to ``"kBH4_yW@4bveir9s"``)
* ``LLM_PLAYGROUND_DB_HOST`` (defaults to ``"localhost"``)
* ``LLM_PLAYGROUND_DB_PORT`` (defaults to ``3306``)

All tools require parameterized queries. Use ``%(name)s`` placeholders
within SQL strings and provide matching entries in the ``params``
dictionary to avoid SQL injection. The tools perform basic safety checks
based on the SQL verb and reject obviously unsafe statements (e.g.,
multiple statements separated by semicolons or disallowed verbs). These
tools execute against the live database (they are not suggestions or
dry-run responses). Use ``mysql_ping`` to verify connectivity and
context before issuing queries.
"""
from __future__ import annotations

import os
from typing import Any

import mysql.connector
from fastmcp import FastMCP

from mcp_framework import log_interaction

DB_NAME = os.getenv("LLM_PLAYGROUND_DB_NAME", "llm_playground")
DB_USER = os.getenv("LLM_PLAYGROUND_DB_USER", "llm_playground")
# The service account password for local development.
DB_PASSWORD = os.getenv("LLM_PLAYGROUND_DB_PASSWORD", "kBH4_yW@4bveir9s")
DB_HOST = os.getenv("LLM_PLAYGROUND_DB_HOST", "localhost")
DB_PORT = int(os.getenv("LLM_PLAYGROUND_DB_PORT", "3306"))

ALLOWED_DDL = {"CREATE", "ALTER"}
ALLOWED_DML = {"INSERT", "UPDATE", "DELETE"}


def _get_connection():
    """Open a connection with explicit autocommit control and sane defaults."""

    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
        raise_on_warnings=True,
    )
    conn.autocommit = False  # enforce transactional behavior for writes
    return conn


def _validate_single_statement(query: str) -> str:
    normalized = query.strip().rstrip(";")
    if ";" in normalized:
        raise ValueError("Multiple SQL statements are not allowed in a single call.")
    return normalized


def _assert_allowed(query: str, allowed_verbs: set[str]) -> str:
    normalized = _validate_single_statement(query)
    verb = normalized.split(maxsplit=1)[0].upper()
    if verb not in allowed_verbs:
        raise ValueError(f"Statement must start with one of: {', '.join(sorted(allowed_verbs))}")
    return normalized


def _run_statement(query: str, params: dict[str, Any] | None, expect_result: bool) -> dict[str, Any]:
    normalized = _validate_single_statement(query)
    with _get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(normalized, params or {})
            result: dict[str, Any] = {"rowcount": cursor.rowcount}
            if expect_result:
                result["rows"] = cursor.fetchall()
            conn.commit()
    return result


def register_mysql_service(mcp: FastMCP) -> None:
    """Register MySQL management tools for the ``llm_playground`` database."""

    @mcp.tool()
    def mysql_ping() -> dict[str, Any]:
        """Test connectivity and report the current database/user context."""

        with _get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT DATABASE() AS db, CURRENT_USER() AS user")
                info = cursor.fetchone() or {}
        log_interaction("mysql_ping", {}, info)
        return info

    @mcp.tool()
    def get_db_schema(table_name: str | None = None) -> dict[str, Any]:
        """Describe tables and columns available in the ``llm_playground`` database."""

        filters = ["table_schema = %(schema)s"]
        params: dict[str, Any] = {"schema": DB_NAME}

        if table_name:
            filters.append("table_name = %(table_name)s")
            params["table_name"] = table_name

        query = f"""
            SELECT
                table_name,
                column_name,
                data_type,
                column_type,
                is_nullable,
                column_key
            FROM information_schema.columns
            WHERE {' AND '.join(filters)}
            ORDER BY table_name, ordinal_position
        """

        with _get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

        result = {"rowcount": len(rows), "rows": rows}
        log_interaction("get_db_schema", params, result)
        return result

    @mcp.tool()
    def mysql_schema(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a parameterized ``CREATE`` or ``ALTER`` statement against the schema."""

        normalized = _assert_allowed(sql, ALLOWED_DDL)
        result = _run_statement(normalized, params, expect_result=False)
        log_interaction("mysql_schema", {"sql": normalized, "params": params}, result)
        return result

    @mcp.tool()
    def mysql_select(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a parameterized ``SELECT`` query and return rows."""

        normalized = _assert_allowed(sql, {"SELECT"})
        result = _run_statement(normalized, params, expect_result=True)
        log_interaction("mysql_select", {"sql": normalized, "params": params}, result)
        return result

    @mcp.tool()
    def mysql_write(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute ``INSERT``, ``UPDATE``, or ``DELETE`` statements and report affected rows."""

        normalized = _assert_allowed(sql, ALLOWED_DML)
        result = _run_statement(normalized, params, expect_result=False)
        log_interaction("mysql_write", {"sql": normalized, "params": params}, result)
        return result

    @mcp.tool()
    def mysql_execute(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a single parameterized DDL/DML statement (excluding DROP/TRUNCATE)."""

        normalized = _validate_single_statement(sql)
        verb = normalized.split(maxsplit=1)[0].upper()
        if verb in {"DROP", "TRUNCATE"}:
            raise ValueError("DROP and TRUNCATE statements are blocked for safety.")
        result = _run_statement(normalized, params, expect_result=verb == "SELECT")
        log_interaction(
            "mysql_execute",
            {"sql": normalized, "params": params, "verb": verb},
            result,
        )
        return result

    # Verify connectivity as soon as the tools are registered so that callers know
    # the database is reachable and properly configured. If the database is
    # temporarily unavailable we still want to register the tools so that callers
    # receive a meaningful runtime error instead of the service failing to start.
    try:
        with _get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT DATABASE() AS db, CURRENT_USER() AS user")
                startup_info = cursor.fetchone() or {}
        log_interaction("mysql_startup_ping", {}, startup_info)
    except Exception as exc:  # pragma: no cover - defensive startup guard
        log_interaction(
            "mysql_startup_ping_failed", {"error": str(exc), "type": type(exc).__name__}, {}
        )

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
multiple statements separated by semicolons or disallowed verbs).
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
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


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

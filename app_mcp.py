"""Composable MCP server that can host multiple services."""
from __future__ import annotations

from mcp_framework import ServiceDefinition, attach_request_logger, create_mcp_server, log_interaction
from services import (
    register_echo_service,
    register_iban_service,
    register_math_service,
    register_newsapi_service,
    register_web_fetch_service,
)

services = [
    ServiceDefinition(
        name="iban",
        description="Validate IBAN strings and return normalized details.",
        register=register_iban_service,
    ),
    ServiceDefinition(
        name="web_fetch",
        description="Fetch a web page and return its plain text content.",
        register=register_web_fetch_service,
    ),
    ServiceDefinition(
        name="newsapi",
        description="Search the NewsAPI.org index for articles by keyword.",
        register=register_newsapi_service,
    ),
    ServiceDefinition(
        name="math_operations",
        description="Perform arithmetic calculations including factorial and Fibonacci.",
        register=register_math_service,
    ),
    ServiceDefinition(
        name="echo",
        description="Repeat any provided message for quick connectivity checks.",
        register=register_echo_service,
    ),
]

mcp, http_app = create_mcp_server(services, app_name="utility-suite", json_response=True)
attach_request_logger(http_app)

log_interaction("startup", {"services": [service.name for service in services]}, {"app": "utility-suite"})

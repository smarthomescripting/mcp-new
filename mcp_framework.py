"""Utilities for composing FastMCP servers from reusable services."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable

from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("uvicorn.error")


@dataclass
class ServiceDefinition:
    """Describe a service that can register tools on a FastMCP instance."""

    name: str
    description: str
    register: Callable[[FastMCP], None]


def log_interaction(action: str, input_data: Any, output_data: Any) -> None:
    """Emit a structured log entry via the standard uvicorn logger (JSON Lines)."""

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "input": input_data,
        "output": output_data,
    }

    try:
        serialized = json.dumps(entry, ensure_ascii=False)
    except TypeError:
        sanitized_entry = {
            "timestamp": entry["timestamp"],
            "action": entry["action"],
            "input": json.loads(json.dumps(entry["input"], default=str)),
            "output": json.loads(json.dumps(entry["output"], default=str)),
        }
        serialized = json.dumps(sanitized_entry, ensure_ascii=False)

    logger.info(serialized)


def create_mcp_server(
    services: Iterable[ServiceDefinition],
    *,
    app_name: str = "multi-service",
    json_response: bool = True,
):
    """Create an MCP server instance and register all provided services."""

    mcp = FastMCP(app_name)
    mcp.settings.json_response = json_response

    for service in services:
        service.register(mcp)

    app = mcp.http_app()
    return mcp, app


def attach_request_logger(app, *, action: str = "http_request") -> None:
    """Attach middleware that logs incoming HTTP requests and responses."""

    class RequestLoggerMiddleware(BaseHTTPMiddleware):
        def __init__(self, app):
            super().__init__(app)
            self.action = action

        async def dispatch(
            self, request: Request, call_next: RequestResponseEndpoint
        ) -> Response:
            request_body = await request.body()
            request_info: dict[str, Any] = {
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query,
                "client": request.client.host if request.client else None,
            }

            if request_body:
                try:
                    payload = json.loads(request_body.decode("utf-8"))
                    if isinstance(payload, dict):
                        request_info["jsonrpc_method"] = payload.get("method")
                        if "params" in payload and isinstance(payload["params"], dict):
                            request_info["param_keys"] = sorted(payload["params"].keys())
                except Exception as exc:  # pragma: no cover - logging should not block requests
                    request_info["body_parse_error"] = str(exc)

            response: Response | None = None
            error_detail: dict[str, Any] | None = None

            try:
                response = await call_next(request)
                return response
            except Exception as exc:  # pragma: no cover - logging should not block requests
                error_detail = {"error": str(exc), "type": exc.__class__.__name__}
                raise
            finally:
                output_data: dict[str, Any] = {
                    "status_code": response.status_code if response else None
                }
                if error_detail:
                    output_data.update(error_detail)
                log_interaction(self.action, request_info, output_data)

    app.add_middleware(RequestLoggerMiddleware)

# iban_mcp_server.py
import json
import logging
from datetime import datetime
from typing import Any, Optional

import uvicorn
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from iban_utils import validate_iban

# Create MCP server
mcp = FastMCP("IBAN Checker")
# Configure JSON response at the settings level to avoid the deprecated
# constructor argument.
mcp.settings.json_response = True

logger = logging.getLogger("uvicorn.error")


def log_interaction(action: str, input_data: Any, output_data: Any) -> None:
    """Emit a structured log entry via the standard uvicorn logger.

    Uses JSON Lines format so each interaction stays on a single line.
    Falls back to stringifying objects that are not JSON serializable to
    avoid breaking logging for unexpected data shapes.
    """

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


class IbanResult(BaseModel):
    valid: bool
    normalized_iban: str
    country: Optional[str] = None
    reason: Optional[str] = None


@mcp.tool()
def iban_check(iban: str) -> IbanResult:
    """
    Validate an IBAN and return structured result.

    Args:
        iban: IBAN string (can contain spaces, lower/upper case)

    Returns:
        IbanResult: {valid, normalized_iban, country, reason}
    """
    try:
        result_dict = validate_iban(iban)
    except Exception as exc:  # pragma: no cover - defensive logging for unexpected errors
        log_interaction(
            "iban_check_error",
            {"iban": iban},
            {"error": str(exc), "type": exc.__class__.__name__},
        )
        raise

    log_interaction("iban_check", {"iban": iban}, result_dict)
    return IbanResult(**result_dict)


# Streamable HTTP transport; by default this serves on http://localhost:8000/mcp
# (same pattern as the official FastMCP quickstart).
log_interaction("startup", {}, {"message": "IBAN MCP server starting"})

app = mcp.streamable_http_app()


@app.middleware("http")
async def log_requests(request: Request, call_next):
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
        except Exception as exc:  # pragma: no cover - logging should not break requests
            request_info["body_parse_error"] = str(exc)

    response: Response | None = None
    error_detail: dict[str, Any] | None = None

    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        error_detail = {"error": str(exc), "type": exc.__class__.__name__}
        raise
    finally:
        output_data: dict[str, Any] = {"status_code": response.status_code if response else None}
        if error_detail:
            output_data.update(error_detail)
        log_interaction("http_request", request_info, output_data)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=mcp.settings.host,
        port=mcp.settings.port,
        log_level=mcp.settings.log_level.lower(),
    )

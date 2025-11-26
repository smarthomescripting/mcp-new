# iban_mcp_server.py
from datetime import datetime
from pathlib import Path
import json
from typing import Any, Optional

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

from iban_utils import validate_iban

# Create MCP server
mcp = FastMCP("IBAN Checker", json_response=True)

LOG_PATH = Path(__file__).with_name("mcp.log")


def log_interaction(action: str, input_data: Any, output_data: Any) -> None:
    """Append a structured log entry to mcp.log.

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

    LOG_PATH.touch(exist_ok=True)

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

    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(serialized + "\n")


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


if __name__ == "__main__":
    # Streamable HTTP transport; by default this serves on http://localhost:8000/mcp
    # (same pattern as the official FastMCP quickstart).
    log_interaction("startup", {}, {"message": "IBAN MCP server starting"})
    mcp.run(transport="streamable-http")

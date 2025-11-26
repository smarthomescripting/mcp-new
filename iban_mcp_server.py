# iban_mcp_server.py
from datetime import datetime
from pathlib import Path
import json
from typing import Optional

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

from iban_utils import validate_iban

# Create MCP server
mcp = FastMCP("IBAN Checker", json_response=True)

LOG_PATH = Path(__file__).with_name("mcp.log")


def log_interaction(action: str, input_data, output_data) -> None:
    """Append a structured log entry to mcp.log."""

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "input": input_data,
        "output": output_data,
    }

    LOG_PATH.touch(exist_ok=True)

    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
    result_dict = validate_iban(iban)
    log_interaction("iban_check", {"iban": iban}, result_dict)
    return IbanResult(**result_dict)


if __name__ == "__main__":
    # Streamable HTTP transport; by default this serves on http://localhost:8000/mcp
    # (same pattern as the official FastMCP quickstart).
    mcp.run(transport="streamable-http")

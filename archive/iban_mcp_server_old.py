# iban_mcp_server.py
from typing import Optional

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

from iban_utils import validate_iban

# Create MCP server
mcp = FastMCP("IBAN Checker", json_response=True)


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
    return IbanResult(**result_dict)


if __name__ == "__main__":
    # Streamable HTTP transport; by default this serves on http://localhost:8000/mcp
    # (same pattern as the official FastMCP quickstart).
    mcp.run(transport="streamable-http")

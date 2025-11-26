"""IBAN validation service for MCP."""
from __future__ import annotations

from fastmcp import FastMCP
from pydantic import BaseModel

from iban_utils import validate_iban
from mcp_framework import log_interaction


class IbanResult(BaseModel):
    valid: bool
    normalized_iban: str
    country: str | None = None
    reason: str | None = None


def register_iban_service(mcp: FastMCP) -> None:
    """Register IBAN validation tools on the provided MCP instance."""

    @mcp.tool()
    def iban_check(iban: str) -> IbanResult:
        """
        Validate an IBAN and return structured result.
        """

        try:
            result_dict = validate_iban(iban)
        except Exception as exc:
            log_interaction(
                "iban_check_error",
                {"iban": iban},
                {"error": str(exc), "type": exc.__class__.__name__},
            )
            raise

        log_interaction("iban_check", {"iban": iban}, result_dict)
        return IbanResult(**result_dict)

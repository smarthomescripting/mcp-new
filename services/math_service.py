"""Math operations service for MCP."""
from __future__ import annotations

import math
from functools import reduce
from typing import Iterable

from fastmcp import FastMCP

from mcp_framework import log_interaction


class MathError(ValueError):
    """Raised when math operations receive invalid input."""


_DEF_OPERATION_HELP = (
    "Supported operations: add, subtract, multiply, divide, modulo, power, "
    "sqrt, factorial, fibonacci, gcd."
)


def _require_values(values: Iterable[float] | None) -> list[float]:
    if not values:
        raise MathError("At least one value is required for the requested operation.")
    return list(values)


def _binary(values: list[float], operation: str) -> tuple[float, float]:
    if len(values) != 2:
        raise MathError(f"Operation '{operation}' requires exactly two values.")
    return values[0], values[1]


def register_math_service(mcp: FastMCP) -> None:
    """Register a tool that performs common math operations."""

    @mcp.tool()
    def math_operations(operation: str, values: list[float]) -> dict[str, float | int]:
        """
        Perform a math operation on the provided values.

        - add: sum all values
        - subtract: subtract subsequent values from the first value
        - multiply: multiply all values together
        - divide: sequentially divide the first value by subsequent values
        - modulo: compute the remainder of the first value divided by the second
        - power: raise the first value to the power of the second
        - sqrt: square root of the first value
        - factorial: factorial of the first value (non-negative integer)
        - fibonacci: nth Fibonacci number where n is the first value (non-negative integer)
        - gcd: greatest common divisor of all integer values
        """

        op = operation.strip().lower()
        input_payload = {"operation": op, "values": values}

        try:
            raw_values = _require_values(values)

            if op == "add":
                result: float | int = sum(raw_values)
            elif op == "subtract":
                if len(raw_values) < 2:
                    raise MathError("Subtract requires at least two values.")
                result = raw_values[0] - sum(raw_values[1:])
            elif op == "multiply":
                result = reduce(lambda x, y: x * y, raw_values)
            elif op == "divide":
                if len(raw_values) < 2:
                    raise MathError("Divide requires at least two values.")
                result = reduce(_safe_divide, raw_values)
            elif op == "modulo":
                dividend, divisor = _binary(raw_values, op)
                result = _safe_modulo(dividend, divisor)
            elif op == "power":
                base, exponent = _binary(raw_values, op)
                result = base**exponent
            elif op == "sqrt":
                value = raw_values[0]
                if value < 0:
                    raise MathError("Square root requires a non-negative value.")
                result = math.sqrt(value)
            elif op == "factorial":
                integer_value = _require_non_negative_int(raw_values[0], op)
                result = math.factorial(integer_value)
            elif op == "fibonacci":
                integer_value = _require_non_negative_int(raw_values[0], op)
                result = _fibonacci(integer_value)
            elif op == "gcd":
                if len(raw_values) < 2:
                    raise MathError("GCD requires at least two values.")
                integer_values = [_require_int(value, op) for value in raw_values]
                result = reduce(math.gcd, integer_values)
            else:
                raise MathError(f"Unknown operation '{operation}'. {_DEF_OPERATION_HELP}")
        except Exception as exc:
            log_interaction(
                "math_operations_error",
                input_payload,
                {"error": str(exc), "type": exc.__class__.__name__},
            )
            raise

        output = {"operation": op, "result": result}
        log_interaction("math_operations", input_payload, output)
        return output


def _safe_divide(x: float, y: float) -> float:
    if y == 0:
        raise MathError("Division by zero is not allowed.")
    return x / y


def _safe_modulo(x: float, y: float) -> float:
    if y == 0:
        raise MathError("Modulo by zero is not allowed.")
    return x % y


def _require_int(value: float, operation: str) -> int:
    if not float(value).is_integer():
        raise MathError(f"Operation '{operation}' requires integer values.")
    return int(value)


def _require_non_negative_int(value: float, operation: str) -> int:
    integer_value = _require_int(value, operation)
    if integer_value < 0:
        raise MathError(f"Operation '{operation}' requires a non-negative integer.")
    return integer_value


def _fibonacci(n: int) -> int:
    if n in (0, 1):
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

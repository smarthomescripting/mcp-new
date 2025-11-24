# iban_utils.py
import re

# Minimal IBAN length map (extend as needed)
IBAN_LENGTHS = {
    "DE": 22,
    "BE": 16,
    "NL": 18,
    "FR": 27,
    "ES": 24,
    "IT": 27,
    "AT": 20,
    "CH": 21,
    "GB": 22,
    # add more if required
}


def normalize_iban(iban: str) -> str:
    """Remove spaces and make upper-case."""
    return re.sub(r"\s+", "", iban).upper()


def iban_mod97(numeric_iban: str) -> int:
    """
    Compute numeric_iban % 97 using the official IBAN iterative algorithm.
    numeric_iban must be a string of digits.
    """
    remainder = 0
    for ch in numeric_iban:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder


def iban_to_numeric(iban: str) -> str:
    """
    Convert IBAN letters to numbers (A=10 ... Z=35) for MOD97 check.
    """
    result = []
    for ch in iban:
        if ch.isdigit():
            result.append(ch)
        elif ch.isalpha():
            result.append(str(ord(ch) - 55))  # A -> 10, B -> 11, ...
        else:
            raise ValueError(f"Invalid character in IBAN: {ch!r}")
    return "".join(result)


def validate_iban(iban_input: str) -> dict:
    """
    Validate an IBAN and return a structured dict.
    """
    iban = normalize_iban(iban_input)

    if len(iban) < 4:
        return {
            "valid": False,
            "normalized_iban": iban,
            "reason": "IBAN too short (must have at least 4 characters).",
        }

    country = iban[:2]
    length = len(iban)

    expected_len = IBAN_LENGTHS.get(country)
    if expected_len is None:
        return {
            "valid": False,
            "normalized_iban": iban,
            "country": country,
            "reason": f"Unsupported or unknown country code: {country}",
        }

    if length != expected_len:
        return {
            "valid": False,
            "normalized_iban": iban,
            "country": country,
            "reason": f"Invalid length for country {country} "
                      f"(expected {expected_len}, got {length}).",
        }

    # Rearrange: move first 4 chars to the end
    rearranged = iban[4:] + iban[:4]

    try:
        numeric = iban_to_numeric(rearranged)
    except ValueError as e:
        return {
            "valid": False,
            "normalized_iban": iban,
            "country": country,
            "reason": str(e),
        }

    remainder = iban_mod97(numeric)

    if remainder == 1:
        return {
            "valid": True,
            "normalized_iban": iban,
            "country": country,
            "reason": "IBAN is valid.",
        }
    else:
        return {
            "valid": False,
            "normalized_iban": iban,
            "country": country,
            "reason": f"MOD97 check failed (remainder={remainder}, expected 1).",
        }

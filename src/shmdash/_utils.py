import re
from typing import Any


def to_identifier(identifier: Any) -> str:
    """Convert to identifier (alphanumeric and "_", max. 32 chars)."""
    result = str(identifier)
    result = re.sub(r"[^a-zA-Z0-9_]", "", result)  # remove non-allowed chars
    return result[:32]  # crop to max. 32 chars

"""
Utility functions for the Poker Bot worker.
"""

import ast
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def get_env(var_name: str) -> Optional[Any]:
    """
    Retrieves an environment variable, handling potential JSON-encoded strings
    from AWS Secrets Manager.

    Args:
        var_name: The name of the environment variable.

    Returns:
        The value of the environment variable, or None if not set.
    """
    val = os.environ.get(var_name)
    if not val:
        return None

    data = None
    try:
        data = json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            # Fallback for single-quoted strings that aren't valid JSON
            data = ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return val

    if isinstance(data, dict):
        # Support secrets stored as JSON keys (common in AWS Secrets Manager)
        # Try the variable name itself, or its lowercase version
        if var_name in data:
            return data[var_name]
        if var_name.lower() in data:
            return data[var_name.lower()]
        if var_name.upper() in data:
            return data[var_name.upper()]

        # If no key matches but there's only one key, return that
        if len(data) == 1:
            return list(data.values())[0]

    return data

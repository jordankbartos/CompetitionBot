import ast
import json
import logging
import os

logger = logging.getLogger(__name__)


def _parse_secret_value(val):
    """Attempt to parse a secret value as JSON or a Python literal, falling back to raw string."""
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return val


def get_secret(var_name):
    """Robustly fetch a secret from environment, handling JSON blobs or string literals."""
    val = os.environ.get(var_name)
    if not val:
        raise ValueError(f"Environment variable {var_name} not set")

    data = _parse_secret_value(val)

    if isinstance(data, dict):
        # Support secrets stored as JSON keys (common in AWS Secrets Manager)
        for key in [var_name, var_name.lower(), var_name.upper()]:
            if key in data:
                return data[key]
        # If no key matches, but there's only one key, return that
        if len(data) == 1:
            return list(data.values())[0]
        raise ValueError(f"Could not find matching key for {var_name} in secret dictionary")

    return data

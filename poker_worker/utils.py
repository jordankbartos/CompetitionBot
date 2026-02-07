import os
import json

def get_env(var_name):
    """
    Retrieves an environment variable, handling potential JSON-encoded strings 
    from AWS Secrets Manager.
    """
    val = os.environ.get(var_name)
    if not val:
        return val
    try:
        data = json.loads(val)
        if isinstance(data, dict):
            # If it's a dict, try the variable name or its lowercase version, 
            # otherwise return the first value
            return data.get(var_name, data.get(var_name.lower(), list(data.values())[0]))
        return data
    except (json.JSONDecodeError, TypeError):
        return val

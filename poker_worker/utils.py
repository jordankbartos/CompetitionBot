import os
import json
import ast

def get_env(var_name):
    """
    Retrieves an environment variable, handling potential JSON-encoded strings 
    from AWS Secrets Manager. Handles both double and single quotes.
    """
    val = os.environ.get(var_name)
    if not val:
        return val
    
    data = None
    try:
        data = json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            # Fallback for single-quoted strings that aren't valid JSON
            data = ast.literal_eval(val)
        except:
            return val
            
    if isinstance(data, dict):
        # If it's a dict, try the variable name or its lowercase version, 
        # otherwise return the first value
        return data.get(var_name, data.get(var_name.lower(), list(data.values())[0]))
    return data

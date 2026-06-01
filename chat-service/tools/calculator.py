DEFINITION = {
    "name": "calculator",
    "description": "Evaluate a mathematical expression and return the numeric result. Use for arithmetic, percentages, unit conversions, and any numeric computation.",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A valid Python math expression, e.g. '2 + 2' or '100 * 1.18'"
            }
        },
        "required": ["expression"]
    },
    "state_schema": {},
    "response_types": ["text"],
}


def handler(params: dict, state: dict) -> dict:
    import math
    allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    allowed["abs"] = abs
    allowed["round"] = round
    try:
        result = eval(params["expression"], {"__builtins__": {}}, allowed)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

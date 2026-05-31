DEFINITION = {
    "name": "get_current_time",
    "description": "Get the current date and time. Use when the user asks what time or date it is.",
    "parameters": {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name e.g. 'Asia/Kolkata', 'UTC'. Defaults to UTC if not provided."
            }
        },
        "required": []
    },
    "state_schema": {},
    "response_types": ["text"],
}


def handler(params: dict, state: dict) -> dict:
    from datetime import datetime, timezone
    import zoneinfo

    tz_name = params.get("timezone", "UTC")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    now = datetime.now(tz)
    return {"datetime": now.strftime("%Y-%m-%d %H:%M:%S %Z")}

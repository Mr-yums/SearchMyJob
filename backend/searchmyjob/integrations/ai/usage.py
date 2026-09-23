import json


def codex_usage(output):
    """Sum completed turns; cached input is a subset, never added twice."""
    totals = dict(input_tokens=0, output_tokens=0, cached_input_tokens=0)
    measured = False
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError, TypeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            return None
        values = {
            key: usage.get(key, 0 if key == "cached_input_tokens" else None) for key in totals
        }
        if any(type(value) is not int or value < 0 for value in values.values()):
            return None
        if values["cached_input_tokens"] > values["input_tokens"]:
            return None
        for key, value in values.items():
            totals[key] += value
        measured = True
    return totals if measured else None

# handler.py

was_cold = True  # Global variable to detect cold/warm start

def handler(event):
    global was_cold

    if was_cold:
        warm = False  # First time => cold start
        was_cold = False
    else:
        warm = True   # Subsequent call => warm start

    return {
        "message": "Hello from Docker!",
        "input": event,
        "warm": warm
    }

if __name__ == "__main__":
    import json
    import sys

    event = {"key": "value"}  # Simulated test input
    result = handler(event)
    print(json.dumps(result))

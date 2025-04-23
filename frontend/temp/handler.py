def handler(event):
    operation = event.get("operation")
    numbers = event.get("numbers", [])

    if operation == "sum":
        result = sum(numbers)
    elif operation == "multiply":
        result = 1
        for num in numbers:
            result *= num
    elif operation == "average":
        result = sum(numbers) / len(numbers)
    else:
        return {"error": "Invalid operation"}

    return {
        "operation": operation,
        "numbers": numbers,
        "result": result
    }

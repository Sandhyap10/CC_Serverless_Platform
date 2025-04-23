
    FROM python:3.9-slim
    WORKDIR /app
    COPY handler.py handler.py
    COPY input.json input.json
    CMD ["python", "-c", "import json; from handler import handler; print(json.dumps(handler(json.load(open('input.json')))))"]
    
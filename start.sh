#!/bin/bash
set -e

uvicorn api:api --host 127.0.0.1 --port 8000 &

python -c "
import time, requests
for i in range(60):
    try:
        requests.get('http://127.0.0.1:8000/health', timeout=2)
        print('API is up', flush=True)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('API never started')
"

python ui.py
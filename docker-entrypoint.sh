#!/bin/sh
set -e

echo "=== checking ml model (model.pt) ==="
python download_model.py || echo "ml model was not downloaded, api будет работать только на regex"

echo "=== starting api ==="
uvicorn app.main:app --host 0.0.0.0 --port 8000



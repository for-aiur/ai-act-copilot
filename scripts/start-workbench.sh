#!/bin/sh
set -eu
python -m aiact.workbench.bootstrap
exec python -m uvicorn aiact.workbench.api:create_app --factory --host 0.0.0.0 --port 8000 --workers 1

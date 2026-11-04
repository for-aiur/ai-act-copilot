#!/bin/sh
set -eu
python - <<'PY'
import os
import sys
import time

url = os.environ.get("DATABASE_URL", "sqlite:///.aiact-workbench/aiact.db")
if url.startswith(("postgresql://", "postgresql+psycopg://")):
    from sqlalchemy import create_engine, text
    engine = create_engine(url, pool_pre_ping=True)
    for attempt in range(90):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
            break
        except Exception:
            if attempt == 89:
                engine.dispose()
                sys.exit("PostgreSQL did not become ready. Check DATABASE_URL and the postgres Compose profile.")
            time.sleep(1)
PY
python -m aiact.workbench.bootstrap
exec python -m uvicorn aiact.workbench.api:create_app --factory --host 0.0.0.0 --port 8000 --workers 1

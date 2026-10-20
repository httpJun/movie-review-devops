#!/usr/bin/env bash
set -euo pipefail
component="$1"
image="$2"
case "$component" in
  backend)
    # Import the production ML stack and launch the real browser, without API/model downloads.
    docker run --rm -i "$image" python - <<'PYCODE'
import numpy as np
from sentence_transformers import SentenceTransformer, models
from playwright.sync_api import sync_playwright
import hdbscan
import psycopg

model = SentenceTransformer(modules=[models.BoW(["great", "bad"])])
vectors = model.encode(["great", "bad"])
assert vectors.shape == (2, 2) and np.isfinite(vectors).all()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    page.set_content("<title>smoke</title>")
    assert page.title() == "smoke"
    browser.close()
print("ML encode, PostgreSQL driver import and Chromium launch passed")
PYCODE
    port=8000
    args=(-e DATABASE_URL=postgresql+psycopg://smoke:smoke@127.0.0.1/smoke -e SCHEDULER_ENABLED=false)
    ;;
  frontend)
    port=3000
    args=()
    ;;
  *) echo "Unknown component: $component" >&2; exit 2 ;;
esac
container=$(docker run -d -p "127.0.0.1:${port}:${port}" "${args[@]}" "$image")
cleanup() {
  docker logs "$container"
  docker rm -f "$container" >/dev/null
}
trap cleanup EXIT
python3 - "$port" "$component" <<'PYCODE'
import json
import sys
import time
import urllib.error
import urllib.request

port, component = sys.argv[1:]
url = f"http://127.0.0.1:{port}"
for attempt in range(60):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = response.read()
            assert response.status == 200
        if component == "backend":
            assert json.loads(body)["message"] == "Movie Review Analysis System API"
            with urllib.request.urlopen(url + "/openapi.json", timeout=2) as response:
                assert json.load(response)["paths"]
        else:
            assert b"<html" in body.lower()
        print(f"{component}: production entrypoint and HTTP smoke passed")
        break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        if attempt == 59:
            raise
        time.sleep(1)
PYCODE

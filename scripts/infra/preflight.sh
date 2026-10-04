#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

failed=0

for tool in aws terraform kubectl helm python3 openssl; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '[OK] Tool: %s\n' "$tool"
  else
    printf '[FAIL] Missing tool: %s\n' "$tool"
    failed=1
  fi
done

files=(
  infra/terraform/eks.tf
  k8s/eks-demo/namespace.yaml
  k8s/eks-demo/resources.json
  k8s/eks-demo/migrate.json
  k8s/gitops/movie-app/deployment-backend.json
  k8s/gitops/movie-app/deployment-frontend.json
  k8s/argocd/movie-app.yaml
  k8s/argocd/values.yaml
  k8s/monitoring/values-demo.yaml
  k8s/monitoring/chart-version.txt
  k8s/monitoring/backend-cpu-alert.yaml
)

for file in "${files[@]}"; do
  if [[ -s "$file" ]]; then
    printf '[OK] File: %s\n' "$file"
  else
    printf '[FAIL] Missing or empty file: %s\n' "$file"
    failed=1
  fi
done

if [[ "$failed" -ne 0 ]]; then
  echo "Preflight failed. Fix the items above."
  exit 1
fi

python3 - <<'PY'
import json
import re
from pathlib import Path

def read_json(path):
    return json.loads(Path(path).read_text())

def image_for(resource, name):
    containers = resource["spec"]["template"]["spec"]["containers"]
    return next(c["image"] for c in containers if c["name"] == name)

resources = read_json("k8s/eks-demo/resources.json")
migration = read_json("k8s/eks-demo/migrate.json")

for name in ("backend", "frontend"):
    deployment = read_json(
        f"k8s/gitops/movie-app/deployment-{name}.json"
    )
    image = image_for(deployment, name)

    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image):
        raise SystemExit(f"[FAIL] {name}: image must use a SHA256 digest")

    snapshot = next(
        item for item in resources["items"]
        if item["kind"] == "Deployment"
        and item["metadata"]["name"] == name
    )
    if image_for(snapshot, name) != image:
        raise SystemExit(
            f"[FAIL] {name}: GitOps and eks-demo images differ. "
            "Review and refresh the demo snapshot."
        )

    if name == "backend":
        migration_image = migration["spec"]["template"]["spec"]["containers"][0]["image"]
        if migration_image != image:
            raise SystemExit("[FAIL] Migration and backend images differ")

    print(f"[OK] {name}: digest pinned and demo image matches")

chart_version = Path("k8s/monitoring/chart-version.txt").read_text().strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", chart_version):
    raise SystemExit("[FAIL] Invalid monitoring chart version")

print(f"[OK] Monitoring chart version: {chart_version}")
PY

echo "Preflight passed (local checks only)."
echo "AWS credentials, ECR image availability and cluster access are not checked."

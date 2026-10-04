#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

MODE="${1:---check}"
case "$MODE" in
  --check|--apply) ;;
  *)
    echo "Usage: bash scripts/infra/install-monitoring.sh [--check|--apply]"
    exit 1
    ;;
esac

bash scripts/infra/preflight.sh

VERSION="$(tr -d '[:space:]' < k8s/monitoring/chart-version.txt)"
VALUES="$ROOT/k8s/monitoring/values-demo.yaml"
ALERT="$ROOT/k8s/monitoring/backend-cpu-alert.yaml"
CONTEXT="movie-review-eks"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/movie-monitoring.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "Downloading kube-prometheus-stack $VERSION"
helm pull kube-prometheus-stack \
  --repo https://prometheus-community.github.io/helm-charts \
  --version "$VERSION" \
  --untar \
  --untardir "$WORK_DIR"

CHART="$WORK_DIR/kube-prometheus-stack"

helm lint "$CHART" \
  --kube-version 1.35.0 \
  -f "$VALUES"

# Render locally without printing generated Secrets.
helm template monitoring "$CHART" \
  --namespace monitoring \
  --kube-version 1.35.0 \
  -f "$VALUES" >/dev/null

echo "Chart lint and local rendering passed."

if [[ "$MODE" == "--check" ]]; then
  echo "Check complete. No AWS/Kubernetes requests were made."
  echo "Chart download required internet access."
  exit 0
fi

kubectl --context "$CONTEXT" --request-timeout=30s \
  get nodes

helm upgrade --install monitoring "$CHART" \
  --kube-context "$CONTEXT" \
  --namespace monitoring \
  --create-namespace \
  -f "$VALUES" \
  --wait \
  --timeout 10m

kubectl --context "$CONTEXT" wait \
  --for=condition=Established \
  crd/prometheusrules.monitoring.coreos.com \
  --timeout=120s

kubectl --context "$CONTEXT" apply -f "$ALERT"

kubectl --context "$CONTEXT" -n monitoring get pods,svc
kubectl --context "$CONTEXT" -n monitoring \
  get prometheusrule movie-backend-demo-alerts

echo "Installation finished."
echo "Verify scrape targets and alert-rule loading in Prometheus."

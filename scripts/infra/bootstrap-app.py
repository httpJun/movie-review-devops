#!/usr/bin/env python3
"""Temporary movie-app bootstrap. Default: offline checks. Live: --apply.

Install as scripts/infra/bootstrap-app.py. Run only one copy at a time.
Existing PostgreSQL StatefulSets and Secrets are never replaced.
This is a bootstrap utility, not a production database upgrade workflow.
"""
import argparse
import json
import secrets
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTEXT = "movie-review-eks"
NS = "movie-app"


def run(args, payload=None):
    return subprocess.run(
        args, input=json.dumps(payload) if payload is not None else None,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.strip()


def kube(*args, payload=None):
    return run(["kubectl", "--context", CONTEXT, "--request-timeout=30s", *args], payload)


def get(kind, name, namespace=NS):
    args = ["get", kind, name, "--ignore-not-found", "-o", "json"]
    if namespace:
        args += ["-n", namespace]
    raw = kube(*args)
    return json.loads(raw) if raw else None


def read(relative):
    return json.loads((ROOT / relative).read_text())


def apply(resource):
    print(kube("apply", "-f", "-", payload=resource), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Modify the existing EKS cluster")
    args = parser.parse_args()
    subprocess.run(["bash", str(ROOT / "scripts/infra/preflight.sh")], check=True)
    items = read("k8s/eks-demo/resources.json")["items"]
    db = next(x for x in items if x["kind"] == "StatefulSet" and x["metadata"]["name"] == "postgres")
    db_service = next(x for x in items if x["kind"] == "Service" and x["metadata"]["name"] == "postgres")
    app_dir = ROOT / "k8s/gitops/movie-app"
    app_items = [json.loads(p.read_text()) for p in sorted(app_dir.glob("*.json"))]
    expected = {("ConfigMap", "movie-app-config"), ("Service", "backend"),
                ("Service", "frontend"), ("Deployment", "backend"), ("Deployment", "frontend")}
    actual = {(x["kind"], x["metadata"]["name"]) for x in app_items}
    if actual != expected or len(app_items) != 5:
        raise RuntimeError("Unexpected GitOps resources; review before applying")
    migration = read("k8s/eks-demo/migrate.json")
    for item in [db, db_service, migration, *app_items]:
        if item["metadata"].get("namespace") != NS:
            raise RuntimeError("Unexpected namespace")
    if not args.apply:
        print("Offline checks passed. No AWS/Kubernetes requests were made.")
        print("Later, with EKS ready: python3 scripts/infra/bootstrap-app.py --apply")
        return

    print(f"Applying to context={CONTEXT}, namespace={NS}", flush=True)
    nodes = json.loads(kube("get", "nodes", "-o", "json"))["items"]
    if not any(any(c["type"] == "Ready" and c["status"] == "True"
                   for c in n.get("status", {}).get("conditions", [])) for n in nodes):
        raise RuntimeError("No Ready node")
    if get("crd", "applications.argoproj.io", namespace=None):
        applications = json.loads(kube("get", "applications.argoproj.io", "-A", "-o", "json"))["items"]
        if any(a.get("spec", {}).get("destination", {}).get("namespace") == NS for a in applications):
            raise RuntimeError("An Argo CD Application targets movie-app; use the GitOps workflow")
    exists = get("namespace", NS, namespace=None)
    db_live = get("statefulset", "postgres") if exists else None
    secret = get("secret", "movie-app-secret") if exists else None
    if db_live and not secret:
        raise RuntimeError("Database exists but Secret is missing; restore original credentials")
    if secret:
        required = {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "DATABASE_URL"}
        if not all(secret.get("data", {}).get(k) for k in required):
            raise RuntimeError("Existing Secret is missing required keys; left unchanged")
        print("Keeping existing DB Secret (values hidden).")
    if exists:
        jobs = json.loads(kube("get", "jobs", "-n", NS, "-o", "json"))["items"]
        for job in jobs:
            if job["metadata"]["name"].startswith("backend-migrate"):
                done = any(c["type"] in ("Complete", "Failed") and c["status"] == "True"
                           for c in job.get("status", {}).get("conditions", []))
                if not done:
                    raise RuntimeError("A migration Job is unfinished; inspect it before retrying")
    print(kube("apply", "-f", str(ROOT / "k8s/eks-demo/namespace.yaml")))
    if not secret:
        password = secrets.token_hex(24)
        payload = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                   "metadata": {"name": "movie-app-secret", "namespace": NS},
                   "stringData": {"POSTGRES_DB": "movie", "POSTGRES_USER": "movie",
                                  "POSTGRES_PASSWORD": password,
                                  "DATABASE_URL": f"postgresql+psycopg://movie:{password}@postgres:5432/movie"}}
        kube("create", "-f", "-", payload=payload)
        print("Created DB Secret (values hidden).")
    for item in app_items:
        if item["kind"] != "Deployment":
            apply(item)
    apply(db_service)
    if db_live:
        print("Keeping existing PostgreSQL StatefulSet unchanged.")
    else:
        print(kube("create", "-f", "-", payload=db))
    print(kube("-n", NS, "rollout", "status", "statefulset/postgres", "--timeout=300s"))
    deadline = time.monotonic() + 120
    while True:
        try:
            kube("-n", NS, "exec", "postgres-0", "-c", "postgres", "--", "sh", "-c",
                 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"')
            break
        except subprocess.CalledProcessError:
            if time.monotonic() >= deadline:
                raise RuntimeError("PostgreSQL connection readiness timed out")
            time.sleep(5)
    migration["metadata"].pop("name", None)
    migration["metadata"]["generateName"] = "backend-migrate-"
    migration["spec"]["ttlSecondsAfterFinished"] = 86400
    job_name = json.loads(kube("create", "-f", "-", "-o", "json", payload=migration))["metadata"]["name"]
    print(f"Migration Job: {job_name}", flush=True)
    deadline = time.monotonic() + 960
    while True:
        job = get("job", job_name)
        conditions = {c["type"] for c in (job or {}).get("status", {}).get("conditions", []) if c["status"] == "True"}
        if "Complete" in conditions:
            break
        if "Failed" in conditions or time.monotonic() >= deadline:
            raise RuntimeError(f"Migration failed/timed out. Inspect logs: kubectl --context {CONTEXT} -n {NS} logs job/{job_name}")
        time.sleep(5)
    print("Migration completed.", flush=True)
    for item in app_items:
        if item["kind"] == "Deployment":
            apply(item)
    for name in ("backend", "frontend"):
        print(kube("-n", NS, "rollout", "status", f"deployment/{name}", "--timeout=300s"))
    print(kube("-n", NS, "get", "pods,svc,jobs"))
    print("Bootstrap completed. Application routes still require a smoke test.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        # Do not echo subprocess input/output: a failed Secret request may contain credentials.
        raise SystemExit("Command failed. Stopped without deleting resources. Inspect cluster status; secret payloads are not printed.")
    except (RuntimeError, KeyError, StopIteration, ValueError, OSError) as exc:
        raise SystemExit(f"Bootstrap stopped: {exc}")

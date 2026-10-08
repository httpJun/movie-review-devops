#!/usr/bin/env python3
"""Create a small team environment in the local Rancher lab."""
import argparse
import json
import re
import subprocess
import sys

CONTEXT = "k3d-rancher-lab"
LABEL = "app.kubernetes.io/managed-by"
OWNER = "team-env-lab"

def kubectl(*args, **kwargs):
    return subprocess.run(
        ["kubectl", "--context", CONTEXT, "--request-timeout=30s", *args],
        check=True, text=True, timeout=60, **kwargs
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("team")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9-]{0,24}[a-z0-9]|[a-z]", args.team):
        parser.error("team: 소문자로 시작하는 영문·숫자·하이픈, 최대 26자")

    namespace = f"team-{args.team}"

    def resource(kind, name, api="v1", **fields):
        return {
            "apiVersion": api,
            "kind": kind,
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {LABEL: OWNER},
            },
            **fields,
        }

    ns = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace,
            "labels": {LABEL: OWNER, "team": args.team},
        },
    }

    resources = [
        resource("ResourceQuota", "team-budget", spec={"hard": {
            "requests.cpu": "500m",
            "requests.memory": "512Mi",
            "limits.cpu": "1",
            "limits.memory": "1Gi",
            "pods": "4",
            "count/configmaps": "5",
        }}),
        resource("LimitRange", "container-defaults", spec={"limits": [{
            "type": "Container",
            "defaultRequest": {"cpu": "100m", "memory": "64Mi"},
            "default": {"cpu": "250m", "memory": "128Mi"},
        }]}),
        resource("ServiceAccount", "team-bot",
                 automountServiceAccountToken=False),
        resource("Role", "team-config-editor",
                 api="rbac.authorization.k8s.io/v1", rules=[
                     {
                         "apiGroups": [""],
                         "resources": ["configmaps"],
                         "verbs": ["get", "list", "watch", "create",
                                   "update", "patch", "delete"],
                     },
                     {
                         "apiGroups": [""],
                         "resources": ["pods"],
                         "verbs": ["get", "list", "watch"],
                     },
                 ]),
        resource("RoleBinding", "team-config-editor",
                 api="rbac.authorization.k8s.io/v1",
                 subjects=[{
                     "kind": "ServiceAccount",
                     "name": "team-bot",
                     "namespace": namespace,
                 }],
                 roleRef={
                     "apiGroup": "rbac.authorization.k8s.io",
                     "kind": "Role",
                     "name": "team-config-editor",
                 }),
    ]

    if not args.apply:
        print(json.dumps(
            {"apiVersion": "v1", "kind": "List", "items": [ns, *resources]},
            indent=2,
        ))
        return

    # Refuse to modify a namespace not managed by this script.
    result = kubectl(
        "get", "namespace", namespace,
        "--ignore-not-found", "-o", "json",
        capture_output=True,
    )
    if result.stdout.strip():
        existing = json.loads(result.stdout)
        labels = existing["metadata"].get("labels") or {}
        if labels.get(LABEL) != OWNER:
            raise ValueError(f"{namespace}: 다른 용도의 네임스페이스라 중단")
        if existing["metadata"].get("deletionTimestamp"):
            raise ValueError(f"{namespace}: 삭제 중이라 중단")

    # Sequential apply: failures can leave a partial environment.
    # Correct the cause and rerun the same command.
    for item in [ns, *resources]:
        kubectl("apply", "-f", "-", input=json.dumps(item))

    print(f"완료: context={CONTEXT}, namespace={namespace}")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(exc.returncode)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"실패: {exc}", file=sys.stderr)
        sys.exit(1)

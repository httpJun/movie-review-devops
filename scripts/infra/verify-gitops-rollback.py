#!/usr/bin/env python3
"""로컬 전용: readiness 설정 오류 주입과 Git revert 복구 검증."""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

CONTEXT = "k3d-rancher-lab"
BRANCH = "feat/deployment-rollback"
MANIFEST = "k8s/rollback-lab/app/deployment.yaml"
GOOD_PATH = "/"
BAD_PATH = "/rollback-lab-intentional-failure"

def run(args):
    return subprocess.run(
        args, check=True, capture_output=True, text=True, timeout=90
    ).stdout.strip()

def git(*args):
    return run(["git", *args])

def kube(*args):
    return run(["kubectl", "--context", CONTEXT, *args])

def deployment():
    return json.loads(kube(
        "-n", "rollback-lab", "get", "deployment", "rollback-web", "-o", "json"
    ))

def application():
    return json.loads(kube(
        "-n", "argocd", "get", "application", "rollback-lab", "-o", "json"
    ))

def refresh():
    kube(
        "-n", "argocd", "annotate", "application", "rollback-lab",
        "argocd.argoproj.io/refresh=hard", "--overwrite"
    )

def wait_for(label, predicate, timeout):
    print(label, flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(3)
    raise RuntimeError(f"제한 시간 초과: {label}")

def healthy_at(revision):
    app = application().get("status", {})
    dep = deployment()
    status = dep.get("status", {})
    container = dep["spec"]["template"]["spec"]["containers"][0]
    return (
        app.get("sync", {}).get("revision") == revision
        and app.get("sync", {}).get("status") == "Synced"
        and app.get("health", {}).get("status") == "Healthy"
        and container["readinessProbe"]["httpGet"]["path"] == GOOD_PATH
        and status.get("observedGeneration", 0) >= dep["metadata"]["generation"]
        and status.get("replicas", 0) == 1
        and status.get("updatedReplicas", 0) == 1
        and status.get("readyReplicas", 0) == 1
        and status.get("availableReplicas", 0) == 1
    )

def failed_deployment():
    dep = deployment()
    status = dep.get("status", {})
    container = dep["spec"]["template"]["spec"]["containers"][0]
    return (
        container["readinessProbe"]["httpGet"]["path"] == BAD_PATH
        and status.get("observedGeneration", 0) >= dep["metadata"]["generation"]
        and any(
            c["type"] == "Progressing"
            and c["status"] == "False"
            and c.get("reason") == "ProgressDeadlineExceeded"
            for c in status.get("conditions", [])
        )
    )

def ensure_remote(expected):
    git("fetch", "origin", BRANCH)
    if git("rev-parse", "HEAD") != expected:
        raise RuntimeError("로컬 HEAD가 변경됐습니다. 자동 Git 변경을 중단합니다.")
    if git("rev-parse", f"origin/{BRANCH}") != expected:
        raise RuntimeError("원격 브랜치가 변경됐습니다. 강제 push하지 않습니다.")

if git("branch", "--show-current") != BRANCH:
    raise SystemExit(f"{BRANCH} 브랜치에서 실행하세요.")
if git("status", "--porcelain"):
    raise SystemExit("커밋하지 않은 변경이 있습니다. 먼저 확인하세요.")

baseline = git("rev-parse", "HEAD")
ensure_remote(baseline)

app_spec = application()["spec"]
if (
    app_spec["source"]["repoURL"]
    != "https://github.com/httpJun/movie-review-devops.git"
    or app_spec["source"]["targetRevision"] != BRANCH
    or app_spec["source"]["path"] != "k8s/rollback-lab/app"
    or app_spec["destination"]["namespace"] != "rollback-lab"
    or app_spec["destination"]["server"]
    != "https://kubernetes.default.svc"
):
    raise SystemExit("Argo CD 연결 설정이 실습 대상과 다릅니다.")

probe = json.loads(kube(
    "-n", "rollback-lab", "get", "pod", "rollback-probe", "-o", "json"
))
if not any(
    c["type"] == "Ready" and c["status"] == "True"
    for c in probe.get("status", {}).get("conditions", [])
):
    raise SystemExit("HTTP 관측 Pod가 준비되지 않았습니다.")

path = Path(MANIFEST)
original = path.read_text()
needle = "              path: /\n"
if original.count(needle) != 1:
    raise SystemExit("정상 readiness 경로를 한 곳에서 찾지 못했습니다.")

refresh()
wait_for("정상 기준 버전 동기화 확인 중", lambda: healthy_at(baseline), 240)

http_check = kube(
    "-n", "rollback-lab", "exec", "deployment/rollback-web", "--",
    "wget", "-q", "-T", "3", "-O", "-", "http://rollback-web/"
)
if "Welcome to nginx!" not in http_check:
    raise SystemExit("정상 기준 HTTP 응답 확인 실패")

started_utc = datetime.now(timezone.utc).isoformat()
output = Path.home() / "movie-review-rollback-lab" / (
    "run-" + datetime.now().strftime("%Y%m%d-%H%M%S")
)
output.mkdir(parents=True, exist_ok=False)
result = {
    "context": CONTEXT,
    "baseline_commit": baseline,
    "started_utc": started_utc,
    "failure_detected": False,
    "recovery_verified": False,
}
bad_commit = None
started = time.monotonic()
detected = None

try:
    ensure_remote(baseline)
    path.write_text(original.replace(
        needle, f"              path: {BAD_PATH}\n"
    ))
    git("add", "--", MANIFEST)
    git("commit", "-m", "test: inject readiness failure in rollback lab")
    bad_commit = git("rev-parse", "HEAD")
    result["bad_commit"] = bad_commit
    git("push", "origin", f"HEAD:{BRANCH}")
    refresh()

    wait_for("배포 실패 판정 대기 중", failed_deployment, 240)
    detected = time.monotonic()
    result["failure_detected"] = True
    result["failure_detection_seconds"] = round(detected - started, 3)
    (output / "failed-deployment.json").write_text(
        json.dumps(deployment(), indent=2) + "\n"
    )
    print("배포 실패 확인. 정상 설정을 Git으로 복원합니다.", flush=True)

except Exception as error:
    result["experiment_error"] = str(error)
    print(f"실험 오류: {error}", flush=True)

finally:
    if bad_commit is not None:
        try:
            ensure_remote(bad_commit)
            git("revert", "--no-edit", bad_commit)
            restored_commit = git("rev-parse", "HEAD")
            result["restore_commit"] = restored_commit
            git("push", "origin", f"HEAD:{BRANCH}")
            refresh()
            wait_for(
                "정상 버전 복원 확인 중",
                lambda: healthy_at(restored_commit),
                240,
            )
            response = kube(
                "-n", "rollback-lab", "exec", "deployment/rollback-web", "--",
                "wget", "-q", "-T", "3", "-O", "-", "http://rollback-web/"
            )
            if "Welcome to nginx!" not in response:
                raise RuntimeError("복원 후 HTTP 응답 검증 실패")
            finished = time.monotonic()
            result["recovery_verified"] = True
            result["total_seconds"] = round(finished - started, 3)
            if detected is not None:
                result["detection_to_recovery_seconds"] = round(
                    finished - detected, 3
                )
        except Exception as error:
            result["recovery_error"] = str(error)

    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        logs = kube(
            "-n", "rollback-lab", "logs", "rollback-probe",
            f"--since-time={started_utc}", "--timestamps"
        )
        (output / "http-probe.log").write_text(logs + "\n")
    except Exception as error:
        result["log_error"] = str(error)

    result["passed"] = (
        result["failure_detected"] and result["recovery_verified"]
    )
    (output / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"기록 경로: {output}")

if not result["passed"]:
    raise SystemExit("검증 미완료. 결과를 보내주세요. 재실행하지 마세요.")

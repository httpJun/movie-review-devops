# 로컬 백업·롤백 재현 안내

명령은 저장소 루트에서 단계별로 실행한다. 대상은 기존 `k3d-rancher-lab`이며 AWS를 생성하지 않는다. Docker·k3d·kubectl·Git·Python 3.12가 필요하다. 클러스터가 없으면 먼저 별도로 구축해야 한다.

이 문서는 기존 실험을 재현하기 위해 준비 과정을 보완한 것이다. 추가한 PostgreSQL 매니페스트와 입력 SQL을 포함한 전체 절차를 새 클러스터에서 다시 실행한 결과는 아직 없다. 기존 측정값을 재실행 결과로 사용하지 않는다.

## 공통 확인

```bash
git status --short
kubectl --context k3d-rancher-lab get nodes
kubectl --context k3d-rancher-lab get pods -A
kubectl --context k3d-rancher-lab get storageclass local-path
```

노드가 Ready가 아니거나 시스템 Pod에 장애가 있으면 먼저 해결한다. 기존 작업이 있는 Git 작업 트리에서는 브랜치를 바꾸지 않는다.

## PostgreSQL 준비

이미 `backup-lab/postgres-0`와 `movie_app_lab` 데이터가 있으면 아래 신규 구축을 건너뛰고 **백업 검증**으로 이동한다. 기존 PVC를 사용하는 DB의 비밀번호를 Secret 수정만으로 바꾸지 않는다.

처음 구축할 때만 Namespace와 Secret을 만든다. 비밀번호는 터미널에 출력하거나 Git에 저장하지 않는다.

```bash
kubectl --context k3d-rancher-lab create namespace backup-lab
LAB_DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_hex(24))')
kubectl --context k3d-rancher-lab -n backup-lab create secret generic postgres-secret \
  --from-literal=POSTGRES_USER=lab \
  --from-literal=POSTGRES_DB=movie_lab \
  --from-literal=POSTGRES_PASSWORD="$LAB_DB_PASSWORD"
unset LAB_DB_PASSWORD
kubectl --context k3d-rancher-lab apply -f k8s/postgres-backup-lab/postgres.yaml
kubectl --context k3d-rancher-lab -n backup-lab rollout status statefulset/postgres --timeout=180s
kubectl --context k3d-rancher-lab -n backup-lab exec postgres-0 -- createdb -U lab -T template0 movie_app_lab
```

리소스가 이미 존재한다는 오류가 나면 계속 덮어쓰지 말고 기존 설정을 확인한다. 이미지 `postgres:16`은 이동 태그이므로 과거 측정 버전 16.15와 다를 수 있다. 재실행 시 서버 버전을 함께 기록한다.

다른 터미널에서 연결을 유지한다.

```bash
kubectl --context k3d-rancher-lab -n backup-lab port-forward pod/postgres-0 15432:5432 --address 127.0.0.1
```

원래 터미널의 저장소 루트에서 마이그레이션 도구를 설치하고 빈 DB에 스키마를 적용한다. 전체 분석용 의존성은 설치하지 않는다.

```bash
python3.12 -m venv "$HOME/movie-review-backup-lab/migration-venv"
source "$HOME/movie-review-backup-lab/migration-venv/bin/activate"
python -m pip install 'alembic>=1.18.4,<2' 'SQLAlchemy>=2.0.49,<2.1' 'psycopg[binary]>=3.3.4,<4' 'pydantic-settings>=2.14.1,<3'
LAB_DB_PASSWORD=$(kubectl --context k3d-rancher-lab -n backup-lab get secret postgres-secret \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | python3 -c 'import base64,sys; print(base64.b64decode(sys.stdin.read()).decode())')
export DATABASE_URL="postgresql+psycopg://lab:${LAB_DB_PASSWORD}@127.0.0.1:15432/movie_app_lab"
export SCHEDULER_ENABLED=false
alembic upgrade head
alembic current
unset LAB_DB_PASSWORD DATABASE_URL SCHEDULER_ENABLED
```


마이그레이션 성공을 확인한 뒤 입력한다. SQL은 기존 영화·리뷰가 있으면 중단한다. 재입력을 위해 기존 데이터를 삭제하지 않는다.

```bash
kubectl --context k3d-rancher-lab -n backup-lab exec -i postgres-0 -- \
  psql -X -v ON_ERROR_STOP=1 -U lab -d movie_app_lab < scripts/infra/seed-backup-lab.sql
```

영화 100건·리뷰 10,000건을 확인한다. 이 입력은 합성 데이터이며 다른 DB 엔진에서 이관한 데이터가 아니다. 마이그레이션용 port-forward는 이제 중지해도 된다.

## 백업 검증

실험 중 원본 DB를 수정하는 앱·작업을 멈춘다. 다음 명령은 원본을 삭제하지 않고 매번 새 복원 DB를 만든다.

```bash
kubectl --context k3d-rancher-lab -n backup-lab exec postgres-0 -- \
  psql -X -U lab -d movie_app_lab -c 'SELECT version(); SELECT count(*) FROM movies; SELECT count(*) FROM reviews;'
python3 scripts/infra/verify-postgres-restore.py
```

출력된 기록 경로의 `result.json`, `before.txt`, `after.txt`를 확인한다. `passed: true`와 함께 예상 행 수, 테이블 목록 일치, 고아 리뷰 0건을 확인한다. 백업·복원 DB는 자동 삭제되지 않는다. 기록은 `$HOME/movie-review-backup-lab/auto-*`에 저장되며 덤프·비밀번호는 커밋하지 않는다.

기존 결과와 수치가 다른 것은 정상이다. [측정 범위](postgres-backup-restore.md)를 함께 읽는다.

## GitOps 롤백 준비

Argo CD와 `applications.argoproj.io`가 설치된 클러스터가 전제다. 설치 자체는 이 절차에 포함하지 않는다. 설치 매니페스트와 실제 이미지 버전을 별도로 기록해야 재현 환경을 비교할 수 있다.

```bash
kubectl --context k3d-rancher-lab get crd applications.argoproj.io
kubectl --context k3d-rancher-lab -n argocd get pods
```

현재 스크립트와 Application은 원본 저장소의 `feat/deployment-rollback` 브랜치를 고정 사용한다. 이 실험은 해당 브랜치에 **오류 커밋과 복원 커밋을 실제 push**한다. 포크에서는 스크립트의 저장소 검사와 Application의 repoURL을 함께 수정해야 한다.

정리 작업을 커밋·병합한 다음, 미커밋 변경이 없는 작업 트리에서 실행한다.

```bash
git fetch origin
git switch feat/deployment-rollback
git merge --ff-only origin/feat/deployment-rollback
git status --short
git rev-parse HEAD
git rev-parse origin/feat/deployment-rollback
```

브랜치가 삭제됐으면 `main`에서 새 실습 브랜치를 만들어 push한 뒤 진행한다. 다른 worktree가 사용 중이면 그 작업 트리로 이동한다. 이력이 갈라졌거나 위 두 커밋이 다르면 중단하고 원인을 확인한다. 강제 push나 reset으로 맞추지 않는다.

`rollback-lab` Namespace가 없는 경우에만 생성하고 Application을 적용한다. 기존 Application이 `main`을 추적 중이라도 다음 apply는 실습 브랜치로 바꾼다.

```bash
kubectl --context k3d-rancher-lab create namespace rollback-lab
kubectl --context k3d-rancher-lab apply -f k8s/rollback-lab/application.yaml
kubectl --context k3d-rancher-lab -n argocd get application rollback-lab -w
```

`Synced / Healthy`를 확인하고 감시를 종료한다. 기존 관측 Pod가 없다면 생성한다. 종료된 관측 Pod가 남아 있다면 기존 로그를 보관하고 해당 Pod만 삭제한 뒤 다시 생성한다.

```bash
kubectl --context k3d-rancher-lab apply -f k8s/rollback-lab/probe.yaml
kubectl --context k3d-rancher-lab -n rollback-lab wait --for=condition=Ready pod/rollback-probe --timeout=120s
python3 scripts/infra/verify-gitops-rollback.py
```

## 롤백 결과와 종료

출력된 기록 경로의 `result.json`과 `http-probe.log`를 확인한다. `passed: true`만으로 HTTP 실패 0회를 의미하지는 않는다. 다음 집계는 실행 경로를 입력받으며 기록 0건도 구분한다.

```bash
python3 - <<'PY'
from collections import Counter
from pathlib import Path
folder = Path(input('출력된 기록 경로: ').strip()).expanduser()
counts = Counter(line.split()[-1] for line in (folder / 'http-probe.log').read_text().splitlines() if line.strip())
for status in ('SUCCESS', 'REQUEST_FAILED', 'CONTENT_MISMATCH'):
    print(status, counts[status])
print('전체 관측 수:', sum(counts.values()))
PY
kubectl --context k3d-rancher-lab -n argocd get application rollback-lab
kubectl --context k3d-rancher-lab -n rollback-lab get pods
```

오류가 발생하면 재실행 전에 Git의 로컬·원격 커밋과 Application의 추적 브랜치·동기화 상태를 확인한다. `finally`가 있어도 push 실패나 프로세스 강제 종료까지 자동 복원되는 것은 아니다.

증거 보관 후 관측 Pod만 제거할 수 있다.

```bash
kubectl --context k3d-rancher-lab -n rollback-lab delete pod rollback-probe
```

정상 설정이 `main`에 병합된 것을 확인한 후 상시 추적을 `main`으로 되돌리려면 다음을 실행한다. 이 설정은 다음 실험의 Application apply로 다시 실습 브랜치가 된다.

```bash
kubectl --context k3d-rancher-lab -n argocd patch application rollback-lab --type merge \
  -p '{"spec":{"source":{"targetRevision":"main"}}}'
```

DB·PVC·Namespace 전체 삭제는 이 문서에서 자동화하지 않는다. `backup-lab`에는 다른 실습 리소스도 있으므로 필요한 백업과 복원 DB를 확인한 뒤 개별 정리한다.

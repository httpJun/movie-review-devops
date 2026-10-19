# 프로젝트 설명·코드 수정 연습

이 문서는 학습용이다. 아래 질문에 답하거나 수정 연습을 했다는 사실을 기존 검증 성과로 간주하지 않는다. AWS 리소스를 다시 만들 필요는 없다.

## 설명 순서

1. 팀이 만든 영화 리뷰 앱과 개인이 수행한 인프라·운영 작업을 구분한다.
2. GitHub Actions → ECR → Git의 이미지 digest 갱신 → Argo CD → Deployment 흐름을 설명한다.
3. 외부 요청이 ALB·프론트엔드·백엔드·DB로 전달되는 경로를 설명한다.
4. EKS 기록과 로컬 k3d 기록을 구분하고, 각각 확인한 결과를 말한다.
5. 문제 하나를 증상 → 확인한 근거 → 조치 → 결과 → 한계 순서로 설명한다.

## 코드 읽기

| 파일 | 먼저 찾을 부분 | 직접 설명할 질문 |
|---|---|---|
| [CI](../.github/workflows/ci.yml) | OIDC 인증, digest 갱신, Git push | 이미지 업로드 성공과 앱 배포 성공은 왜 다른가? |
| [GitOps Application](../k8s/argocd/movie-app.yaml) | source.path, targetRevision, selfHeal | 이 Application이 관리하지 않는 DB·Secret은 누가 준비하는가? |
| [백업 검증](../scripts/infra/verify-postgres-restore.py) | snapshot_sql, pg_dump, pg_restore, passed | 파일 생성만으로 복원 가능성을 판단할 수 없는 이유는? |
| [롤백 검증](../scripts/infra/verify-gitops-rollback.py) | ensure_remote, failed_deployment, healthy_at, finally | 실패 판정과 Git 복원은 Argo CD와 Python 중 누가 수행하는가? |

## 백업 스크립트를 이해하는 질문

- PVC는 현재 DB 데이터를 저장한다. SQL로 삭제한 데이터를 PVC 자체가 되돌려 주는가?
- `pg_dump -Fc` 출력은 왜 Pod가 아닌 Mac에 저장하는가?
- 백업과 비교 기준 조회 사이에 원본 데이터가 바뀌면 어떤 일이 생기는가?
- 행 수가 같아도 내용은 다를 수 있다. 체크섬을 계산할 때 기본키로 정렬하는 이유는?
- `movie_restore_시각`이라는 새 DB를 만드는 이유는?
- 테이블 이름 목록 일치는 모든 인덱스·제약·권한 정의의 완전한 비교인가?
- `restore_seconds`는 DB 생성·검증·앱 정상화 시간까지 포함하는가?
- 데이터가 비어 있는 두 DB가 서로 같으면 현재 `passed` 조건이 통과할 수 있는가?

답의 핵심: 원본 쓰기를 멈춘 테스트에서 두 업무 테이블의 내용과 버전을 비교했다. 전체 데이터 종류·서비스 복구·운영 RPO/RTO를 입증한 것은 아니다. 스크립트는 예상 데이터 수 100/10,000 자체를 성공 조건으로 강제하지 않는다.

## 롤백 스크립트를 이해하는 질문

- readiness 실패는 컨테이너 종료와 어떻게 다른가?
- `maxUnavailable: 0`, `maxSurge: 1`일 때 오류 Pod와 정상 Pod는 어떻게 공존하는가?
- `ProgressDeadlineExceeded`는 실패 판정인가, Kubernetes의 자동 롤백 명령인가?
- Git에 오류 설정이 남은 상태에서 `kubectl rollout undo`만 하면 selfHeal과 어떤 충돌이 생길 수 있는가?
- `git revert`와 이력을 덮어쓰는 방식은 어떻게 다른가?
- 이전 Healthy 상태를 새 배포의 성공으로 오인하지 않기 위해 revision과 generation을 확인하는 이유는?
- `ensure_remote`가 막는 위험은 무엇이며, 확인 직후 다른 push가 발생하는 경쟁 상황까지 제거하는가?
- 기존 Pod가 살아 있었는데 11.169초를 서비스 중단 시간이라고 말해도 되는가?

답의 핵심: 이번에는 새 배포의 실패를 감지하고 정상 설정을 Git에 복원했다. 서비스 전체를 되살린 실험이 아니다. HTTP 관측 80회 성공은 모든 순간·모든 요청의 무중단 증명이 아니다.

## 이미 확인된 코드의 한계

- 백업 스크립트는 클러스터·DB·데이터를 만들지 않는다. subprocess 실행 제한 시간과 모든 예외에 대한 구조화된 실패 결과 저장도 없다.
- 롤백 스크립트는 로컬에서 수동 실행하며 브랜치·저장소·리소스 이름이 고정돼 있다.
- 오류 커밋의 push가 실패하면 원격 HEAD와 로컬 오류 커밋이 달라져 복원 경로의 `ensure_remote`도 중단될 수 있다. `finally`가 있다고 모든 실패에서 복원되는 것은 아니다.
- 복원 커밋 생성 후 push가 실패하면 로컬과 원격이 달라질 수 있다. 강제 push·반복 재실행 대신 Git 상태와 Application 상태를 확인해야 한다.
- `passed`는 배포 실패 감지와 정상 복원을 검사한다. HTTP 관측 실패 0회 여부는 별도 집계다.
- readiness 경로 변경은 YAML 구조 편집이 아닌 문자열 치환이다. 들여쓰기 변경에도 영향을 받는다.

## 서버 없이 할 수정 연습

연습 브랜치에서 수행하고, 검증 스크립트 자체를 import하거나 실행하지 않는다. 두 파일은 최상위에서 실제 작업을 실행한다.

1. `restore_seconds`를 읽어 밀리초와 초를 출력하는 작은 프로그램을 작성한다.
2. `http-probe.log` 예시 문자열에 SUCCESS·REQUEST_FAILED·CONTENT_MISMATCH를 섞고 집계한다. 실패 0건과 기록 0건을 구분한다.
3. 백업 결과의 `snapshot_match`, `table_list_match`, `orphan_reviews` 중 하나씩 바꾼 JSON 예제로 성공 판정을 설명한다.
4. 롤백의 원격 변경·타임아웃·push 실패 시나리오를 종이에 추적하고, 어디에서 수동 확인이 필요한지 표시한다.

각 연습은 입력·예상 결과·실제 결과를 먼저 적는다. 이후 새 프로젝트를 시작할 기준은 코드를 외우는 것이 아니라, 위 흐름과 한계를 자신의 말로 설명하고 작은 변경을 직접 검증하는 것이다.

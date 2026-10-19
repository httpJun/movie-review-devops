# GitOps 배포 실패 탐지·자동 롤백 검증

## 목적과 범위

로컬 k3d에서 배포 설정 오류를 자동으로 감지하고,
Git 복원 커밋을 Argo CD가 반영하여 정상 상태로 돌아오는지 검증했다.

대상은 별도 Nginx 실습 앱이다.
영화 리뷰 앱 전체나 EKS 운영 환경의 복구를 검증한 것은 아니다.

## 구성

- 검증일: 2026-10-20
- 클러스터: k3d rancher-lab
- Namespace: rollback-lab
- 배포 대상: nginx:1.28.0-alpine
- 정상 Pod 수: 1개
- RollingUpdate: maxSurge 1, maxUnavailable 0
- 배포 진행 제한 시간: 60초
- Argo CD: 자동 동기화, selfHeal 활성화
- Git 추적 브랜치: feat/deployment-rollback
- Git 추적 경로: k8s/rollback-lab/app
- 실행 위치: 사용자 Mac의 Python 스크립트

## 검증 과정

1. Git 상태, 정상 Deployment, Argo CD 동기화 및 HTTP 응답을 확인했다.
2. readinessProbe 경로를 존재하지 않는 경로로 변경하고 Git에 push했다.
3. Argo CD가 오류 설정을 반영했다.
4. 새 Pod가 준비되지 않아 Deployment의 Progressing 조건에
   ProgressDeadlineExceeded가 기록되는 것을 감지했다.
5. 스크립트가 오류 커밋을 git revert로 되돌리고 push했다.
6. Argo CD 동기화, 정상 Deployment 및 HTTP 응답을 확인했다.

Argo CD 자체가 실패 버전을 판단해 자동 롤백한 것은 아니다.
Python 스크립트가 실패 판정과 Git 복원 커밋을 수행했고,
Argo CD가 복원된 Git 설정을 클러스터에 반영했다.

## 결과

| 항목 | 결과 |
|---|---|
| 배포 실패 자동 감지 | 성공 |
| Git 복원 커밋 생성·push | 성공 |
| 정상 배포·HTTP 응답 확인 | 성공 |
| 실험 시작부터 실패 감지 | 69.576초 |
| 실패 감지부터 정상 복원 확인 | 11.169초 |
| 전체 소요 시간 | 80.744초 |
| HTTP 관측 | 80회 성공, 요청 실패 0회, 내용 불일치 0회 |
| 최종 Argo CD 상태 | Synced / Healthy |
| 최종 Pod 상태 | 기존 정상 Pod 1/1 Running |

maxUnavailable 0 설정으로 기존 정상 Pod가 유지됐다.
이번 결과는 실패한 신규 배포를 되돌린 사례이며,
서비스 전체 중단 후 재기동한 사례가 아니다.

## 시간과 관측의 해석

- 실패 감지 시간에는 Git 커밋·push, 동기화, 배포 제한 시간 및 조회 지연이 포함된다.
- 복원 시간에는 Git revert·push, 동기화와 정상 상태·HTTP 확인이 포함된다.
- 11.169초는 서비스 중단 시간이 아니다.
- HTTP 관측은 약 1초 간격으로 수행했으며 전 구간의 모든 요청을 대표하지 않는다.
- 관측한 80회에서 실패가 없었으며, 절대적인 무중단 보장을 의미하지 않는다.

## 실행 방법과 전제

저장소 루트에서 다음 명령을 실행한다.

    python3 scripts/infra/verify-gitops-rollback.py

필요 조건:
- 로컬 클러스터와 Argo CD가 실행 중이어야 한다.
- 정상 실습 앱과 rollback-probe가 준비되어 있어야 한다.
- feat/deployment-rollback 브랜치를 사용해야 한다.
- 미커밋 변경이 없어야 하고 로컬 HEAD와 원격 브랜치가 일치해야 한다.
- 해당 브랜치에 Git push 권한이 있어야 한다.

스크립트는 오류 주입 커밋과 복원 커밋을 원격 브랜치에 push한다.
실행 중 다른 작업으로 브랜치를 변경하지 않는다.

## 한계

- readiness 설정 오류 한 종류를 검증했다.
- 앱 코드 오류, DB 스키마 변경, 외부 의존성 장애는 검증하지 않았다.
- 로컬 실행 스크립트이며 CI 작업으로 연결하지 않았다.
- 실행 프로세스 강제 종료나 Git push 실패 등 모든 중간 실패에서
  자동 복구를 보장하는 구성은 아니다.
- 원격 브랜치가 예상과 다르면 강제 push하지 않고 중단한다.

## 근거

- [측정 결과](evidence/gitops-rollback/result.json)
- [HTTP 집계](evidence/gitops-rollback/http-summary.json)
- [HTTP 원본 로그](evidence/gitops-rollback/http-probe.log)
- [실패 시 Deployment](evidence/gitops-rollback/failed-deployment.json)
- [최종 Argo CD 상태](evidence/gitops-rollback/application-after.txt)
- [최종 Pod 상태](evidence/gitops-rollback/pods-after.txt)
- [자동 검증 스크립트](../scripts/infra/verify-gitops-rollback.py)

# 단기 EKS 실습용 배포 스크립트

## 검증 상태 — 2026-10-05

- preflight.sh: 로컬 사전 점검 통과
- bootstrap-app.py: Python 문법 및 로컬 입력 검사 통과
- install-monitoring.sh: Bash 문법, Helm lint 및 로컬 렌더링 통과
- 스크립트의 --apply 실행은 아직 EKS에서 검증하지 않았다.
- 기반 배포 설정은 이전 실습에서 수동으로 검증했다.

## 파일

| 파일 | 역할 |
|---|---|
| preflight.sh | 도구·파일·이미지 digest 일치 여부 확인 |
| bootstrap-app.py | DB 준비 → 마이그레이션 → 앱 배포 |
| install-monitoring.sh | 모니터링 설치 → CPU 경고 규칙 적용 |

## 클러스터 없이 검사

저장소 루트에서 실행한다.

```bash
bash scripts/infra/preflight.sh
python3 scripts/infra/bootstrap-app.py
bash scripts/infra/install-monitoring.sh --check
```

위 명령은 AWS와 Kubernetes API에 접속하지 않는다.
모니터링 검사는 Helm 차트 다운로드를 위해 인터넷에 접속한다.
AWS 인증, ECR 이미지 존재 여부, 클러스터 접근 권한은 검증하지 않는다.

## 실제 배포

EKS와 Ready 노드, ECR 이미지 및 movie-review-eks 컨텍스트가
준비되어 있어야 한다. 인프라 생성은 이 스크립트에 포함하지 않는다.

```bash
python3 scripts/infra/bootstrap-app.py --apply
bash scripts/infra/install-monitoring.sh --apply
```

앱 배포가 성공한 다음 모니터링 설치를 실행한다.

### 앱 배포 동작

- 기존 DB Secret은 유지하고, 없을 때만 생성한다.
- 기존 PostgreSQL StatefulSet은 수정하지 않는다.
- DB가 있는데 Secret이 없으면 중단한다.
- DB 연결 준비 후 새 마이그레이션 Job을 생성한다.
- 마이그레이션 성공 후 backend와 frontend를 배포한다.
- 완료된 새 마이그레이션 Job은 24시간 후 자동 정리된다.
- 미완료 마이그레이션 Job이 있으면 재실행을 중단한다.
- movie-app을 대상으로 하는 Argo CD Application이 있으면 중단한다.
- 동시에 여러 번 실행하지 않는다.

### 제한 및 후속 확인

- PostgreSQL은 emptyDir이므로 DB Pod 삭제 시 데이터가 사라진다.
- 기존 StatefulSet을 유지하는 동작은 데이터 백업을 의미하지 않는다.
- 운영 중인 DB의 무중단 마이그레이션을 보장하지 않는다.
- 실패 시 생성한 리소스를 자동 삭제하거나 롤백하지 않는다.
- 앱 배포 후 실제 API와 화면 접속을 별도로 확인한다.
- 모니터링 설치 후 수집 대상과 경고 규칙 로드를 별도로 확인한다.
- Alertmanager 외부 알림, Argo CD 및 ALB 설치는 포함하지 않는다.

## 종료

포트포워딩이나 터미널 종료만으로 AWS 리소스가 삭제되지는 않는다.
실습 종료 시 Terraform 삭제 계획을 검토하고 적용한다.
삭제 후 EKS·EC2·EBS·로드밸런서·NAT Gateway·Elastic IP를 조회한다.
보존한 ECR 이미지에는 저장 비용이 남을 수 있다.

## 삭제 후 잔존 리소스 확인

```bash
bash scripts/infra/check-cleanup.sh
```

- AWS 계정과 실행 주체를 표시한 뒤 서울 리전을 조회한다.
- EKS, 종료되지 않은 EC2, EBS, ALB/NLB/GWLB,
  삭제되지 않은 NAT Gateway, Elastic IP 개수를 확인한다.
- 조회만 수행하며 리소스를 생성하거나 삭제하지 않는다.
- 종료 코드 0: 조회한 6개 항목 모두 없음
- 종료 코드 1: 잔존 리소스가 있어 검토 필요
- 종료 코드 2: 조회 실패 또는 예상하지 못한 응답
- 계정 확인 실패 시에도 비정상 종료한다.
- ECR 저장 비용, 다른 서비스·리전, 이미 발생한 비용은 확인하지 않는다.

### 실제 조회 검증 — 2026-10-05

- Bash 문법 검사 통과
- AWS 계정 확인 성공
- 서울 리전의 조회 대상 6개 항목 모두 0개 확인
- 최종 PASS 출력 확인

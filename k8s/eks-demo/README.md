# EKS 단기 실습 환경

## 검증 완료 — 2026-10-01

- Terraform으로 EKS 1.35 및 t3.large 관리형 노드 1대 구성
- GitHub Actions에서 빌드한 ECR 이미지를 digest로 고정하여 배포
- PostgreSQL 실행 및 Alembic Job으로 테이블 9개 생성
- FastAPI·Next.js readiness 확인
- 로컬 Docker 앱 중지 후 포트포워딩으로 API와 화면 접속 확인
- 백엔드 Pod 삭제 후 새 Pod 자동 생성 확인
- 새 Pod 생성 후 약 30초에 Ready 도달, 포트포워딩 재연결 후 API 응답 확인

## 실습 범위와 제한

- 단일 노드·단일 앱 replica 구성이다.
- PostgreSQL은 emptyDir를 사용한다. DB Pod 삭제 시 데이터가 사라진다.
- Service는 ClusterIP이며 외부 공개 대신 포트포워딩으로 접속한다.
- Secret 값은 Git에 저장하지 않는다.
- 데이터 수집·LLM 분석, 장기 모니터링, 자동 배포는 아직 검증하지 않았다.
- Pod 삭제 후 자동 재생성을 검증했으며 노드 장애 복구나 무중단을 보장하지 않는다.

## 파일

- namespace.yaml: 네임스페이스
- resources.json: 검증한 앱·DB·Service·ConfigMap 구성
- migrate.json: DB 마이그레이션 Job

## 새 클러스터에 재배포하는 순서

저장소 루트에서 실행한다.
EKS와 노드, ECR 이미지가 준비되어 있어야 한다.

1. kubeconfig 연결
2. namespace.yaml 적용
3. movie-app-secret 생성
4. ConfigMap·Service·PostgreSQL 적용
5. PostgreSQL 연결 준비 확인
6. migrate.json 적용 및 Job Complete 확인
7. backend·frontend Deployment 적용
8. rollout 및 포트포워딩 접속 확인

resources.json 전체를 처음부터 적용하면 마이그레이션보다 앱이 먼저
시작될 수 있으므로 위 순서대로 리소스를 나누어 적용한다.

Secret에 필요한 키:
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL

DATABASE_URL 형식:
postgresql+psycopg://<user>:<password>@postgres:5432/<database>

DB Pod가 재생성되어 데이터가 사라졌다면 마이그레이션을 다시 실행해야 한다.
이전 Complete Job은 자동 재실행되지 않는다.

## 접속

각 명령은 별도 터미널에서 유지한다.
로컬 Docker 앱 등과 8000·3000 포트가 충돌하지 않아야 한다.

```bash
kubectl --context movie-review-eks -n movie-app port-forward svc/backend 8000:8000
kubectl --context movie-review-eks -n movie-app port-forward svc/frontend 3000:3000
```

- API: http://localhost:8000/
- 영화 목록: http://localhost:8000/movies
- 화면: http://localhost:3000/movies

## 비용 관리

EKS·EC2·EBS·퍼블릭 IPv4는 사용 조건에 따라 과금된다.
맥북이나 포트포워딩을 종료해도 AWS 리소스는 삭제되지 않는다.
실습 종료 시 삭제 계획을 확인하고 유료 리소스 및 잔존 리소스를 정리한다.

## Metrics Server 및 HPA 검증 — 2026-10-01

- Metrics Server v0.9.0으로 노드·Pod CPU 및 메모리 조회 확인
- backend HPA: 최소 1개, 최대 2개, CPU request 대비 목표 50%
- 컨테이너 내부에서 120초간 인위적인 CPU 부하 발생
- CPU 사용률 상승에 따라 Pod 1 → 2 확장 확인
- 부하 종료 후 CPU 사용률 하락에 따라 Pod 2 → 1 축소 확인
- 실제 사용자 트래픽 성능이나 노드 자동 확장은 검증하지 않음

재배포 시 Metrics Server 설치와 앱 준비 완료 후 hpa.yaml을 적용한다.
HPA 운영 중 resources.json의 backend replicas 값을 다시 적용하면
HPA가 관리하는 replica 수에 간섭할 수 있으므로 주의한다.

## ALB 및 GitOps 검증 — 2026-10-02~03

- AWS Load Balancer Controller와 EKS Pod Identity를 구성했다.
- ALB 주소로 프론트엔드 접속 및 /backend-api/movies 응답을 확인했다.
- Next.js rewrite로 브라우저 API 요청을 내부 backend Service로 전달했다.
- ALB 접속 검증과 캡처 후 Ingress를 삭제하고 ALB 삭제를 확인했다.
- Argo CD에서 공개 Git 저장소의 k8s/gitops/movie-app 경로를 연결했다.
- Git의 frontend replicas 변경으로 1 → 2 → 1 자동 반영을 확인했다.
- GitHub Actions가 backend·frontend 이미지를 ECR에 업로드하고,
  GitOps Deployment의 이미지 digest를 갱신하는 커밋을 생성하도록 구성했다.
- Argo CD가 해당 커밋을 감지해 EKS에 자동 배포하는 흐름을 검증했다.

### 디스크 부족 장애와 복구

증상:
- 새 backend 이미지 압축 해제 중 no space left on device 발생.
- ephemeral-storage 부족으로 새 Pod가 Evicted되고 배포가 지연됐다.
- 기존 backend Pod는 Running 상태를 유지했다.

원인 및 조치:
- 20GiB 노드에서 기존 이미지와 새 이미지의 다운로드·압축 해제 공간이 부족했다.
- Linux 의존성에 NVIDIA CUDA와 Triton 등 GPU 관련 패키지가 포함되어 있었다.
- GitOps의 backend digest를 기존 정상 이미지로 되돌려 복구했다.
- Argo CD Synced/Healthy 및 노드 DiskPressure=False를 확인했다.
- Linux용 PyTorch를 CPU 전용으로 변경하고 uv 설치 캐시를 이미지에 남기지 않도록 수정했다.

검증 결과:
- 로컬 CPU 이미지 크기: docker image inspect 기준 약 0.97GiB.
- 로컬에서 GPU 관련 패키지 부재 및 sentence-transformers import 성공 확인.
- 소스 커밋: e05756c.
- 자동 이미지 갱신 커밋: 3a85373.
- 해당 배포 커밋으로 Argo CD Synced/Healthy 확인.
- EKS backend에서 torch 2.14.1+cpu, CUDA build None 확인.
- backend rollout 성공 및 노드 DiskPressure=False 확인.
- ECR의 압축 크기와 로컬 이미지 크기는 측정 기준이 달라 직접 감소율을 계산하지 않았다.

### 재배포와 구성 관리

- k8s/gitops/movie-app은 Argo CD가 지속적으로 관리하는 앱 구성이다.
- k8s/eks-demo/resources.json과 migrate.json은 초기 구성용 스냅샷이다.
- 이번 스냅샷의 앱·마이그레이션 이미지는 검증된 GitOps digest로 갱신했다.
- 향후 CI가 GitOps 이미지를 갱신해도 eks-demo 스냅샷은 자동 갱신되지 않는다.
- 새 클러스터에서는 namespace, Secret, ConfigMap, Service, PostgreSQL,
  마이그레이션을 먼저 준비한 뒤 앱을 배포한다.
- Argo CD 관리 시작 후 앱 변경은 GitOps 경로에서 수행한다.
- resources.json 전체를 반복 적용하면 GitOps 설정과 충돌할 수 있다.
- Secret, PostgreSQL, 마이그레이션 Job, ALB Ingress는 현재 Application의 관리 대상이 아니다.
- PostgreSQL은 emptyDir이므로 Pod 또는 클러스터 삭제 시 데이터가 사라진다.
- DB가 초기화되면 마이그레이션을 다시 실행해야 한다.
- Completed 마이그레이션 Job은 이미지 파일을 변경해도 자동 재실행되지 않는다.
  기존 Job이 남아 있다면 삭제 후 새로 생성해야 한다.

### 검증 범위 보충

앞선 2026-10-01 기록 이후 ALB 접속과 GitOps 자동 배포를 추가 검증했다.
영화 수집·LLM 분석 전체 흐름, 데이터 영속성, 장기 모니터링,
노드 장애 복구 및 무중단 서비스는 아직 검증하지 않았다.


## Prometheus·Grafana 모니터링 검증 — 2026-10-04

- Prometheus·Grafana로 앱 Pod와 노드의 CPU·메모리·네트워크·디스크 지표를 확인했다.
- 120초 CPU 부하에 따른 그래프 상승·하락과 부하 후 앱 상태를 확인했다.
- 단기 모니터링 검증이며 장기 보관과 외부 알림은 포함하지 않는다.
- 설치 및 재현 절차: [모니터링 README](../monitoring/README.md)

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
- 데이터 수집·LLM 분석, HPA, 모니터링, 자동 배포는 아직 검증하지 않았다.
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

# PostgreSQL 백업·복구 검증

## 목적

영화 리뷰 서비스의 PostgreSQL 데이터를 논리 백업하고,
별도 DB에 복원한 뒤 데이터 일치 여부를 검증한다.

## 실험 환경

- 검증일: 2026-10-19
- 환경: Mac의 로컬 k3d, rancher-lab 클러스터
- Namespace: backup-lab
- PostgreSQL: 16.15, ARM64
- 저장소: local-path PVC 1Gi
- 원본 DB: movie_app_lab
- 복원 DB: movie_app_restore
- 실제 앱 Alembic 마이그레이션: b9a8c7d6e5f4
- 테스트 데이터: 영화 100건, 리뷰 10,000건
- 백업 크기: 약 107KB(ls -lh 표시 기준)

## 수행 과정

1. 실제 앱의 Alembic 마이그레이션으로 테이블을 생성했다.
2. movies와 reviews에 합성 테스트 데이터를 입력했다.
3. 행 수, 기본키 순으로 정렬한 데이터의 MD5 체크섬,
   Alembic 버전을 원본 비교 기준으로 저장했다.
4. pg_dump -Fc로 DB 전체를 백업하고 Mac에 저장했다.
5. template0를 사용해 빈 복원 대상 DB를 생성했다.
6. pg_restore --exit-on-error --single-transaction으로 복원했다.
7. 원본과 복원 DB의 행 수·체크섬·Alembic 버전을 비교했다.
8. 테이블 9개와 연결된 영화가 없는 리뷰 0건을 확인했다.

## 결과

| 항목 | 결과 |
|---|---|
| 새 DB 복원 | 성공 |
| 영화 | 100건, 원본 체크섬 일치 |
| 리뷰 | 10,000건, 원본 체크섬 일치 |
| Alembic 버전 | b9a8c7d6e5f4, 원본 일치 |
| 복원된 테이블 | 9개 |
| 연결된 영화가 없는 리뷰 | 0건 |
| 복원 명령 소요 시간 | 단일 측정 0.151초 |

소요 시간은 Python perf_counter로 측정했다.
kubectl 프로세스 실행, 연결, 백업 전송 및 pg_restore 실행을 포함하며,
복원 대상 DB 생성과 복원 후 검증 시간은 포함하지 않는다.

## 사전 삭제·복구 실험

별도 movie_lab DB의 backup_demo 스키마에서 영화 100건과
리뷰 10,000건을 백업했다. 스키마 삭제 후 테이블 0개를 확인하고
복원하여 두 테이블의 행 수와 체크섬 일치를 확인했다.

이 사전 실험은 단순화한 테스트 테이블을 사용했다.
실제 앱 스키마 실험은 원본을 유지하고 새 DB에 복원하는 방식으로 수행했다.

## 검증 한계

- 로컬 환경의 소규모 합성 데이터에 대한 검증이다.
- 실제 데이터가 있는 movies·reviews와 Alembic 버전을 비교했다.
  나머지 업무 테이블은 데이터가 채워진 상태의 복구를 검증하지 않았다.
- API 정상화, EKS 재해 복구, 전체 서비스 RTO·RPO는 미검증이다.
- 정기 백업, 원격 백업 보관, PITR은 미구현이다.
- local-path PVC는 노드 장애에 대비한 고가용성 저장소가 아니다.
- 0.151초를 운영 환경의 복구 시간으로 일반화하지 않는다.

## 증거

- [원본 비교 기준](evidence/postgres-backup-restore/before.txt)
- [복원 후 결과](evidence/postgres-backup-restore/after.txt)
- [복원 시간 및 종료 코드](evidence/postgres-backup-restore/restore-result.json)

## 자동 검증 스크립트

DB·스키마·합성 데이터 준비는 [로컬 재현 안내](local-reproduction.md)를 참고한다. 저장소 루트에서 실행한다.

```bash
python3 scripts/infra/verify-postgres-restore.py
```

### 실행 전제

- Python 3와 kubectl이 설치되어 있어야 한다.
- k3d-rancher-lab 클러스터가 실행 중이어야 한다.
- backup-lab의 postgres-0 Pod가 정상 실행 중이어야 한다.
- lab 사용자가 movie_app_lab에 접근하고 DB를 생성할 수 있어야 한다.
- 원본 DB에 앱 마이그레이션과 테스트 데이터가 준비되어 있어야 한다.
- 비교 중에는 원본 DB 쓰기를 중지해야 한다.

스크립트는 환경 구축이나 데이터 입력을 수행하지 않는다.
kubectl exec로 실행하므로 port-forward는 필요하지 않다.

### 동작

1. 원본 행 수·체크섬·Alembic 버전을 기록한다.
2. DB 전체를 백업하고 백업 목록을 읽을 수 있는지 확인한다.
3. 실행 시각을 이름에 포함한 빈 DB를 생성한다.
4. 백업을 복원하고 명령 소요 시간을 측정한다.
5. 원본과 복원 DB의 비교 기준 및 public 테이블 목록을 비교한다.
6. 연결된 영화가 없는 리뷰 수를 확인한다.

기록과 백업은 ~/movie-review-backup-lab/auto-실행시각에 저장한다.
복원 DB는 검증 후에도 남으며 자동 삭제하지 않는다.

### 자동 실행 결과

- 백업 크기: 109,402바이트
- 복원 명령 소요 시간: 0.15342초
- 행 수·체크섬·Alembic 버전: 일치
- public 테이블 목록: 일치
- 연결된 영화가 없는 리뷰: 0건
- 최종 판정: 성공

[자동 실행 결과](evidence/postgres-backup-restore/automated/result.json)

자동화한 범위는 복원 검증이며, 정기 백업 스케줄링은 포함하지 않는다.

# CI/CD 배포 검증 — 2026-10-20

## 확인 결과
- GitHub Actions의 Python quality, Secret scan, 이미지 검사 및 Quality gate 통과.
- 검증된 이미지를 ECR에 업로드하고 배포 PR #8 생성.
- 배포 PR 검사 통과 후 수동 병합.
- EKS 재생성 후 초기 배포와 DB 마이그레이션 완료.
- Argo CD movie-app: Synced / Healthy.
- ALB를 통한 프론트엔드 /movies: HTTP 200.
- 프론트엔드 경유 /backend-api/movies: HTTP 200.
- KOBIS API에서 2026-10-19 기준 영화 10편을 수집하고 DB 저장 및 API 조회 확인.

## 초기 배포 설정
GitOps에서 승인한 이미지 digest에 맞춰 초기 배포용 resources.json과
DB 마이그레이션용 migrate.json을 갱신했다.

## 확인 범위와 제한
- 취약점 정책 통과는 취약점이 없다는 뜻이 아니다.
- 임시 취약점 예외 만료일은 2026-11-03이며 만료 전 재검토가 필요하다.
- 리뷰 수집부터 LLM 분석까지 전체 파이프라인은 이번에 검증하지 않았다.
- 대시보드는 분석 완료 영화만 표시하므로, 수집한 영화 10편의 화면 표시는 확인하지 못했다.
- 분석 전 영화 표시와 영화 목록 자동 수집은 후속 작업이다.

## 종료 확인
- PostgreSQL 백업을 로컬에 보관하고 pg_restore --list로 목록을 확인했다.
  이번 백업의 실제 복원 시험은 수행하지 않았다.
- 프로젝트 ALB 삭제 확인.
- EKS 관련 리소스 11개 삭제 후 서울 리전 클러스터 목록이 비어 있음을 확인.
- 프로젝트 VPC에 종료되지 않은 EC2 인스턴스가 없음을 확인.
- 서울 리전의 available 상태 EBS 볼륨이 없음을 확인.
- ECR 이미지와 GitHub Actions 권한은 유지했다.
- 다른 리전·서비스 및 청구액 전체가 0임을 확인한 것은 아니다.

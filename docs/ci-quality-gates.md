# CI 품질 검증 및 배포 통제

## 동작

1. `main` 대상 모든 PR에서 Python 검사, secret 검사, 두 컨테이너의 빌드/취약점 검사를 실행한다. PR에는 AWS 인증이나 저장소 쓰기 권한을 주지 않는다.
2. `Quality gate`는 모든 검사 성공 시에만 성공한다. 실패/취소/건너뜀은 성공으로 취급하지 않는다.
3. 애플리케이션 및 CI 관련 파일이 `main`에 반영되면 같은 검사를 다시 실행한다. `main`의 수동 실행도 같은 검사를 거친다.
4. 통과한 Docker 이미지를 artifact로 전달하고, **재빌드 없이 동일한 이미지**를 OIDC 인증으로 ECR에 push한다. `latest` 대신 소스 커밋 SHA 태그를 사용한다.
5. ECR에서 digest를 조회해 GitOps Deployment 두 파일만 변경하는 별도 PR을 생성한다. 기존의 `main` 직접 push는 제거했다.
6. 사람이 배포 PR의 검사/변경을 확인하고 병합하면 Argo CD가 반영한다. 이미지 게시 자체는 클러스터 배포 승인이 아니다.

GitOps 파일만 바뀌는 병합은 push 경로 필터에서 제외되어 이미지 생성/배포 PR의 무한 반복이 발생하지 않는다. PR 검사는 경로 필터 없이 실행하여 required check가 영원히 Pending이 되는 일을 피한다.

## 최초 활성화 — 저장소 소유자가 설정해야 하는 항목

이 문서와 워크플로를 커밋하는 것만으로 브랜치 보호가 활성화되지는 않는다. GitHub 연결 도구는 administration API를 제공하지 않으므로 아래 항목은 저장소 Settings에서 적용한다.

### Actions

Settings → Actions → General → Workflow permissions:

- `Allow GitHub Actions to create and approve pull requests`를 활성화한다. 이 워크플로는 PR 생성에만 사용하고 자동 승인하지 않는다.
- 기본 토큰 권한은 읽기 전용으로 유지할 수 있다. publish job에만 contents/pull-requests write를 명시했다.

### main 보호

Settings → Branches → Add branch protection rule에서 `main`을 지정한다. Rulesets를 사용하는 경우 동일한 조건으로 만들고 Enforcement를 Active로 설정한다.

- Require a pull request before merging.
- Require status checks to pass before merging → **Quality gate** 선택 (첫 실행 후 검색 가능).
- Require branches to be up to date before merging.
- Do not allow bypassing the above settings / 관리자 우회 금지.
- force push 및 branch deletion 허용하지 않음.
- 1인 프로젝트에서는 required approving reviews를 1로 설정하면 작성자가 자신의 PR을 승인할 수 없어 막힌다. PR 필수 + 검사 필수 + 사람이 병합하는 방식으로 운영한다. 별도 리뷰어가 생기면 1명 승인과 stale approval 해제를 추가한다.

보호 설정 전에는 CI 실패가 `main` 직접 push나 관리자 병합을 막아주지 않는다. 보호 규칙과 워크플로가 함께 적용되어야 한다.

### 봇이 생성한 배포 PR의 검사 실행

`GITHUB_TOKEN`으로 생성한 PR은 GitHub의 재귀 실행 방지 정책 때문에 다른 Actions 실행을 자동으로 발생시키지 않는다. 배포 PR에서 저장소 소유자가 **Close pull request → Reopen pull request**를 직접 실행하면 `pull_request` 검사가 실행된다. 검사를 우회하거나 required check를 해제하지 않는다.

여러 배포 PR이 있으면 소스 커밋/CI 링크를 비교해 최신 의도한 버전을 선택하고 이전 PR을 닫는다. 이전 digest PR을 뒤늦게 병합하면 롤백이 될 수 있다. ECR의 digest와 연결된 커밋을 확인한 후 병합한다.

현재 OIDC role의 `repo:httpJun/movie-review-devops:ref:refs/heads/main` 신뢰 조건을 유지할 수 있도록 publish job에 environment를 추가하지 않았다. 환경 승인 기능을 나중에 도입하면 AWS trust policy의 `sub`도 environment 형식에 맞춰 별도로 변경해야 한다.

## 검사 범위와 실패 대응

| 검사 | 범위 | 실패 시 조치 |
| --- | --- | --- |
| Ruff | app, scripts, alembic, tests의 E9/F63/F7/F82: 문법 및 일부 런타임 오류 | 표시된 코드 수정. 스타일 전체 준수나 타입 안전성을 의미하지 않음 |
| pytest | 라벨 생성의 순서/누락/빈 응답/잘못된 JSON/API 실패/키 누락, 대표 문구 빈도 | 실패 케이스와 실제 구현 확인. 정책의 신규 탐지·수정 버전 공개·만료 차단도 검증. 외부 DB/실제 수집 통합 테스트는 미포함 |
| Trivy secret | 저장소 작업 트리 | 실제 유출이면 키 폐기/교체 후 코드에서 제거. 과거 Git 이력 전체 검사는 아님 |
| Trivy image | 모든 심각도를 JSON으로 보관하고 HIGH/CRITICAL 정책 평가 | 전체 artifact와 Actions summary에서 차단/유예 내역 확인 |
| Image smoke | API/프론트엔드 HTTP, Chromium, ML 기본 인코딩 | 런타임 호환성 확인; 실제 사전학습 모델·외부 서비스 전체 회귀 검증은 아님 |

### 취약점 처리 정책 (2026-10-29 재검토)

- 수정 버전이 있는 HIGH/CRITICAL: 무조건 차단. 기존 유예 목록에 있어도 차단한다.
- 수정 버전이 없는 신규 HIGH/CRITICAL: 검토되지 않은 항목이므로 차단한다.
- 기존 58건: `security/vulnerability-exceptions.json`에 등록된 backend Debian의 패키지·설치 버전·CVE·심각도가 모두 일치할 때만 임시 유예한다.
- 유예 만료일은 **2026-11-10 (UTC) 당일부터 차단**, 담당자는 저장소 소유자 httpJun이다. 자동 연장은 없다. 한국 시간으로 당일 오전 9시부터 적용된다.
- 패키지/버전/심각도 변경, 새로운 CVE, 수정 버전 공개 시 새 평가 대상이 된다. frontend로 예외가 전파되지 않는다.
- LOW/MEDIUM/UNKNOWN도 전체 JSON에 남기되 현재 자동 배포 차단 대상은 아니다.

이는 개인 포트폴리오/데모 범위에서의 최초 14일 유예에 7일을 추가한 한시적 위험 수용이며, 취약점이 수정되었거나 악용 불가능하다는 판단이 아니다. 특히 libxml2의 CRITICAL CVE-2026-6653은 남아 있다. 공개 운영/실제 사용자 데이터 취급 전에는 별도 영향 분석과 보완이 필요하다. 목록과 사유/담당자/만료일을 PR에서 함께 검토한다.

Trivy 자체는 `ignore-unfixed: false`, 모든 심각도, JSON 출력, `exit-code: 0`으로 전체 결과를 생성한다. 바로 다음 **Enforce vulnerability policy** 단계가 위 기준을 적용해 exit 1로 차단한다. 따라서 스캐너의 exit 0이 전체 게이트 통과를 의미하지 않는다. DB 다운로드/스캐너 실행 오류는 그대로 실패하며 `continue-on-error`는 사용하지 않는다.

전체 Trivy JSON은 30일간 artifact로 보관하고, 차단/유예 개수와 유예 CVE를 Actions Summary에 표시한다. `.trivyignore`로 결과를 숨기지 않는다. 각 PR/main 실행에서 DB를 다시 확인하며, 담당자는 주 1회 및 만료 전 main의 수동 CI로 재검토한다. 자동 주기 실행이나 알림을 설정한 것은 아니다. 유예 목록을 갱신할 때는 항목별 근거와 새 만료일을 별도 PR로 남긴다.


## 로컬 검증

```bash
python3.12 -m venv .venv-ci
.venv-ci/bin/python -m pip install -r requirements-ci.txt
.venv-ci/bin/ruff check app scripts alembic tests
.venv-ci/bin/python -m pytest -q
```

CI용 의존성은 외부 API를 mock하는 격리된 단위 테스트에 필요한 최소 집합이다. 프로덕션 전체 의존성은 Dockerfile의 `uv sync --frozen --no-dev`로 설치하고 최종 이미지를 검사한다.

## 실패 차단 검증 절차

1. 임시 PR에서 테스트의 예상 결과를 일부러 틀리게 변경한다 → Python quality/Quality gate 실패, publish는 실행되지 않아야 한다.
2. 임시 PR에서 정의되지 않은 변수를 추가한다 → Ruff 실패, Quality gate 실패.
3. Trivy가 실패한 실행의 artifact를 열어 HIGH/CRITICAL 항목과 차단 결과를 확인한다. 취약한 이미지를 운영 환경에 배포해서 검증하지 않는다.
4. 보호 규칙 활성화 후 실패 PR의 병합 버튼이 차단되는지 확인하고, 임시 변경을 되돌린다.
5. 정상 소스 PR 병합 후 ECR 게시와 배포 PR 생성을 확인한다. 배포 PR을 닫았다 다시 열어 검사한 후 병합하고 Argo CD/실제 HTTP 응답을 확인한다.

로컬 단위 테스트 성공만으로 ECR 권한, GitHub 보호 규칙, 실제 배포까지 검증되었다고 기록하지 않는다. Actions 실행 링크와 병합 차단 화면, 배포 후 HTTP 검증 결과를 별도로 남긴다.

## 2026-10-29 예외 재검토 및 7일 연장

- 저장소 소유자의 요청으로 기존 58건의 만료일을 2026-11-03에서 2026-11-10으로 연장했다. 새 예외는 추가하지 않았다.
- 근거: [main CI 40868649327](https://github.com/httpJun/movie-review-devops/actions/runs/40868649327). backend 차단 0/유예 58, frontend 차단 0/유예 0.
- Debian Security Tracker의 trixie 정보를 대조한 결과, 중복 제외 20개 CVE 모두 open이며 수정 버전이 제공되지 않았다. 데이터: https://security-tracker.debian.org/tracker/data/json (2026-10-29 조회).
- EKS는 종료된 상태이며, 재가동 또는 공개 운영 전 재검토한다. CRITICAL libxml2를 포함한 잔여 위험은 해결되지 않았다.
- 수정 버전이 있는 항목, 신규/변경된 항목은 계속 차단한다. 2026-11-10 00:00 UTC(한국 시간 09:00)부터 기존 예외도 차단하며 자동 연장은 없다.

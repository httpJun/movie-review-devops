# 2차 파이프라인 공통 설계 문서

## LLM 기반 영화 리뷰 의견 구조화 시스템 (Real Data + PostgreSQL 기반)

---

# 1. 프로젝트 개요

## 프로젝트 목적

대량의 영화 리뷰 데이터를 분석하여 핵심 의견을 구조화하고, 사용자에게 요약된 인사이트를 제공하는 시스템 구축.

---

## 핵심 목표

* 리뷰 데이터 자동 분석
* 핵심 표현 추출
* 감정 분석
* 유사 의견 그룹화
* 사용자 친화적 요약 제공
* Real Data 기반 확장 가능한 구조 설계

---

# 2. 시스템 아키텍처

```text
Real Data / Dataset
        ↓
Pipeline (B)
        ↓
LLM Module (C)
        ↓
Embedding + Clustering (D)
        ↓
Final Result Builder
        ↓
Frontend (A)
```

---

# 3. 시스템 역할 분리 (A/B/C/D)

---

## A. Frontend

### 역할

* 결과 시각화
* 사용자 인터랙션
* 의견 조회 및 페이지네이션

### 주요 기능

* Top 3 의견 표시
* 긍정/부정 비율 표시
* 의견별 리뷰 조회
* 페이지네이션

### 추천 기술 스택

```text
Next.js
TypeScript
Tailwind CSS
shadcn/ui
TanStack Query
```

---

## B. Pipeline / API Layer

### 역할

* 전체 파이프라인 orchestration
* Job 관리
* 모듈 실행
* 결과 조합

### 주요 기능

* Job 생성
* run-llm 실행
* run-cluster 실행
* final-result 생성
* 결과 조회 API 제공

### 기술 스택

```text
FastAPI
SQLAlchemy
Alembic
PostgreSQL
```

---

## C. LLM Module

### 역할

* 리뷰에서 핵심 표현 추출
* sentiment 분석

### 출력 형태

```json
{
  "review_id": "r001",
  "phrases": [
    {
      "text": "연기 좋음",
      "sentiment": "positive"
    },
    {
      "text": "스토리 아쉬움",
      "sentiment": "negative"
    }
  ]
}
```

---

## D. Embedding + Clustering Module

### 역할

* phrase embedding
* 유사 의견 그룹화

### 기술 스택

```text
sentence-transformers
HDBSCAN
```

---

# 4. 데이터 처리 흐름

---

## 1단계. 리뷰 수집

### 입력 데이터

```text
Dataset / Real Data
```

### 저장 위치

```text
reviews table
```

---

## 2단계. LLM 처리

### 수행 작업

* 핵심 표현 추출
* sentiment 분석

### 저장 위치

```text
llm_phrases table
```

---

## 3단계. Embedding

### 수행 작업

* phrase → vector 변환

### 사용 모델

```text
sentence-transformers
```

### 목적

* 의미 기반 유사도 계산 가능하게 변환

---

## 4단계. Clustering

### 수행 작업

* 유사한 표현 자동 그룹화

### 사용 알고리즘

```text
HDBSCAN
```

### 목적

* 주요 의견 도출

---

## 5단계. Final Result 생성

### 수행 작업

* Top 의견 계산
* 긍/부정 비율 계산
* Frontend 응답용 데이터 생성

---

# 5. 임베딩 및 클러스터링 상세 설명

---

## sentence-transformer 역할

### 목적

문장을 의미 기반 숫자 벡터로 변환.

---

### 예시

```text
"연기 좋다"
→ [0.12, -0.52, 0.91, ...]
```

```text
"배우 연기 최고"
→ [0.11, -0.49, 0.88, ...]
```

→ 의미가 비슷하면 벡터 거리도 가까워짐.

---

## HDBSCAN 역할

### 목적

유사한 의미를 가진 표현 자동 그룹화.

---

### 예시

```text
연기 좋다
배우 연기 최고
연기 미쳤다
```

→ 같은 클러스터로 그룹화.

---

### 특징

* 클러스터 개수 자동 결정
* 노이즈 제거 가능
* 밀도 기반 군집화

---

# 6. API 구조

---

## Job 기반 구조

### 실행 API

```text
POST /batch/jobs
POST /batch/jobs/{job_id}/run-llm
POST /batch/jobs/{job_id}/run-cluster
POST /batch/jobs/{job_id}/build-final
```

---

## 결과 조회 API

```text
GET /batch/jobs/{job_id}/final-result
GET /batch/jobs/{job_id}/opinion-groups
GET /batch/jobs/{job_id}/opinion-groups/{cluster_id}/reviews
```

---

# 7. Frontend 데이터 흐름

---

## final-result

### 제공 데이터

* Top 3 의견
* 긍정/부정 비율

---

## opinion-groups

### 제공 데이터

* 전체 의견 목록
* count
* total_count

---

## opinion-group reviews

### 제공 데이터

* 특정 의견 관련 리뷰
* 페이지네이션

---

# 8. PostgreSQL 기반 DB 구조

---

# 사용 기술

```text
PostgreSQL
SQLAlchemy 2.0 ORM
Alembic
psycopg
```

---

# 주요 테이블

---

## movies

```text
movie_id
movie_title
release_year
source
```

---

## reviews

```text
review_id
movie_id
text
source
collected_at
is_processed
```

---

## batch_jobs

```text
job_id
movie_id
status
created_at
updated_at
```

---

## llm_phrases

```text
phrase_id
review_id
movie_id
text
sentiment
created_at
```

---

## opinion_groups

```text
cluster_id
movie_id
topic
sentiment
label
count
review_count
updated_at
```

---

## review_cluster_map

```text
id
cluster_id
review_id
```

---

## movie_summary

```text
movie_id
positive_percent
negative_percent
positive_review_count
negative_review_count
tie_review_count
total_review_count
updated_at
```

---

# 9. ORM 구조

---

## ORM 라이브러리

```text
SQLAlchemy 2.0 ORM
```

---

## Migration 관리

```text
Alembic
```

### 목적

* DB 스키마 변경 이력 관리
* 안전한 테이블 구조 변경

---

## ORM Model과 API Schema 분리

### ORM Model

```python
class Review(Base):
```

→ DB 저장용

---

### Pydantic Schema

```python
class ReviewResponse(BaseModel):
```

→ API 응답용

---

# 10. Real Data 확장 전략

---

## 일일 배치 시스템

### 목적

* 신규 리뷰만 처리
* 전체 재분석 방지

---

## 처리 흐름

```text
신규 리뷰 수집
→ is_processed = false 조회
→ LLM 처리
→ Clustering
→ summary 갱신
→ is_processed = true
```

---

## 결과 누적 구조

### 목적

* 기존 분석 결과 유지
* 비용 절감
* 성능 향상

---

# 11. KPI

---

## 분석 정확도

### 표현 추출

```text
F1 Score ≥ 0.75
```

### 클러스터 품질

```text
Silhouette Score ≥ 0.3
```

### Top3 의견 적합도

```text
≥ 70%
```

---

## 처리 성능

```text
1000~3000개 리뷰
하루 단위 처리
```

---

## 서비스 품질

```text
API 응답 속도 ≤ 1초
```

※ 결과 조회 API 기준

---

# 12. KPI 측정 방법

---

## 표현 추출 평가

### 방식

* 사람이 정답 정의
* Precision / Recall 계산

---

## 클러스터 품질 평가

### 방식

* Silhouette Score 활용
* 군집 분리도 평가

---

# 13. 향후 계획

---

## OpenAI 기반 LLM 적용

### 목적

* 표현 추출 정확도 향상

---

## DB 구조 고도화

### 목적

* 대용량 데이터 처리
* 서비스 안정성 향상

---

## 실시간 데이터 확장

### 목적

* 실서비스 대응

---

# 14. 핵심 설계 원칙

---

## 낮은 결합도

* 모듈 독립성 유지
* API 기반 연결

---

## 높은 응집도

* 역할별 책임 분리
* 모듈 단일 책임 유지

---

## 확장 가능한 구조

* Real Data 대응 가능
* DB 기반 확장 가능
* 모듈 교체 가능

---

# 최종 결론

본 프로젝트는 단순 감성 분석이 아닌,
대량의 리뷰 데이터를 의미 기반으로 구조화하여 사용자에게 핵심 의견을 제공하는 시스템이다.

또한 PostgreSQL + SQLAlchemy + Alembic 기반 구조를 통해,
실제 서비스 수준의 확장성과 유지보수성을 고려한 파이프라인으로 발전시키는 것을 목표로 한다.




















---

# 영화 리뷰 분석 프로젝트 공통 설계 문서

## 1. 프로젝트 개요

본 프로젝트는 **영화 리뷰를 일일 배치(batch) 방식으로 분석**하여, 사용자가 영화 페이지에 접속했을 때 **미리 생성된 리뷰 요약 결과**를 조회할 수 있도록 하는 시스템이다.

실시간으로 사용자의 요청마다 즉시 리뷰를 분석하는 구조가 아니라,
**분석 대상 영화에 대해 하루 동안 리뷰를 수집하고, 정해진 시점에 배치 작업을 수행한 뒤, 다음 조회 시 저장된 결과를 반환하는 구조**로 설계한다.

최종적으로 사용자는 네이버 지도의 음식점 리뷰 요약처럼, 영화별로 다음과 같은 형태의 결과를 보게 된다.

* 많이 언급된 리뷰 포인트
* 긍정/부정 방향
* 대표 키워드
* 대표 문장 예시

---

## 2. 팀 역할

* **A (프론트엔드)**: 페이지 기획, 요청 화면/상태 화면/결과 화면 구현
* **B (파이프라인 및 데이터 관리)**: 분석 대상 영화 관리, 배치 작업 관리, C/D 모듈 연동, 최종 결과 저장 및 조회 API 설계
* **C (LLM 모듈)**: 리뷰 원문에서 핵심 표현(key phrases) 추출
* **D (클러스터링 모듈)**: 핵심 표현들을 의미 기반으로 그룹화

---

## 3. 시스템 흐름

전체 파이프라인은 아래 순서로 동작한다.

```text
분석 대상 영화 등록
→ 배치 작업(job) 생성
→ 리뷰 수집
→ C(LLM) 핵심 표현 추출
→ 중간 결과 저장
→ D(클러스터링) 군집화
→ 최종 결과 저장
→ 프론트에서 저장된 결과 조회
```

즉, 프론트는 분석 결과를 즉시 생성하는 것이 아니라,
**이미 배치 처리되어 저장된 결과를 조회해서 보여주는 역할**을 한다.

---

## 4. 개발 기준

* 백엔드 및 파이프라인 기준 언어: **Python**
* API 서버 기준: **FastAPI**
* 초기 저장 방식: **JSON 파일**
* 필요 시 추후 **SQLite 또는 DB**로 확장 가능

권장 초기 구조 예시:

```text
project/
├─ app/
│  ├─ main.py
│  ├─ schemas.py
│  ├─ services/
│  │  ├─ movie_service.py
│  │  ├─ job_service.py
│  │  ├─ llm_service.py
│  │  ├─ cluster_service.py
│  │  └─ result_service.py
│  └─ routers/
│     ├─ movies.py
│     ├─ jobs.py
│     └─ results.py
├─ data/
│  ├─ movies.json
│  ├─ jobs.json
│  ├─ llm_results.json
│  ├─ cluster_results.json
│  └─ final_results.json
└─ README.md
```

---

## 5. 공통 필드 규칙

모든 스키마는 아래 규칙을 따른다.

* 필드명은 **snake_case**
* 날짜/시간은 **ISO 8601 문자열**
* 활성 여부는 `is_` 접두사 사용
* 식별자는 문자열(string)로 통일
* 내부 추적용 ID는 반드시 유지

예:

* `movie_id`
* `job_id`
* `review_id`
* `registered_at`
* `updated_at`
* `is_active`

---

## 6. 분석 대상 영화 스키마

분석 대상 영화 스키마는 **우리 시스템이 어떤 영화를 관리할지 정의하는 기준 데이터**이다.

### 목적

* 어떤 영화를 배치 분석할지 관리
* 배치 작업 생성 시 기준 데이터로 사용
* 프론트/결과 조회 시 영화 식별 기준으로 사용

### 스키마

```json
{
  "movie_id": "mv_001",
  "movie_title": "파묘",
  "source": "naver",
  "is_active": true,
  "registered_at": "2026-03-27T10:00:00",
  "updated_at": "2026-03-27T10:00:00",
  "release_year": 2024,
  "notes": "시연용 대표 영화"
}
```

### 필드 설명

* `movie_id`: 내부 관리용 고유 ID
* `movie_title`: 영화 제목
* `source`: 리뷰 출처 (`naver`, `imdb` 등)
* `is_active`: 현재 분석 대상 여부
* `registered_at`: 등록 시각
* `updated_at`: 마지막 수정 시각
* `release_year`: 개봉 연도
* `notes`: 관리용 메모

---

## 7. 배치 작업(Job) 스키마

배치 작업 스키마는 **어떤 영화에 대해 어떤 날짜 기준 분석을 수행하는지 기록하는 실행 단위**이다.

### 목적

* 배치 작업 생성 및 추적
* 작업 상태 관리
* 디버깅 및 로그 확인
* 프론트 상태 조회에 활용

### 스키마

```json
{
  "job_id": "job_001",
  "movie_id": "mv_001",
  "movie_title": "파묘",
  "target_date": "2026-03-27",
  "status": "queued",
  "created_at": "2026-03-27T23:50:00",
  "started_at": null,
  "finished_at": null
}
```

### 필드 설명

* `job_id`: 배치 작업 고유 ID
* `movie_id`: 대상 영화 ID
* `movie_title`: 사람이 보기 쉬운 영화 제목
* `target_date`: 이 날짜까지 수집된 리뷰를 기준으로 분석
* `status`: 현재 작업 상태
* `created_at`: 작업 생성 시각
* `started_at`: 작업 시작 시각
* `finished_at`: 작업 종료 시각

---

## 8. 배치 상태값(Status) 정의

배치 작업 상태는 아래 값으로 고정한다.

```text
queued
collecting_reviews
llm_processing
clustering
saving_results
completed
failed
```

### 상태 흐름

```text
queued
→ collecting_reviews
→ llm_processing
→ clustering
→ saving_results
→ completed
```

에러 발생 시 어느 단계에서든 `failed`로 전환할 수 있다.

---

## 9. 모듈 간 데이터 형식

이 프로젝트는 B가 중심이 되어 A, C, D 모듈을 연결한다.
아래 데이터 형식은 **모듈 간 공통 규약**으로 사용한다.

---

### 9-1. B → C : LLM 추출 요청 스키마

B가 C에게 리뷰 원문을 전달하여 핵심 표현 추출을 요청할 때 사용한다.

```json
{
  "job_id": "job_001",
  "movie_id": "mv_001",
  "movie_title": "파묘",
  "target_date": "2026-03-27",
  "reviews": [
    {
      "review_id": "r1",
      "text": "연기는 좋았는데 스토리는 지루했다."
    },
    {
      "review_id": "r2",
      "text": "배우 몰입감이 좋고 분위기가 무서웠다."
    }
  ]
}
```

#### 필드 설명

* `job_id`: 배치 작업 추적용
* `movie_id`: 영화 식별용
* `movie_title`: 로그/확인용
* `target_date`: 분석 기준 날짜
* `reviews`: 리뷰 목록

  * `review_id`: 리뷰 고유 ID
  * `text`: 리뷰 원문

---

### 9-2. C → B : LLM 추출 결과 스키마

C가 리뷰별 핵심 표현을 추출하여 B에게 반환할 때 사용한다.

```json
{
  "job_id": "job_001",
  "movie_id": "mv_001",
  "results": [
    {
      "review_id": "r1",
      "key_phrases": [
        "연기 좋음",
        "스토리 지루함"
      ]
    },
    {
      "review_id": "r2",
      "key_phrases": [
        "배우 몰입감 높음",
        "공포 분위기 강함"
      ]
    }
  ]
}
```

#### 필드 설명

* `job_id`: 배치 작업 추적용
* `movie_id`: 영화 식별용
* `results`: 리뷰별 추출 결과

  * `review_id`: 원본 리뷰 ID
  * `key_phrases`: 핵심 표현 문자열 배열

#### `key_phrases` 규칙

* 문자열 배열로 고정
* 리뷰당 2~5개 권장
* 짧고 명확한 표현 사용
* 클러스터링에 적합하도록 너무 긴 문장 금지

예:

* `"연기 좋음"` O
* `"전체적으로 배우들의 연기가 굉장히 인상적이어서 몰입감이 높았다"` X

---

### 9-3. B → D : 클러스터링 요청 스키마

B가 C의 결과를 정리하여 D에게 군집화를 요청할 때 사용한다.

```json
{
  "job_id": "job_001",
  "movie_id": "mv_001",
  "movie_title": "파묘",
  "phrases": [
    {
      "review_id": "r1",
      "text": "연기 좋음"
    },
    {
      "review_id": "r1",
      "text": "스토리 지루함"
    },
    {
      "review_id": "r2",
      "text": "배우 몰입감 높음"
    },
    {
      "review_id": "r2",
      "text": "공포 분위기 강함"
    }
  ]
}
```

#### 필드 설명

* `job_id`: 배치 작업 추적용
* `movie_id`: 영화 식별용
* `movie_title`: 로그/확인용
* `phrases`: 군집화 대상 핵심 표현 목록

  * `review_id`: 원본 리뷰 추적용
  * `text`: 군집화할 핵심 표현

---

### 9-4. D → B : 클러스터링 결과 스키마

D가 유사한 핵심 표현들을 묶은 결과를 B에게 반환할 때 사용한다.

```json
{
  "job_id": "job_001",
  "movie_id": "mv_001",
  "clusters": [
    {
      "cluster_id": 1,
      "topic": "연기",
      "items": [
        {
          "review_id": "r1",
          "text": "연기 좋음"
        },
        {
          "review_id": "r3",
          "text": "배우 연기 뛰어남"
        }
      ]
    },
    {
      "cluster_id": 2,
      "topic": "스토리",
      "items": [
        {
          "review_id": "r1",
          "text": "스토리 지루함"
        },
        {
          "review_id": "r4",
          "text": "전개 느림"
        }
      ]
    }
  ]
}
```

#### 필드 설명

* `job_id`: 배치 작업 추적용
* `movie_id`: 영화 식별용
* `clusters`: 클러스터 목록

  * `cluster_id`: 군집 ID
  * `topic`: 군집 대표 주제명
  * `items`: 해당 군집에 포함된 핵심 표현 목록

    * `review_id`: 원본 리뷰 ID
    * `text`: 핵심 표현 텍스트

---

## 10. 최종 결과 스키마

최종 결과 스키마는 **프론트가 바로 사용할 수 있는 영화별 리뷰 요약 데이터**이다.

이 구조는 네이버 지도 리뷰 요약과 유사한 사용자 경험을 목표로 한다.

### 스키마

```json
{
  "movie_id": "mv_001",
  "movie_title": "파묘",
  "analysis_date": "2026-03-27",
  "total_reviews": 408,
  "review_summary": [
    {
      "label": "연기가 좋아요",
      "count": 325,
      "ratio": 0.8,
      "examples": [
        "배우 연기가 뛰어남",
        "연기 몰입감 좋음"
      ]
    },
    {
      "label": "스토리가 아쉬워요",
      "count": 120,
      "ratio": 0.29,
      "examples": [
        "스토리 전개가 느림",
        "서사가 지루함"
      ]
    },
    {
      "label": "영상미가 좋아요",
      "count": 210,
      "ratio": 0.51,
      "examples": [
        "영상미가 뛰어남",
        "화면 연출이 좋음"
      ]
    }
  ]
}
```

### 필드 설명

* `movie_id`: 영화 ID
* `movie_title`: 영화 제목
* `analysis_date`: 분석 기준 날짜
* `total_reviews`: 분석에 사용된 전체 리뷰 수
* `review_summary`: 최종 요약 카드 목록

  * `label`: 사용자에게 보여줄 요약 문구
  * `count`: 해당 요약에 해당하는 표현 수
  * `ratio`: 전체 대비 비율
  * `examples`: 대표 문장 예시

---

## 11. 저장 파일 예시

초기 개발 단계에서는 아래 JSON 파일 기반으로 시작한다.

* `movies.json`: 분석 대상 영화 목록
* `jobs.json`: 배치 작업 목록
* `llm_results.json`: C 모듈 결과 저장
* `cluster_results.json`: D 모듈 결과 저장
* `final_results.json`: 최종 프론트 조회용 결과 저장

---

## 12. B의 역할 정리

B는 본 프로젝트에서 **파이프라인 오케스트레이터** 역할을 수행한다.

주요 책임은 다음과 같다.

1. 분석 대상 영화 관리
2. 배치 작업 생성 및 상태 관리
3. 리뷰 데이터 준비
4. C(LLM) 모듈 호출 및 결과 저장
5. D(클러스터링) 모듈 호출 및 결과 저장
6. 최종 결과를 프론트용 형태로 가공
7. 프론트 조회용 API 설계 및 제공

즉, B는 단순 백엔드가 아니라 **프론트(A), LLM(C), 클러스터링(D)을 연결하여 최종 서비스 결과를 만드는 중심 역할**이다.

---

## 13. 향후 구현 순서

권장 구현 순서는 아래와 같다.

1. `movies.json` 샘플 작성
2. `jobs.json` 샘플 작성
3. B → C / C → B 더미 JSON 연결
4. B → D / D → B 더미 JSON 연결
5. `final_results.json` 생성
6. FastAPI 조회 API 구현
7. 프론트(A)와 연결
8. 실제 배치 실행 로직 연결

---

## 14. 요약

이 프로젝트는 **실시간 분석 서비스가 아니라, 분석 대상 영화에 대해 일일 배치 방식으로 리뷰를 처리하고, 저장된 결과를 다음 조회 시 제공하는 구조**이다.

따라서 핵심은 다음 세 가지다.

* 어떤 영화를 분석할지 관리하는 것
* 어떤 배치 작업이 언제 수행됐는지 관리하는 것
* 모듈 간 데이터 형식을 통일해 안정적으로 연결하는 것

---

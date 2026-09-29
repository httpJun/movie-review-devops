import type {
  DashboardMovie,
  DashboardMoviesResponse,
  DashboardSummary,
  JobStatus,
  KeywordSentiment,
  RecentActivity,
  SentimentRatio,
  TopKeyword,
} from "./types";

import summaryMock from "./mock/dashboard-summary.json";
import moviesMock from "./mock/dashboard-movies.json";

const BASE_URL =
  process.env.API_BASE_URL ?? "http://backend:8000";

// 백엔드 대시보드 API가 준비될 때까지 mock 사용.
// .env에 NEXT_PUBLIC_USE_MOCK_DASHBOARD=false 를 넣으면 실제 API 호출.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_DASHBOARD !== "false";

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  if (USE_MOCK) {
    return summaryMock as DashboardSummary;
  }

  const res = await fetch(`${BASE_URL}/dashboard/summary`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`대시보드 summary 조회 실패: ${res.status}`);
  }
  return res.json();
}

export async function fetchDashboardMovies(): Promise<DashboardMoviesResponse> {
  if (USE_MOCK) {
    return moviesMock as DashboardMoviesResponse;
  }

  const res = await fetch(`${BASE_URL}/dashboard/movies`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`대시보드 movies 조회 실패: ${res.status}`);
  }
  return res.json();
}

// ============================================
// 실 API (/dashboard/*) → 프론트 타입 어댑터
// ============================================
//
// 백엔드 응답 모양(app/schemas.py: DashboardMovieItem, DashboardSummaryResponse)을
// 프론트가 쓰는 DashboardMovie / DashboardSummary 모양으로 변환한다.
// latest_job_id 는 백엔드가 movie 객체에 직접 실어 보낸다.
// 백엔드에 없는 필드(avg_processing_seconds, overall_sentiment, top_keywords_overall,
// job_status, job_completed_at 등)는 안전한 기본값(0 / 빈 배열 / null)으로 채운다.

type ApiSentimentRatio = {
  positive_percent: number;
  negative_percent: number;
};

type ApiTopKeyword = {
  rank: number;
  topic?: string;
  sentiment: string;
  label: string;
  count: number;
};

type ApiDashboardMovieItem = {
  movie_id: string;
  movie_title: string;
  poster_url: string | null;
  genre: string | null;
  release_year: number | null;
  release_date: string | null;
  source: string | null;
  total_review_count: number;
  sentiment_ratio: ApiSentimentRatio;
  top_keywords: ApiTopKeyword[];
  latest_job_id: string | null;
};

type ApiDashboardMoviesResponse = {
  items: ApiDashboardMovieItem[];
  total_count: number;
};

type ApiRecentJob = {
  job_id: string;
  movie_id: string;
  movie_title: string;
  status: string;
  finished_at: string | null;
};

type ApiDashboardSummaryResponse = {
  total_movies: number;
  total_completed_jobs: number;
  total_reviews_analyzed: number;
  recent_jobs: ApiRecentJob[];
  updated_at: string;
};

function normalizeJobStatus(status: string): JobStatus {
  if (status === "completed" || status === "running" || status === "failed") {
    return status;
  }
  // 파이프라인 중간 상태(queued / llm_processing / clustering 등)는 "running"으로 묶음
  return "running";
}

function normalizeKeywordSentiment(s: string): KeywordSentiment {
  if (s === "positive" || s === "negative" || s === "neutral") return s;
  return "neutral";
}

function splitGenres(genre: string | null): string[] {
  if (!genre) return [];
  return genre
    .split(",")
    .map((g) => g.trim())
    .filter((g) => g.length > 0);
}

function adaptTopKeyword(k: ApiTopKeyword): TopKeyword {
  return {
    rank: k.rank,
    label: k.label,
    sentiment: normalizeKeywordSentiment(k.sentiment),
    count: k.count,
  };
}

function adaptMovie(item: ApiDashboardMovieItem): DashboardMovie {
  const sentiment: SentimentRatio = {
    positive_percent: item.sentiment_ratio?.positive_percent ?? 0,
    negative_percent: item.sentiment_ratio?.negative_percent ?? 0,
  };

  return {
    movie_id: item.movie_id,
    movie_title: item.movie_title,
    source: item.source ?? "",
    is_active: true,
    release_year: item.release_year ?? 0,
    poster_url: item.poster_url,
    release_date: item.release_date,
    genres: splitGenres(item.genre),
    latest_job_id: item.latest_job_id,
    job_status: null,
    job_completed_at: null,
    review_count: item.total_review_count,
    sentiment,
    top_keywords: (item.top_keywords ?? []).map(adaptTopKeyword),
  };
}

function adaptSummary(api: ApiDashboardSummaryResponse): DashboardSummary {
  const recent_activities: RecentActivity[] = (api.recent_jobs ?? []).map(
    (j) => ({
      movie_id: j.movie_id,
      movie_title: j.movie_title,
      status: normalizeJobStatus(j.status),
      completed_at: j.finished_at ?? "",
    }),
  );

  return {
    total_movies: api.total_movies,
    completed_movies: api.total_completed_jobs,
    total_reviews: api.total_reviews_analyzed,
    // 실 API에 없는 필드는 안전한 기본값으로 채움 — /movies 페이지는 사용하지 않음
    avg_processing_seconds: 0,
    overall_sentiment: { positive_percent: 0, negative_percent: 0 },
    top_keywords_overall: [],
    recent_activities,
    updated_at: api.updated_at,
  };
}

export type DashboardData = {
  movies: DashboardMovie[];
  summary: DashboardSummary;
  total: number;
};

/**
 * /dashboard/summary 와 /dashboard/movies 를 함께 호출해서
 * 프론트가 쓰는 모양으로 변환해 반환한다.
 *
 * - mock 토글(USE_MOCK)은 보지 않음. 항상 실 API.
 * - latest_job_id 는 movie 객체에 백엔드가 직접 실어 보냄. null 인 영화는
 *   결과 페이지 링크 없음 → 카드가 disabled 상태로 렌더링.
 * - 호출 실패 시 throw — 호출자가 try/catch 로 에러 UI 처리.
 */
export async function fetchDashboardData(): Promise<DashboardData> {
  const [summaryRes, moviesRes] = await Promise.all([
    fetch(`${BASE_URL}/dashboard/summary`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
    }),
    fetch(`${BASE_URL}/dashboard/movies`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
    }),
  ]);

  if (!summaryRes.ok) {
    throw new Error(`대시보드 summary 조회 실패: ${summaryRes.status}`);
  }
  if (!moviesRes.ok) {
    throw new Error(`대시보드 movies 조회 실패: ${moviesRes.status}`);
  }

  const summaryApi = (await summaryRes.json()) as ApiDashboardSummaryResponse;
  const moviesApi = (await moviesRes.json()) as ApiDashboardMoviesResponse;

  const summary = adaptSummary(summaryApi);
  const movies = (moviesApi.items ?? []).map(adaptMovie);

  return {
    movies,
    summary,
    total: moviesApi.total_count ?? movies.length,
  };
}

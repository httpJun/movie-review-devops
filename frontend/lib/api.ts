import {
  BatchJobResponse,
  FinalResult,
  Movie,
  OpinionGroup,
  OpinionGroupReviewsResponse,
} from "./types";

const BASE_URL =
  typeof window === "undefined"
    ? process.env.API_BASE_URL ?? "http://backend:8000"
    : "/backend-api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API 요청 실패: ${res.status}`);
  }

  return res.json();
}

export function getMovies() {
  return request<Movie[]>("/movies");
}

export function createBatchJob(movieId: string, targetDate: string) {
  return request<BatchJobResponse>("/batch/jobs", {
    method: "POST",
    body: JSON.stringify({
      movie_id: movieId,
      target_date: targetDate,
    }),
  });
}

export async function runBatchPipeline(jobId: string) {
  await request(`/batch/jobs/${jobId}/run-llm`, {
    method: "POST",
  });

  await request(`/batch/jobs/${jobId}/run-cluster`, {
    method: "POST",
    body: JSON.stringify({
      cluster_mode: "hdbscan",
    }),
  });

  await request(`/batch/jobs/${jobId}/build-final`, {
    method: "POST",
  });
}

export function getFinalResult(jobId: string) {
  return request<FinalResult>(`/batch/jobs/${jobId}/final-result`);
}

export function getOpinionGroups(jobId: string) {
  return request<OpinionGroup[]>(`/batch/jobs/${jobId}/opinion-groups`);
}

export function getOpinionGroupReviews(
  jobId: string,
  clusterId: string | number,
  page: number,
  pageSize: number
) {
  return request<OpinionGroupReviewsResponse>(
    `/batch/jobs/${jobId}/opinion-groups/${clusterId}/reviews?page=${page}&page_size=${pageSize}`
  );
}

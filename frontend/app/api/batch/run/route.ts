import { NextRequest, NextResponse } from "next/server";

const BASE_URL =
  process.env.API_BASE_URL ?? "http://backend:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const movieId = body.movie_id;
    const targetDate = body.target_date;

    if (!movieId || !targetDate) {
      return NextResponse.json(
        { message: "movie_id와 target_date가 필요합니다." },
        { status: 400 }
      );
    }

    const createJobRes = await fetch(`${BASE_URL}/batch/jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        movie_id: movieId,
        target_date: targetDate,
      }),
    });

    if (!createJobRes.ok) {
      const errorText = await createJobRes.text();

      return NextResponse.json(
        {
          message: `작업 생성 실패: ${createJobRes.status}`,
          detail: errorText,
        },
        { status: createJobRes.status }
      );
    }

    const job = await createJobRes.json();
    const jobId = job.job_id;

    if (!jobId) {
      return NextResponse.json(
        { message: "백엔드 응답에 job_id가 없습니다.", job },
        { status: 500 }
      );
    }

    const runLlmRes = await fetch(`${BASE_URL}/batch/jobs/${jobId}/run-llm`, {
      method: "POST",
    });

    if (!runLlmRes.ok) {
      const errorText = await runLlmRes.text();

      return NextResponse.json(
        {
          message: `LLM 분석 실패: ${runLlmRes.status}`,
          detail: errorText,
          job_id: jobId,
        },
        { status: runLlmRes.status }
      );
    }

    const runClusterRes = await fetch(
      `${BASE_URL}/batch/jobs/${jobId}/run-cluster`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          cluster_mode: "hdbscan",
        }),
      }
    );

    if (!runClusterRes.ok) {
      const errorText = await runClusterRes.text();

      return NextResponse.json(
        {
          message: `클러스터링 실패: ${runClusterRes.status}`,
          detail: errorText,
          job_id: jobId,
        },
        { status: runClusterRes.status }
      );
    }

    const buildFinalRes = await fetch(
      `${BASE_URL}/batch/jobs/${jobId}/build-final`,
      {
        method: "POST",
      }
    );

    if (!buildFinalRes.ok) {
      const errorText = await buildFinalRes.text();

      return NextResponse.json(
        {
          message: `최종 결과 생성 실패: ${buildFinalRes.status}`,
          detail: errorText,
          job_id: jobId,
        },
        { status: buildFinalRes.status }
      );
    }

    return NextResponse.json({
      job_id: jobId,
      movie_id: movieId,
      target_date: targetDate,
      status: "completed",
    });
  } catch (error) {
    return NextResponse.json(
      {
        message:
          error instanceof Error
            ? error.message
            : "분석 실행 중 알 수 없는 오류가 발생했습니다.",
      },
      { status: 500 }
    );
  }
}

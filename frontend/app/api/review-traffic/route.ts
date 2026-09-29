import { NextRequest, NextResponse } from "next/server";

const BASE_URL =
  process.env.API_BASE_URL ?? "http://backend:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const movieId = searchParams.get("movieId");
  const granularity = searchParams.get("granularity") ?? "day";

  if (!movieId) {
    return NextResponse.json(
      { message: "movieId가 필요합니다." },
      { status: 400 }
    );
  }

  const backendUrl = `${BASE_URL}/movies/${encodeURIComponent(
    movieId
  )}/review-traffic?granularity=${encodeURIComponent(granularity)}`;

  const res = await fetch(backendUrl, {
    cache: "no-store",
  });

  const data = await res.json();

  if (!res.ok) {
    return NextResponse.json(
      {
        message: `리뷰 트래픽 API 요청 실패: ${res.status}`,
        backendUrl,
        data,
      },
      { status: res.status }
    );
  }

  return NextResponse.json(data);
}

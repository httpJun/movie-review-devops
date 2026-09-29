import { NextRequest, NextResponse } from "next/server";

const BASE_URL =
  process.env.API_BASE_URL ?? "http://backend:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const jobId = searchParams.get("jobId");
  const clusterId = searchParams.get("clusterId");
  const page = searchParams.get("page") ?? "1";
  const pageSize = searchParams.get("pageSize") ?? "5";

  if (!jobId || !clusterId) {
    return NextResponse.json(
      { message: "jobId와 clusterId가 필요합니다." },
      { status: 400 }
    );
  }

  const backendUrl = `${BASE_URL}/batch/jobs/${encodeURIComponent(
    jobId
  )}/opinion-groups/${encodeURIComponent(
    clusterId
  )}/reviews?page=${encodeURIComponent(page)}&page_size=${encodeURIComponent(
    pageSize
  )}`;

  const res = await fetch(backendUrl, {
    cache: "no-store",
  });

  const data = await res.json();

  if (!res.ok) {
    return NextResponse.json(
      {
        message: `리뷰 API 요청 실패: ${res.status}`,
        backendUrl,
        data,
      },
      { status: res.status }
    );
  }

  return NextResponse.json(data);
}

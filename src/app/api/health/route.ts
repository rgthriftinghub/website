import { NextResponse } from "next/server";

// Infrastructure-only endpoint used by the Docker container health check.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok" });
}

import { NextRequest, NextResponse } from "next/server";

import { ConfigError } from "@/lib/chain";
import { readPayoutPreview, readPosition } from "@/lib/market";

const ADDRESS = /^0x[0-9a-fA-F]{40}$/;

export async function GET(request: NextRequest) {
  const id = Number(request.nextUrl.searchParams.get("id"));
  const address = request.nextUrl.searchParams.get("address") ?? "";

  if (!Number.isInteger(id) || id < 0) {
    return NextResponse.json({ error: "a market id is required" }, { status: 400 });
  }
  if (!ADDRESS.test(address)) {
    return NextResponse.json(
      { error: "a 0x-prefixed 20-byte address is required" },
      { status: 400 },
    );
  }

  try {
    const [position, preview] = await Promise.all([
      readPosition(id, address),
      readPayoutPreview(id, address),
    ]);
    return NextResponse.json({ position, preview });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const status = error instanceof ConfigError ? 503 : 502;
    return NextResponse.json({ error: message }, { status });
  }
}

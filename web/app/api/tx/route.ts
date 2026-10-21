import { NextRequest, NextResponse } from "next/server";

import { ConfigError, getTransaction } from "@/lib/chain";

const TX_ID = /^0x[0-9a-fA-F]{64}$/;

export async function GET(request: NextRequest) {
  const txId = request.nextUrl.searchParams.get("id") ?? "";
  if (!TX_ID.test(txId)) {
    return NextResponse.json(
      { error: "a 0x-prefixed 32-byte transaction id is required" },
      { status: 400 },
    );
  }
  try {
    return NextResponse.json(await getTransaction(txId));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const status = error instanceof ConfigError ? 503 : 502;
    return NextResponse.json({ error: message }, { status });
  }
}

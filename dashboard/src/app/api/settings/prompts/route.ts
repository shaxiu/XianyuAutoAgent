import { NextRequest, NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const accountId = new URL(request.url).searchParams.get("account_id");
  if (!accountId) return NextResponse.json({ error: "account_id required" }, { status: 400 });

  const supabase = createSupabaseClient();
  const { data, error } = await supabase
    .from("prompts")
    .select("*")
    .eq("account_id", accountId);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function PUT(request: NextRequest) {
  const { account_id, type, content } = await request.json();
  if (!account_id || !type) {
    return NextResponse.json({ error: "account_id and type required" }, { status: 400 });
  }

  const supabase = createSupabaseClient();
  const { error } = await supabase
    .from("prompts")
    .upsert(
      { account_id, type, content },
      { onConflict: "account_id,type" }
    );

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

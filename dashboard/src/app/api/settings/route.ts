import { NextRequest, NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const accountId = new URL(request.url).searchParams.get("account_id");
  if (!accountId) return NextResponse.json({ error: "account_id required" }, { status: 400 });

  const supabase = createSupabaseClient();
  const { data, error } = await supabase
    .from("accounts")
    .select("*")
    .eq("id", accountId)
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function PUT(request: NextRequest) {
  const body = await request.json();
  const { account_id, ...updates } = body;
  if (!account_id) return NextResponse.json({ error: "account_id required" }, { status: 400 });

  const supabase = createSupabaseClient();
  const { error } = await supabase
    .from("accounts")
    .update(updates)
    .eq("id", account_id);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

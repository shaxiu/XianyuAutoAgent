import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const NOTIFY_EMAIL = Deno.env.get("NOTIFY_EMAIL") || "";

serve(async (req) => {
  const payload = await req.json();
  const record = payload.record;

  // Only notify on ERROR
  if (record.level !== "ERROR") {
    return new Response("not error level", { status: 200 });
  }

  // Send email via Resend
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${RESEND_API_KEY}`,
    },
    body: JSON.stringify({
      from: "Xianyu Monitor <onboarding@resend.dev>",
      to: [NOTIFY_EMAIL],
      subject: `[Xianyu Alert] ${record.message.substring(0, 50)}`,
      html: `
        <h2>Xianyu Bot Error Alert</h2>
        <p><strong>Account:</strong> ${record.account_id}</p>
        <p><strong>Level:</strong> ${record.level}</p>
        <p><strong>Message:</strong> ${record.message}</p>
        <p><strong>Time:</strong> ${record.created_at}</p>
      `,
    }),
  });

  return new Response(JSON.stringify({ sent: res.ok }), { status: 200 });
});

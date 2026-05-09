import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

serve(async (req) => {
  const url    = new URL(req.url);
  const action = url.searchParams.get("action");
  const token  = url.searchParams.get("token");

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const resendKey   = Deno.env.get("RESEND_API_KEY")!;
  const appUrl      = (Deno.env.get("APP_URL") ?? "https://job-creation-dashboard-swart.vercel.app").replace(/\/$/, "");

  const result = (status: string, name = "", msg = "") => {
    const p = new URLSearchParams({ status, app: appUrl });
    if (name) p.set("name", name);
    if (msg)  p.set("msg", msg);
    return Response.redirect(`${appUrl}/access-result.html?${p}`, 302);
  };

  if (!token || !["approve", "reject"].includes(action ?? "")) {
    return result("error", "", "유효하지 않은 링크입니다.");
  }

  const supabase = createClient(supabaseUrl, serviceKey);

  const { data: request, error: fetchError } = await supabase
    .from("access_requests")
    .select("*")
    .eq("token", token)
    .maybeSingle();

  if (fetchError || !request) {
    return result("error", "", "신청 정보를 찾을 수 없습니다.");
  }
  if (request.status !== "pending") {
    return result("already");
  }

  const name = request.name ?? request.email;

  if (action === "approve") {
    const { error: insertError } = await supabase
      .from("approved_users")
      .insert({ email: request.email });

    if (insertError) return result("error", "", "승인 처리 중 오류가 발생했습니다.");

    const { error: updateError } = await supabase
      .from("access_requests")
      .update({ status: "approved", processed_at: new Date().toISOString() })
      .eq("token", token);

    if (updateError) return result("error", "", "처리 중 오류가 발생했습니다.");

    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${resendKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: "onboarding@resend.dev",
        to: request.email,
        subject: "대시보드 접근이 승인되었습니다",
        html: `
          <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
            <h2 style="color:#1a1a1a;margin-bottom:8px">접근 승인 완료</h2>
            <p style="color:#4a4a4a;line-height:1.6">
              안녕하세요, <strong>${name}</strong> 님.<br>
              일자리 창출 결과 대시보드 다운로드 접근이 승인되었습니다.<br>
              이제 Excel 파일을 다운로드하실 수 있습니다.
            </p>
            <a href="${appUrl}"
               style="display:inline-block;margin-top:24px;padding:12px 24px;
                      background:#FF6B35;color:#fff;text-decoration:none;
                      border-radius:8px;font-weight:600;font-size:15px">
              대시보드 바로가기
            </a>
          </div>
        `,
      }),
    });

    return result("approved", name);
  } else {
    const { error: updateError } = await supabase
      .from("access_requests")
      .update({ status: "rejected", processed_at: new Date().toISOString() })
      .eq("token", token);

    if (updateError) return result("error", "", "처리 중 오류가 발생했습니다.");

    return result("rejected", name);
  }
});

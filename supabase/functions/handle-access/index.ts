import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function htmlPage(title: string, message: string): Response {
  return new Response(
    `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: sans-serif; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; margin: 0; background: #fafafa; }
    .box { background: #fff; border-radius: 16px; padding: 40px 36px;
           text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,.08);
           max-width: 400px; width: 90%; }
    h1   { font-size: 22px; margin-bottom: 12px; color: #1a1a1a; }
    p    { color: #4a4a4a; line-height: 1.7; }
  </style>
</head>
<body>
  <div class="box">
    <h1>${escapeHtml(title)}</h1>
    <p>${message}</p>
  </div>
</body>
</html>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

serve(async (req) => {
  const url    = new URL(req.url);
  const action = url.searchParams.get("action");
  const token  = url.searchParams.get("token");

  if (!token || !["approve", "reject"].includes(action ?? "")) {
    return htmlPage("잘못된 요청", "유효하지 않은 링크입니다.");
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const resendKey   = Deno.env.get("RESEND_API_KEY")!;
  const appUrl      = Deno.env.get("APP_URL")!;

  const supabase = createClient(supabaseUrl, serviceKey);

  const { data: request, error: fetchError } = await supabase
    .from("access_requests")
    .select("*")
    .eq("token", token)
    .maybeSingle();

  if (fetchError || !request) {
    return htmlPage("오류", "신청 정보를 찾을 수 없습니다.");
  }
  if (request.status !== "pending") {
    return htmlPage("이미 처리됨", "이미 처리된 신청입니다.");
  }

  if (action === "approve") {
    const { error: updateError } = await supabase
      .from("access_requests")
      .update({ status: "approved", processed_at: new Date().toISOString() })
      .eq("token", token);

    if (updateError) return htmlPage("오류", "처리 중 오류가 발생했습니다.");

    const { error: insertError } = await supabase
      .from("approved_users")
      .insert({ email: request.email });

    if (insertError) return htmlPage("오류", "승인 처리 중 오류가 발생했습니다.");

    const emailRes = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${resendKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: "noreply@dcamp.kr",
        to: request.email,
        subject: "대시보드 접근이 승인되었습니다",
        html: `
          <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
            <h2 style="color:#1a1a1a;margin-bottom:8px">접근 승인 완료</h2>
            <p style="color:#4a4a4a;line-height:1.6">
              안녕하세요, <strong>${escapeHtml(request.name ?? request.email)}</strong> 님.<br>
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

    if (!emailRes.ok) {
      console.error(`Resend error: ${emailRes.status}`);
    }

    const safeName = escapeHtml(request.name ?? request.email);
    const safeEmail = escapeHtml(request.email);
    return htmlPage(
      "✅ 승인 완료",
      `${safeName}(${safeEmail}) 님의 접근이 승인되었습니다.<br>신청자에게 승인 이메일이 발송되었습니다.`
    );
  } else {
    const { error: updateError } = await supabase
      .from("access_requests")
      .update({ status: "rejected", processed_at: new Date().toISOString() })
      .eq("token", token);

    if (updateError) return htmlPage("오류", "처리 중 오류가 발생했습니다.");

    const safeName = escapeHtml(request.name ?? request.email);
    const safeEmail = escapeHtml(request.email);
    return htmlPage(
      "거절 처리 완료",
      `${safeName}(${safeEmail}) 님의 신청이 거절되었습니다.`
    );
  }
});

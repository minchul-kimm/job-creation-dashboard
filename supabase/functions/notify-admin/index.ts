import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "https://job-creation-dashboard-swart.vercel.app",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceKey  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const resendKey   = Deno.env.get("RESEND_API_KEY")!;
    const adminEmail  = Deno.env.get("ADMIN_EMAIL")!;

    // 사용자 JWT 검증
    const auth = req.headers.get("Authorization");
    if (!auth) {
      return new Response(
        JSON.stringify({ error: "인증이 필요합니다." }),
        { status: 401, headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }

    const supabase = createClient(supabaseUrl, serviceKey);
    const { data: { user }, error: authError } = await supabase.auth.getUser(
      auth.replace(/^Bearer\s+/i, "")
    );

    if (authError || !user?.email) {
      return new Response(
        JSON.stringify({ error: "인증에 실패했습니다." }),
        { status: 401, headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }

    const email = user.email;
    const name  = user.user_metadata?.full_name
               || user.user_metadata?.name
               || email;

    // 도메인 검사
    if (email.split("@")[1] !== "dcamp.kr") {
      return new Response(
        JSON.stringify({ error: "dcamp.kr 이메일만 신청 가능합니다." }),
        { status: 403, headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }

    // 중복 신청 확인
    const { data: existing } = await supabase
      .from("access_requests")
      .select("status")
      .eq("email", email)
      .maybeSingle();

    if (existing) {
      return new Response(
        JSON.stringify({ error: "이미 신청이 접수되었습니다." }),
        { status: 409, headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }

    // 토큰 생성 및 신청 기록 저장
    const token = crypto.randomUUID();
    const { error: insertError } = await supabase
      .from("access_requests")
      .insert({ email, name, token });

    if (insertError) throw insertError;

    // 관리자 이메일 발송
    const approveUrl = `${supabaseUrl}/functions/v1/handle-access?action=approve&token=${token}`;
    const rejectUrl  = `${supabaseUrl}/functions/v1/handle-access?action=reject&token=${token}`;

    const emailRes = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${resendKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: "onboarding@resend.dev",
        to: adminEmail,
        subject: `[접근 신청] ${name}(${email}) 님이 다운로드 접근을 신청했습니다`,
        html: `
          <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
            <h2 style="color:#1a1a1a;margin-bottom:8px">대시보드 접근 신청</h2>
            <p style="color:#4a4a4a;line-height:1.6">
              <strong>${name}</strong>(${email}) 님이<br>
              일자리 창출 결과 대시보드 다운로드 접근을 신청했습니다.
            </p>
            <div style="margin-top:28px">
              <a href="${approveUrl}"
                 style="display:inline-block;padding:12px 24px;background:#22C55E;color:#fff;
                        text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">
                ✅ 승인하기
              </a>
              <a href="${rejectUrl}"
                 style="display:inline-block;padding:12px 24px;background:#E63946;color:#fff;
                        text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;
                        margin-left:12px">
                ❌ 거절하기
              </a>
            </div>
            <p style="color:#8a8a8a;font-size:12px;margin-top:32px">
              버튼을 클릭하면 자동으로 처리됩니다.
            </p>
          </div>
        `,
      }),
    });
    if (!emailRes.ok) throw new Error(`Resend error: ${emailRes.status}`);

    return new Response(JSON.stringify({ ok: true }), {
      headers: { ...CORS, "Content-Type": "application/json" },
    });
  } catch (_e) {
    return new Response(
      JSON.stringify({ error: "서버 오류가 발생했습니다." }),
      { status: 500, headers: { ...CORS, "Content-Type": "application/json" } }
    );
  }
});

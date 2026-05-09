# 다운로드 버튼 인증 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 일자리 창출 대시보드의 Excel 다운로드 버튼을 Supabase Google OAuth 로그인 및 관리자 승인 사용자만 사용할 수 있도록 보호한다.

**Architecture:** Vercel에서 정적 HTML을 호스팅하고, Supabase가 Auth·DB·Edge Functions를 담당한다. 다운로드 버튼 클릭 시 로그인 여부와 `approved_users` 테이블 포함 여부를 확인하고, 미승인 `@dcamp.kr` 계정은 접근 신청 → 관리자 이메일 승인 워크플로를 거친다.

**Tech Stack:** Supabase JS SDK v2 (CDN), Supabase Edge Functions (Deno), Resend (이메일), Vercel (정적 호스팅), Google OAuth

---

## 파일 구조

```
github-repo/
├── index.html                              ← 수정 (Auth UI + JS 추가)
└── supabase/
    └── functions/
        ├── notify-admin/
        │   └── index.ts                    ← 신규 (신청 접수 + 관리자 이메일)
        └── handle-access/
            └── index.ts                    ← 신규 (승인/거절 처리 + 신청자 이메일)
```

---

## 사전 준비 — 계정 및 환경 설정

> 이 Task는 외부 서비스 설정으로 코드를 작성하지 않는다. 각 단계를 완료한 후 얻은 값을 메모해 두면 이후 Task에서 사용한다.

### Task 1: Supabase 프로젝트 생성

**Files:** 없음

- [ ] **Step 1: Supabase 프로젝트 생성**

  1. [supabase.com](https://supabase.com) → 로그인 → New Project
  2. Name: `dcamp-dashboard`, Region: `Northeast Asia (Seoul)` 선택
  3. DB 비밀번호 설정 후 Create Project (약 1분 소요)

- [ ] **Step 2: 프로젝트 URL과 anon key 메모**

  Settings → API → 아래 두 값 복사해 둠
  - **Project URL**: `https://xxxxxxxxxxxx.supabase.co`
  - **anon public key**: `eyJ...` (긴 문자열)
  - **service_role key**: `eyJ...` (별도 메모, 외부 노출 금지)

- [ ] **Step 3: Google OAuth 설정**

  1. Supabase → Authentication → Providers → Google → Enable 토글 ON
  2. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성 (또는 기존 프로젝트 사용)
  3. API 및 서비스 → 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 만들기
     - 유형: 웹 애플리케이션
     - 승인된 리디렉션 URI 추가: `https://xxxxxxxxxxxx.supabase.co/auth/v1/callback`
  4. 생성된 **Client ID**와 **Client Secret**을 Supabase Google Provider 설정에 입력 → Save

- [ ] **Step 4: Supabase CLI 설치**

  ```powershell
  npm install -g supabase
  supabase --version
  ```
  예상 출력: `1.x.x` (버전 확인)

- [ ] **Step 5: CLI 로그인 및 프로젝트 연결**

  ```powershell
  cd "C:\Claude Work\1. Job Creation Result\github-repo"
  supabase login
  supabase init
  supabase link --project-ref xxxxxxxxxxxx
  ```
  `supabase init` 은 `supabase/` 디렉토리를 생성한다. `xxxxxxxxxxxx`는 Supabase 프로젝트 URL의 서브도메인 부분.

- [ ] **Step 6: Resend 계정 및 API 키 발급**

  1. [resend.com](https://resend.com) → 가입 → API Keys → Create API Key
  2. 이름: `dcamp-dashboard`, 권한: Full access
  3. 발급된 키(`re_...`) 메모
  4. Domains → Add Domain → `dcamp.kr` 입력 → DNS 레코드 추가 (도메인 관리 패널에서 설정) → Verify

  > Resend 도메인 인증이 완료되어야 `noreply@dcamp.kr` 발신 주소를 사용할 수 있다.

- [ ] **Step 7: 커밋**

  ```powershell
  git add supabase/
  git commit -m "chore: supabase init"
  ```

---

### Task 2: DB 스키마 및 RLS 설정

**Files:** 없음 (Supabase Dashboard SQL Editor에서 직접 실행)

- [ ] **Step 1: 테이블 생성 SQL 실행**

  Supabase Dashboard → SQL Editor → New Query에 아래 SQL 전체 붙여넣고 Run:

  ```sql
  -- approved_users: 다운로드 허용 이메일
  CREATE TABLE approved_users (
    id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    email      text        UNIQUE NOT NULL,
    created_at timestamptz DEFAULT now()
  );

  -- access_requests: 접근 신청 기록
  CREATE TABLE access_requests (
    id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    email        text        NOT NULL,
    name         text,
    status       text        NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'approved', 'rejected')),
    token        text        UNIQUE NOT NULL,
    created_at   timestamptz DEFAULT now(),
    processed_at timestamptz
  );
  ```

- [ ] **Step 2: RLS 정책 적용**

  SQL Editor → New Query:

  ```sql
  -- RLS 활성화
  ALTER TABLE approved_users   ENABLE ROW LEVEL SECURITY;
  ALTER TABLE access_requests  ENABLE ROW LEVEL SECURITY;

  -- 로그인한 사용자는 자신의 이메일만 approved_users에서 조회 가능
  CREATE POLICY "users can check own approval"
    ON approved_users FOR SELECT
    USING (email = auth.jwt() ->> 'email');

  -- 로그인한 사용자는 자신의 신청 내역만 조회 가능
  CREATE POLICY "users can view own requests"
    ON access_requests FOR SELECT
    USING (email = auth.jwt() ->> 'email');

  -- 일반 사용자는 approved_users/access_requests에 직접 쓰기 불가
  -- (Edge Function이 service_role key로만 INSERT/UPDATE)
  ```

- [ ] **Step 3: 초기 승인 사용자 등록**

  SQL Editor → New Query (관리자 본인 이메일로 수정 후 실행):

  ```sql
  INSERT INTO approved_users (email) VALUES
    ('it@dcamp.kr');
  -- 추가 허용 계정이 있으면 계속 추가:
  -- ('other@dcamp.kr');
  ```

- [ ] **Step 4: 테이블 확인**

  SQL Editor:
  ```sql
  SELECT * FROM approved_users;
  SELECT * FROM access_requests;
  ```
  예상: `approved_users`에 1행, `access_requests`는 빈 테이블

---

## Edge Functions

### Task 3: notify-admin Edge Function

**Files:**
- Create: `supabase/functions/notify-admin/index.ts`

- [ ] **Step 1: 파일 생성**

  ```powershell
  cd "C:\Claude Work\1. Job Creation Result\github-repo"
  supabase functions new notify-admin
  ```

- [ ] **Step 2: index.ts 작성**

  `supabase/functions/notify-admin/index.ts` 를 아래 내용으로 교체:

  ```typescript
  import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
  import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

  const CORS = {
    "Access-Control-Allow-Origin": "*",
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
        auth.replace("Bearer ", "")
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
      if (!email.endsWith("@dcamp.kr")) {
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

      await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${resendKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          from: "noreply@dcamp.kr",
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
  ```

- [ ] **Step 3: 환경변수(secrets) 설정**

  ```powershell
  supabase secrets set RESEND_API_KEY=re_여기에_발급받은_키
  supabase secrets set ADMIN_EMAIL=it@dcamp.kr
  ```

- [ ] **Step 4: 배포**

  ```powershell
  supabase functions deploy notify-admin --no-verify-jwt
  ```

  > `--no-verify-jwt` 를 쓰는 이유: JWT 검증을 함수 내부에서 직접 수행하기 때문.

  예상 출력:
  ```
  Deployed Function notify-admin on project xxxxxxxxxxxx
  ```

- [ ] **Step 5: 동작 확인 (curl)**

  아래 명령에서 `<ACCESS_TOKEN>`은 Supabase Dashboard → Authentication → Users에서 테스트 사용자로 로그인한 뒤 얻은 JWT 토큰:

  ```powershell
  curl -X POST `
    https://xxxxxxxxxxxx.supabase.co/functions/v1/notify-admin `
    -H "Authorization: Bearer <ACCESS_TOKEN>" `
    -H "Content-Type: application/json"
  ```

  예상: `{"ok":true}` 반환, 관리자 이메일 수신

- [ ] **Step 6: 커밋**

  ```powershell
  git add supabase/functions/notify-admin/
  git commit -m "feat: notify-admin edge function"
  ```

---

### Task 4: handle-access Edge Function

**Files:**
- Create: `supabase/functions/handle-access/index.ts`

- [ ] **Step 1: 파일 생성**

  ```powershell
  supabase functions new handle-access
  ```

- [ ] **Step 2: index.ts 작성**

  `supabase/functions/handle-access/index.ts` 를 아래 내용으로 교체:

  ```typescript
  import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
  import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

  function html(title: string, message: string): Response {
    return new Response(
      `<!DOCTYPE html>
  <html lang="ko">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
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
      <h1>${title}</h1>
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
      return html("잘못된 요청", "유효하지 않은 링크입니다.");
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceKey  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const resendKey   = Deno.env.get("RESEND_API_KEY")!;
    const appUrl      = Deno.env.get("APP_URL")!;

    const supabase = createClient(supabaseUrl, serviceKey);

    const { data: request } = await supabase
      .from("access_requests")
      .select("*")
      .eq("token", token)
      .maybeSingle();

    if (!request) {
      return html("오류", "신청 정보를 찾을 수 없습니다.");
    }
    if (request.status !== "pending") {
      return html("이미 처리됨", "이미 처리된 신청입니다.");
    }

    if (action === "approve") {
      await supabase
        .from("access_requests")
        .update({ status: "approved", processed_at: new Date().toISOString() })
        .eq("token", token);

      await supabase
        .from("approved_users")
        .insert({ email: request.email });

      await fetch("https://api.resend.com/emails", {
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
                안녕하세요, <strong>${request.name}</strong> 님.<br>
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

      return html(
        "✅ 승인 완료",
        `${request.name}(${request.email}) 님의 접근이 승인되었습니다.<br>신청자에게 승인 이메일이 발송되었습니다.`
      );
    } else {
      await supabase
        .from("access_requests")
        .update({ status: "rejected", processed_at: new Date().toISOString() })
        .eq("token", token);

      return html(
        "거절 처리 완료",
        `${request.name}(${request.email}) 님의 신청이 거절되었습니다.`
      );
    }
  });
  ```

- [ ] **Step 3: APP_URL secret 설정**

  (Vercel 배포 후 URL을 알게 되면 업데이트. 일단 임시값으로 설정)

  ```powershell
  supabase secrets set APP_URL=https://your-project.vercel.app
  ```

- [ ] **Step 4: 배포**

  ```powershell
  supabase functions deploy handle-access --no-verify-jwt
  ```

  예상 출력:
  ```
  Deployed Function handle-access on project xxxxxxxxxxxx
  ```

- [ ] **Step 5: 동작 확인**

  1. Task 3 Step 5에서 신청이 생성된 경우 `access_requests` 테이블에서 token 값 확인
  2. 브라우저에서 접속:
     ```
     https://xxxxxxxxxxxx.supabase.co/functions/v1/handle-access?action=approve&token=<token값>
     ```
  3. 예상: "✅ 승인 완료" 페이지 표시, 신청자에게 이메일 수신, `approved_users`에 행 추가 확인

- [ ] **Step 6: 커밋**

  ```powershell
  git add supabase/functions/handle-access/
  git commit -m "feat: handle-access edge function"
  ```

---

## 프론트엔드 수정

### Task 5: index.html — Auth UI 및 다운로드 로직 수정

**Files:**
- Modify: `index.html`

> `index.html`은 크기가 매우 크다. 각 Step은 추가/수정할 위치를 명확히 지정한다.

- [ ] **Step 1: Supabase SDK CDN 추가**

  `index.html`의 `</head>` 바로 위에 아래 한 줄 추가:

  ```html
  <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  ```

- [ ] **Step 2: Auth 모달 CSS 추가**

  `index.html`의 `</style>` 바로 위에 아래 CSS 블록 추가:

  ```css
  /* ── Auth Modal ── */
  .auth-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;align-items:center;justify-content:center}
  .auth-overlay.open{display:flex}
  .auth-modal{background:#fff;border-radius:18px;padding:40px 36px;max-width:400px;width:90%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.2);position:relative}
  .auth-modal-close{position:absolute;top:14px;right:16px;background:none;border:none;font-size:20px;cursor:pointer;color:var(--muted);line-height:1}
  .auth-modal h2{font-size:20px;font-weight:800;margin-bottom:8px;color:var(--text)}
  .auth-modal-desc{font-size:14px;color:var(--muted);margin-bottom:28px;line-height:1.6;min-height:40px}
  .google-btn{display:inline-flex;align-items:center;gap:10px;padding:12px 24px;background:#fff;border:1.5px solid var(--border-strong);border-radius:10px;font-size:14px;font-weight:600;font-family:inherit;cursor:pointer;transition:.2s;width:100%;justify-content:center}
  .google-btn:hover{border-color:var(--brand);background:var(--brand-bg)}
  .auth-status{margin-top:16px;font-size:13px;color:var(--muted);min-height:20px}
  .request-area{display:none;margin-top:16px}
  .request-btn{display:inline-flex;align-items:center;gap:7px;padding:10px 20px;background:var(--brand);color:#fff;border:none;border-radius:10px;font-size:14px;font-weight:600;font-family:inherit;cursor:pointer;transition:.2s;width:100%;justify-content:center}
  .request-btn:hover{background:var(--brand-dark)}
  .request-btn:disabled{opacity:.6;cursor:not-allowed}
  ```

- [ ] **Step 3: Auth 모달 HTML 추가**

  `index.html`의 `</body>` 바로 위에 아래 HTML 블록 추가:

  ```html
  <!-- Auth Modal -->
  <div id="authOverlay" class="auth-overlay" onclick="if(event.target===this)closeAuthModal()">
    <div class="auth-modal">
      <button class="auth-modal-close" onclick="closeAuthModal()">✕</button>
      <h2>로그인이 필요합니다</h2>
      <p id="authModalDesc" class="auth-modal-desc">
        상세데이터를 다운로드하려면<br>Google 계정으로 로그인해 주세요.
      </p>
      <button class="google-btn" onclick="signInWithGoogle()">
        <svg width="18" height="18" viewBox="0 0 24 24">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
        Google 계정으로 로그인
      </button>
      <p id="authStatus" class="auth-status"></p>
      <div id="requestArea" class="request-area">
        <button class="request-btn" id="requestBtn" onclick="requestAccess()">
          접근 신청하기
        </button>
      </div>
    </div>
  </div>
  ```

- [ ] **Step 4: Auth JavaScript 추가**

  `index.html`의 기존 `<script>` 태그 내부 **맨 앞**에 아래 코드 추가.
  (기존 코드 중 `function switchTab` 바로 위에 삽입)

  > 아래 `YOUR_SUPABASE_URL`과 `YOUR_SUPABASE_ANON_KEY`를 Task 1 Step 2에서 메모한 실제 값으로 교체한다.

  ```javascript
  // ── Supabase Auth ──
  const _SB_URL  = 'YOUR_SUPABASE_URL';
  const _SB_KEY  = 'YOUR_SUPABASE_ANON_KEY';
  const _sb      = window.supabase.createClient(_SB_URL, _SB_KEY);
  let   _user    = null;
  let   _pendingDl = false;

  _sb.auth.onAuthStateChange(async (event, session) => {
    _user = session?.user ?? null;
    if (event === 'SIGNED_IN' && _pendingDl) {
      _pendingDl = false;
      await _checkAndDownload();
    }
  });

  async function signInWithGoogle() {
    await _sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.href },
    });
  }

  async function _checkAndDownload() {
    const email = _user?.email;
    if (!email) return;

    const { data: approved } = await _sb
      .from('approved_users')
      .select('email')
      .eq('email', email)
      .maybeSingle();

    if (approved) {
      closeAuthModal();
      _doDownload();
      return;
    }

    openAuthModal();
    const domain = email.split('@')[1];

    if (domain !== 'dcamp.kr') {
      _setAuthStatus('dcamp.kr 이메일 계정으로만 신청 가능합니다.');
      return;
    }

    const { data: req } = await _sb
      .from('access_requests')
      .select('status')
      .eq('email', email)
      .maybeSingle();

    if (!req) {
      document.getElementById('authModalDesc').textContent = '접근 신청이 필요합니다.';
      document.getElementById('requestArea').style.display = 'block';
    } else if (req.status === 'pending') {
      _setAuthStatus('접근 신청이 검토 중입니다. 승인 후 다운로드가 가능합니다.');
    } else if (req.status === 'approved') {
      // approved_users에 없는데 approved인 엣지케이스 — 재시도
      _setAuthStatus('오류가 발생했습니다. 페이지를 새로고침 해주세요.');
    } else if (req.status === 'rejected') {
      _setAuthStatus('접근 신청이 거절되었습니다. 문의가 필요하시면 관리자에게 연락해 주세요.');
    }
  }

  async function requestAccess() {
    const btn = document.getElementById('requestBtn');
    btn.disabled = true;
    btn.textContent = '신청 중...';

    const { data: { session } } = await _sb.auth.getSession();

    try {
      const res = await fetch(_SB_URL + '/functions/v1/notify-admin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + session.access_token,
        },
      });

      if (res.ok) {
        document.getElementById('requestArea').style.display = 'none';
        _setAuthStatus('접근 신청이 완료되었습니다. 승인 후 이메일로 안내드립니다.');
      } else {
        const err = await res.json();
        _setAuthStatus(err.error || '신청 중 오류가 발생했습니다.');
        btn.disabled = false;
        btn.textContent = '접근 신청하기';
      }
    } catch {
      _setAuthStatus('신청 중 오류가 발생했습니다.');
      btn.disabled = false;
      btn.textContent = '접근 신청하기';
    }
  }

  function openAuthModal() {
    document.getElementById('authOverlay').classList.add('open');
    document.getElementById('authModalDesc').innerHTML =
      '상세데이터를 다운로드하려면<br>Google 계정으로 로그인해 주세요.';
    document.getElementById('authStatus').textContent = '';
    document.getElementById('requestArea').style.display = 'none';
    const btn = document.getElementById('requestBtn');
    btn.disabled = false;
    btn.textContent = '접근 신청하기';
  }

  function closeAuthModal() {
    document.getElementById('authOverlay').classList.remove('open');
    _pendingDl = false;
  }

  function _setAuthStatus(msg) {
    document.getElementById('authModalDesc').textContent = '';
    document.getElementById('authStatus').textContent = msg;
  }

  function _doDownload() {
    const bc = atob(XLSX_B64), ba = new Uint8Array(bc.length);
    for (let i = 0; i < bc.length; i++) ba[i] = bc.charCodeAt(i);
    const blob = new Blob([ba], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url;
    a.download = '2025년_말_기준_일자리_창출_결과_v5.xlsx';
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  }
  ```

- [ ] **Step 5: 기존 downloadExcel() 함수 교체**

  기존 코드 (약 line 862):
  ```javascript
  function downloadExcel(){
    const bc=atob(XLSX_B64),ba=new Uint8Array(bc.length);
    for(let i=0;i<bc.length;i++) ba[i]=bc.charCodeAt(i);
    const blob=new Blob([ba],{type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"});
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url; a.download="2025년_말_기준_일자리_창출_결과_v5.xlsx";
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
  }
  ```

  를 아래로 교체:
  ```javascript
  async function downloadExcel() {
    const { data: { session } } = await _sb.auth.getSession();
    if (!session) {
      _pendingDl = true;
      openAuthModal();
      return;
    }
    _user = session.user;
    await _checkAndDownload();
  }
  ```

- [ ] **Step 6: 로컬에서 동작 확인**

  브라우저에서 `index.html` 직접 열기 (file:// 프로토콜) 대신, 로컬 서버로 실행:

  ```powershell
  npx serve "C:\Claude Work\1. Job Creation Result\github-repo" -p 3000
  ```

  브라우저에서 `http://localhost:3000` 접속 후:
  1. 다운로드 버튼 클릭 → 로그인 모달 표시 확인
  2. Google 로그인 → 승인된 계정이면 즉시 다운로드 확인
  3. 미승인 `@dcamp.kr` 계정이면 "접근 신청하기" 버튼 표시 확인
  4. `@dcamp.kr` 아닌 계정이면 "dcamp.kr 이메일..." 메시지 확인

  > Supabase OAuth redirect가 `localhost`로 돌아오려면 Supabase Dashboard → Authentication → URL Configuration → Redirect URLs에 `http://localhost:3000` 추가 필요.

- [ ] **Step 7: 커밋**

  ```powershell
  git add index.html
  git commit -m "feat: download button auth with Supabase Google OAuth"
  ```

---

## 배포

### Task 6: Vercel 배포 및 최종 설정

**Files:** 없음 (Vercel 대시보드 설정)

- [ ] **Step 1: Vercel GitHub 연동**

  1. [vercel.com](https://vercel.com) → Add New Project
  2. GitHub 저장소 연결 → Import
  3. Framework Preset: **Other** (Next.js 아님)
  4. Root Directory: `/` (기본값 유지)
  5. Deploy 클릭

  배포 완료 후 URL 확인 (예: `https://dcamp-dashboard.vercel.app`)

- [ ] **Step 2: Supabase Redirect URL에 Vercel 도메인 추가**

  Supabase Dashboard → Authentication → URL Configuration:
  - Site URL: `https://dcamp-dashboard.vercel.app`
  - Redirect URLs에 추가: `https://dcamp-dashboard.vercel.app`

- [ ] **Step 3: handle-access의 APP_URL 업데이트**

  ```powershell
  supabase secrets set APP_URL=https://dcamp-dashboard.vercel.app
  supabase functions deploy handle-access --no-verify-jwt
  ```

- [ ] **Step 4: Google OAuth Redirect URI에 Supabase 콜백 추가 확인**

  Google Cloud Console → OAuth 클라이언트에서 아래 URI가 등록되어 있는지 확인:
  - `https://xxxxxxxxxxxx.supabase.co/auth/v1/callback`

- [ ] **Step 5: 전체 흐름 E2E 테스트**

  Vercel 배포 URL에서 순서대로 테스트:

  | 시나리오 | 예상 결과 |
  |---------|----------|
  | 로그인 없이 다운로드 클릭 | 로그인 모달 표시 |
  | `@gmail.com` 계정으로 로그인 후 다운로드 | "dcamp.kr 이메일..." 메시지 |
  | `@dcamp.kr` 미승인 계정 → 접근 신청 | 관리자에게 이메일 수신 |
  | 관리자 이메일에서 [승인하기] 클릭 | "승인 완료" 페이지, 신청자에게 이메일 수신 |
  | 승인된 계정으로 다운로드 클릭 | 모달 없이 즉시 다운로드 |
  | 대기 중 계정으로 다운로드 클릭 | "검토 중입니다" 메시지 |
  | 거절된 계정으로 다운로드 클릭 | "거절되었습니다" 메시지 |
  | 승인 링크 재클릭 (이미 처리) | "이미 처리됨" 페이지 |

- [ ] **Step 6: 최종 커밋 및 GitHub Push**

  ```powershell
  git push origin main
  ```

  Vercel이 자동으로 재배포를 시작한다. 배포 완료 후 동일한 E2E 테스트 반복.

---

## 체크리스트 요약

| Task | 내용 |
|------|------|
| Task 1 | Supabase 프로젝트, Google OAuth, Resend, Supabase CLI 설정 |
| Task 2 | DB 테이블(`approved_users`, `access_requests`) + RLS + 초기 이메일 삽입 |
| Task 3 | `notify-admin` Edge Function 배포 |
| Task 4 | `handle-access` Edge Function 배포 |
| Task 5 | `index.html` Auth UI + 다운로드 로직 수정 |
| Task 6 | Vercel 배포, OAuth redirect 설정, E2E 테스트 |

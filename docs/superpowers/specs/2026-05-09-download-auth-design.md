# 다운로드 버튼 인증 설계

**날짜:** 2026-05-09  
**프로젝트:** 일자리 창출 결과 대시보드  
**범위:** 다운로드 버튼 Google 로그인 보호 + 접근 신청/승인 워크플로

---

## 1. 목표

현재 누구나 클릭할 수 있는 Excel 다운로드 버튼을 로그인한 승인 사용자만 사용할 수 있도록 제한한다. `@dcamp.kr` Google 계정만 접근 신청이 가능하며, 관리자가 이메일로 승인/거절을 처리한다. 승인 시 신청자에게 확인 이메일이 발송된다.

---

## 2. 아키텍처

```
index.html (Vercel 정적 호스팅)
    └── Supabase JS SDK (@supabase/supabase-js)
         ├── Auth: Google OAuth
         └── Database: approved_users, access_requests 테이블

Supabase Edge Functions
    ├── notify-admin     : 신청 시 관리자에게 이메일 발송
    └── handle-access    : 승인/거절 링크 처리, 신청자에게 결과 이메일 발송

이메일 서비스: Resend (무료 3,000건/월)
```

- Vercel은 정적 파일 호스팅 전용  
- 모든 백엔드 로직은 Supabase(DB + Edge Functions)에서 처리  
- 이메일 발송은 Resend API 사용

---

## 3. 데이터 모델

### `approved_users`
다운로드가 허용된 이메일 목록. 초기 허용 계정은 직접 삽입.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | uuid (PK) | 자동 생성 |
| email | text (UNIQUE) | 허용된 Google 이메일 |
| created_at | timestamptz | 추가 일시 |

### `access_requests`
접근 신청 기록 및 처리 상태.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | uuid (PK) | 자동 생성 |
| email | text | 신청자 Google 이메일 |
| name | text | 신청자 이름 (Google 계정 표시명) |
| status | text | `pending` / `approved` / `rejected` |
| token | text (UNIQUE) | 이메일 링크용 보안 토큰 |
| created_at | timestamptz | 신청 일시 |
| processed_at | timestamptz | 처리 일시 (nullable) |

---

## 4. 사용자 흐름

### 4-1. 승인된 사용자
1. 다운로드 버튼 클릭
2. 로그인 모달 → Google 로그인
3. `approved_users` 에서 이메일 확인 → 일치
4. 다운로드 실행

### 4-2. @dcamp.kr 미승인 사용자 (첫 신청)
1. 다운로드 버튼 클릭
2. 로그인 모달 → Google 로그인
3. `approved_users` 불일치, `access_requests` 없음
4. "접근 신청" 버튼 표시
5. 신청 클릭 → `access_requests` 레코드 생성 (status: pending)
6. `notify-admin` Edge Function 호출 → 관리자에게 이메일 발송

### 4-3. @dcamp.kr 미승인 사용자 (신청 대기 중)
1. 다운로드 버튼 클릭 → 로그인
2. `access_requests` status = `pending` 확인
3. "접근 신청이 검토 중입니다" 메시지 표시

### 4-4. 그 외 이메일 (@dcamp.kr 아닌 계정)
1. 다운로드 버튼 클릭 → 로그인
2. 이메일 도메인 확인 → dcamp.kr 아님
3. "dcamp.kr 이메일 계정으로만 신청 가능합니다" 메시지, 신청 불가

### 4-5. 관리자 승인 흐름
1. 신청 이메일 수신
2. [승인하기] 클릭 → `handle-access?action=approve&token=<token>`
3. Edge Function: `access_requests` status → `approved`, `approved_users` 에 이메일 추가
4. 신청자에게 승인 확인 이메일 발송
5. 완료 페이지 표시 ("승인 완료되었습니다")

### 4-6. 관리자 거절 흐름
1. 신청 이메일 수신
2. [거절하기] 클릭 → `handle-access?action=reject&token=<token>`
3. Edge Function: `access_requests` status → `rejected`
4. 완료 페이지 표시 ("거절 처리되었습니다")
5. 신청자에게 별도 알림 없음

### 4-7. 거절된 사용자가 재접근 시
1. 다운로드 버튼 클릭 → 로그인
2. `access_requests` status = `rejected` 확인
3. "접근 신청이 거절되었습니다. 문의가 필요하시면 관리자에게 연락해 주세요." 메시지 표시
4. 재신청 불가 (관리자가 DB에서 직접 레코드 삭제 시 재신청 가능)

---

## 5. 이메일 템플릿

### 관리자 수신 (신청 알림)
```
제목: [접근 신청] {name}({email}) 님이 다운로드 접근을 신청했습니다

{name}({email}) 님이 일자리 창출 결과 대시보드 다운로드 접근을 신청했습니다.

[✅ 승인하기]  →  https://<supabase>/functions/v1/handle-access?action=approve&token=<token>
[❌ 거절하기]  →  https://<supabase>/functions/v1/handle-access?action=reject&token=<token>
```

### 신청자 수신 (승인 확인)
```
제목: 대시보드 접근이 승인되었습니다

안녕하세요, {name} 님.
일자리 창출 결과 대시보드 다운로드 접근이 승인되었습니다.
이제 대시보드에서 Excel 파일을 다운로드하실 수 있습니다.

→ https://<vercel-app-url>
```

---

## 6. 프론트엔드 변경 사항 (index.html)

- Supabase JS SDK CDN 추가
- Supabase 프로젝트 URL / anon key 설정
- `downloadExcel()` 함수 수정:
  - 로그인 상태 확인
  - 미로그인 → 로그인 모달 표시
  - 로그인 후 승인 여부 확인
  - 승인 → 기존 다운로드 로직 실행
  - 미승인 → 도메인 확인 후 신청 UI 표시
- 로그인 모달 컴포넌트 추가 (Google 로그인 버튼)
- 접근 신청 / 상태 표시 UI 추가

---

## 7. 보안 고려사항

- 승인/거절 토큰은 `crypto.randomUUID()` 로 생성, 1회성 처리 (처리 후 재사용 불가)
- Supabase Row Level Security(RLS) 적용: 사용자는 자신의 신청 행만 조회 가능
- `approved_users` 테이블은 클라이언트에서 직접 쓰기 불가 (Edge Function 경유만 허용)
- 도메인 검사는 프론트엔드와 Edge Function 양쪽에서 모두 수행

---

## 8. 외부 서비스 요구사항

| 서비스 | 용도 | 플랜 |
|--------|------|------|
| Supabase | Auth, DB, Edge Functions | Free |
| Vercel | 정적 호스팅 | Free |
| Resend | 이메일 발송 | Free (3,000건/월) |
| Google Cloud Console | OAuth 앱 등록 | 무료 |

---

## 9. 미결 사항

- 관리자 이메일 주소: 구현 전 확인 필요
- Vercel 배포 URL: 배포 후 확정
- Supabase 프로젝트 URL/키: 프로젝트 생성 후 확정

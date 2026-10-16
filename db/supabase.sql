-- ============================================================================
-- Supabase 표 만들기 (한 번만 실행)
--
-- Supabase 대시보드 > SQL Editor > New query 에 이 파일 내용을 통째로 붙여 넣고 Run.
-- 여러 번 실행해도 괜찮다 (이미 있으면 건너뛴다).
--
-- 앱 서버만 서버 전용 키(SUPABASE_SECRET_KEY)로 읽고 쓴다.
-- 브라우저용 공개 키(anon/publishable)로는 아무것도 못 읽게 RLS 를 켜고 허용 규칙을 두지 않는다.
-- 개인정보(생년월일·시간·성별·도시·이름)는 저장하지 않는다. 계산 결과와 그 해시만 둔다.
-- ============================================================================

-- AI 챕터 풀이. key = 사실표·챕터·프롬프트 버전의 해시
create table if not exists public.chapter (
    key        text primary key,
    tab        text not null,
    chapter    text not null,
    source     text not null check (source in ('ai', 'rule')),
    body_json  text not null,
    created    double precision not null
);
create index if not exists chapter_tab on public.chapter (tab, chapter);

-- 저장·공유한 결과. id = 무작위 링크 이름. 사주 원국은 들어 있어서 링크를 받은 사람은 원국을 볼 수 있다.
create table if not exists public.share (
    id          text primary key,
    facts_json  text not null,
    summary     text not null,
    created     double precision not null
);
create index if not exists share_created on public.share (created);

-- 사주를 펼친 결과 (6시간). 서버가 여러 대(Vercel)여도 탭·상담이 이어지게. 개인정보 없이 계산 결과·요약만.
create table if not exists public.ctx (
    token       text primary key,
    summary     text not null,
    target      text not null,
    facts_json  text not null,
    created     double precision not null
);
create index if not exists ctx_created on public.ctx (created);

-- AI 호출 시각 (시간당 총량을 서버 여러 대가 함께 센다)
create table if not exists public.ai_call (
    id  bigserial primary key,
    ts  double precision not null
);
create index if not exists ai_call_ts on public.ai_call (ts);

-- 상담 사용 기록 (한 사람 하루 10번을 서버 여러 대가 함께 센다). k 는 IP·쿠키·결과·사주의 해시, 원래 값은 없다.
create table if not exists public.chat_use (
    id  bigserial primary key,
    k   text not null,
    ts  double precision not null
);
create index if not exists chat_use_k_ts on public.chat_use (k, ts);

-- 방문자 수 (하루·누적). 같은 IP 는 한 사람. IP 를 서버 비밀과 섞은 해시만, IP 원래 값은 없다.
-- visit_day.k 는 날짜도 섞은 해시라 하루 표만으로는 같은 사람이 언제 또 왔는지 이어 볼 수 없다. visitor 는 처음 온 날만.
create table if not exists public.visit_day (
    day  text not null,
    k    text not null,
    primary key (day, k)
);
create table if not exists public.visitor (
    k          text primary key,
    first_day  text not null
);
create index if not exists visitor_first_day on public.visitor (first_day);

-- 날짜별 방문자 숫자. 어제보다 오래된 날의 visit_day 줄을 content_store.purge 가 여기에 숫자로 합치고 지운다.
-- visitors = 그날 온 사람 수, new = 그날 처음 온 사람 수. 누적 방문자 = new 의 합 + 아직 합치지 않은 visitor 수.
create table if not exists public.visit_count (
    day       text primary key,
    visitors  integer not null,
    new       integer not null
);

-- 보관 기간 (content_store.purge 가 앱 서버에서 10분에 한 번 지운다, 2026-10-16 법률 검토)
--   ctx 6시간 / chat_use·ai_call 24시간 / feedback 90일 뒤 ip 를 비우고 365일 뒤 줄을 지움
--   share 365일 / visit_day 는 어제보다 오래되면 visit_count 로 합치고 지움 / visitor 365일

-- 익명 쪽지 (불편한 점·의견, 2026-10-16). 욕설·도배 차단용으로 IP 를 같이 둔다 (화면에 알린다). k 는 IP 해시
create table if not exists public.feedback (
    id    bigserial primary key,
    ts    double precision not null,
    ip    text not null,
    k     text not null,
    body  text not null
);
create index if not exists feedback_k_ts on public.feedback (k, ts);
-- 쪽지를 못 보내게 막은 IP. k(IP 해시)만으로 막고 ip 칸에는 '' 를 넣는다
create table if not exists public.feedback_block (
    k     text primary key,
    ip    text not null,
    note  text not null,
    ts    double precision not null
);

-- 공개 키로는 못 읽고 못 쓰게 잠근다 (서버 전용 키는 RLS 를 거치지 않는다)
alter table public.chapter enable row level security;
alter table public.share enable row level security;
alter table public.ctx enable row level security;
alter table public.ai_call enable row level security;
alter table public.chat_use enable row level security;
alter table public.visit_day enable row level security;
alter table public.visitor enable row level security;
alter table public.visit_count enable row level security;
alter table public.feedback enable row level security;
alter table public.feedback_block enable row level security;
revoke all on public.chapter from anon, authenticated;
revoke all on public.share from anon, authenticated;
revoke all on public.ctx from anon, authenticated;
revoke all on public.ai_call from anon, authenticated;
revoke all on public.chat_use from anon, authenticated;
revoke all on public.visit_day from anon, authenticated;
revoke all on public.visitor from anon, authenticated;
revoke all on public.visit_count from anon, authenticated;
revoke all on public.feedback from anon, authenticated;
revoke all on public.feedback_block from anon, authenticated;

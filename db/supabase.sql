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

-- 공개 키로는 못 읽고 못 쓰게 잠근다 (서버 전용 키는 RLS 를 거치지 않는다)
alter table public.chapter enable row level security;
alter table public.share enable row level security;
revoke all on public.chapter from anon, authenticated;
revoke all on public.share from anon, authenticated;

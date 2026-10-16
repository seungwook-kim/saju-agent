-- ============================================================================
-- 생성 콘텐츠 저장소 초기화 스크립트 (SQLite)
--
-- AI 가 쓴 챕터 풀이를 저장해 다시 쓴다.
-- 앱이 처음 필요할 때 data/content.db 를 이 파일로 만든다 (love_fortune/content_store.py).
-- 해석 데이터(db/init.sql)와 달리 지워도 된다: 지우면 다시 만든다.
-- 개인정보(생년월일·시간·성별·도시·이름)는 저장하지 않는다. 키는 계산 결과의 해시다.
-- ============================================================================

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta VALUES ('schema_version', '1');

-- 챕터 풀이. key = 사실표·챕터·프롬프트 버전의 해시
CREATE TABLE IF NOT EXISTS chapter (
    key        TEXT PRIMARY KEY,
    tab        TEXT NOT NULL,
    chapter    TEXT NOT NULL,
    source     TEXT NOT NULL CHECK (source IN ('ai', 'rule')),
    body_json  TEXT NOT NULL,
    created    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS chapter_tab ON chapter (tab, chapter);

-- 예전 버전의 삽화 목록 표는 쓰지 않는다
DROP TABLE IF EXISTS portrait;

-- 저장·공유한 결과. id = 무작위 링크 이름. 계산 결과(사실표)와 상담용 요약만 둔다.
-- 생년월일·시간·도시·이름은 넣지 않는다. 다만 사주 원국은 들어 있어서, 링크를 받은 사람은 원국을 볼 수 있다.
CREATE TABLE IF NOT EXISTS share (
    id          TEXT PRIMARY KEY,
    facts_json  TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created     REAL NOT NULL
);

-- 방문자 수 (하루·누적). 같은 IP 는 한 사람. IP 를 서버 비밀과 섞은 해시만 둔다. 하루 표의 k 는 날짜도 섞어서 날을 넘어 이어 볼 수 없다
CREATE TABLE IF NOT EXISTS visit_day (
    day  TEXT NOT NULL,
    k    TEXT NOT NULL,
    PRIMARY KEY (day, k)
);
CREATE TABLE IF NOT EXISTS visitor (
    k          TEXT PRIMARY KEY,
    first_day  TEXT NOT NULL
);
-- 보관 기간 (content_store.purge, 2026-10-16 법률 검토): 어제보다 오래된 날의 visit_day 는 날짜별 숫자로 합쳐 지운다.
-- visitor 는 처음 온 날이 365일 지나면 지운다. 쪽지는 90일 뒤 IP 를 비우고 365일 뒤 지운다. 공유 링크는 365일.
CREATE TABLE IF NOT EXISTS visit_count (
    day       TEXT PRIMARY KEY,
    visitors  INTEGER NOT NULL,
    new       INTEGER NOT NULL
);

-- 익명 쪽지 (불편한 점·의견). 욕설·도배 차단용으로 IP 를 같이 둔다 (화면에 알린다). k 는 IP 해시
CREATE TABLE IF NOT EXISTS feedback (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    REAL NOT NULL,
    ip    TEXT NOT NULL,
    k     TEXT NOT NULL,
    body  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_k_ts ON feedback (k, ts);
-- 쪽지를 못 보내게 막은 IP (k = IP 해시). ip 칸은 늘 '' (해시만으로 막는다)
CREATE TABLE IF NOT EXISTS feedback_block (
    k     TEXT PRIMARY KEY,
    ip    TEXT NOT NULL,
    note  TEXT NOT NULL,
    ts    REAL NOT NULL
);

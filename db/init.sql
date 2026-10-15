-- ============================================================================
-- 종합 사주 해석 데이터베이스 초기화 스크립트 (SQLite)
--
-- 앱이 처음 실행될 때 이 파일로 data/fortune.db 를 만든다 (love_fortune/store.py).
-- 저장소를 받은 사람은 따로 할 일이 없다. 직접 만들어 보려면:
--     sqlite3 data/fortune.db < db/init.sql
-- DBeaver 에서는 SQLite 연결로 data/fortune.db 를 열면 된다.
--
-- 계산 규칙(간지·절기·명반·행성 위치)은 코드에 있고, 여기에는 그 결과를 사람 말로
-- 풀어 주는 해석 데이터와 출처만 둔다. 개인정보는 넣지 않는다.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 스키마 버전. 이 값이 바뀌면 앱이 DB 를 다시 만든다.
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO meta VALUES ('schema_version', '2');
INSERT INTO meta VALUES ('description', '종합 사주 해석 데이터 (택일·생기복덕·점성 트랜짓)');

-- 데이터 출처와 검증 방법
CREATE TABLE source (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    url       TEXT,
    used_for  TEXT NOT NULL,
    verified  TEXT NOT NULL
);
INSERT INTO source VALUES
 ('kasi', '한국천문연구원 천문우주지식정보 음양력 변환', 'https://astro.kasi.re.kr/life/pageView/8',
  '음력 날짜·윤달·일진 기준', '무작위 204일 전부 일치 (tests/data/kasi_lunar.json 63건 고정)'),
 ('de421', 'NASA JPL DE421 천체력 (skyfield 로 계산)', 'https://ssd.jpl.nasa.gov/',
  '24절기 입기 시각 1899~2051', '2026·1988년 공개 절기표(DE441+천문연 특일 정보)와 1분 안쪽 일치'),
 ('lunar_python', 'lunar-python (6tail, MIT)', 'https://github.com/6tail/lunar-python',
  '사주 4기둥 대조, 건제12신·황도흑도·28수 표 대조', '4기둥 4,000명 전부 일치, 건제·황도 144칸 전부 일치'),
 ('iztro', 'iztro (MIT)', 'https://github.com/SylarLong/iztro',
  '자미두수 명반·대한·소한·유년·유월·유일 대조', '명반 2,886개, 유월·유일 1,335건 전 항목 일치'),
 ('gunghap', '궁합닷컴 생기복덕 조견표', 'http://www.gunghap.com/taekil/saenggi_p.php3',
  '생기복덕(천기대요) 나이·성별별 표', '괘 변화 규칙으로 계산한 값과 128칸 전부 일치'),
 ('saju_sites', '사주만세 계산 원리, 정해 만세력 강의', 'https://sajumanse.com/calculation/',
  '진태양시·서머타임·야자시 처리 방식', '야자시는 사이트마다 달라 선택 옵션으로 둠'),
 ('transit_orbs', 'Astrodienst Astrowiki 외 트랜짓 오브 해설', 'https://www.astro.com/astrowiki/en/Transit',
  '트랜짓 허용 오차(orb)', '여러 출처가 1~3도를 권함, 달은 조금 넓게');

-- 건제12신 (월건과 일지로 정하는 그날의 성격). 길흉은 한국 자료 기준 6길 6흉
CREATE TABLE officer (
    name     TEXT PRIMARY KEY,
    ord      INTEGER NOT NULL UNIQUE,
    good     INTEGER NOT NULL CHECK (good IN (0, 1)),
    meaning  TEXT NOT NULL,
    advice   TEXT NOT NULL
);
INSERT INTO officer VALUES
 ('건', 0, 0, '세운다는 뜻의 날. 기운이 새로 서며 세게 뻗는다', '계획은 세우되 큰일은 한 번 더 살피기'),
 ('제', 1, 1, '없앤다는 뜻의 날. 묵은 것을 털어낸다', '정리·청소·끊을 것 끊기에 좋은 흐름'),
 ('만', 2, 0, '가득 찬다는 뜻의 날. 넘치기 쉽다', '욕심을 덜고 채운 것을 지키기'),
 ('평', 3, 0, '평평하다는 뜻의 날. 고르지만 밋밋하다', '무리한 승부보다 평소 일을 차분히'),
 ('정', 4, 1, '정한다는 뜻의 날. 자리가 잡힌다', '약속·계약처럼 정하는 일에 좋은 흐름'),
 ('집', 5, 1, '잡는다는 뜻의 날. 붙잡아 지킨다', '마무리·거둬들이기에 좋은 흐름'),
 ('파', 6, 0, '깨뜨린다는 뜻의 날. 틀이 흔들린다', '새 일은 미루고 고칠 것만 고치기'),
 ('위', 7, 1, '위태롭다는 뜻의 날. 조심하면 오히려 길하다고 본다', '안전을 챙기면서 차분히 나아가기'),
 ('성', 8, 1, '이룬다는 뜻의 날. 일이 이루어진다', '시작·약속·축하할 일에 좋은 흐름'),
 ('수', 9, 0, '거둔다는 뜻의 날. 닫아걸기 쉽다', '새로 벌이기보다 거둬들이기'),
 ('개', 10, 1, '연다는 뜻의 날. 길이 열린다', '문을 여는 일, 첫걸음에 좋은 흐름'),
 ('폐', 11, 0, '닫는다는 뜻의 날. 막히기 쉽다', '쉬고 지키며 막힌 곳 점검하기');

-- 황도·흑도 12신
CREATE TABLE heaven_spirit (
    name     TEXT PRIMARY KEY,
    ord      INTEGER NOT NULL UNIQUE,
    yellow   INTEGER NOT NULL CHECK (yellow IN (0, 1)),
    meaning  TEXT NOT NULL
);
INSERT INTO heaven_spirit VALUES
 ('청룡', 0, 1, '푸른 용이 지키는 황도일'),
 ('명당', 1, 1, '밝은 자리라는 황도일'),
 ('천형', 2, 0, '하늘의 형벌이라는 흑도일'),
 ('주작', 3, 0, '붉은 새가 시끄러운 흑도일, 말다툼을 조심'),
 ('금궤', 4, 1, '금 상자라는 황도일'),
 ('천덕', 5, 1, '하늘의 덕이 닿는 황도일'),
 ('백호', 6, 0, '흰 호랑이가 사나운 흑도일, 다침을 조심'),
 ('옥당', 7, 1, '옥으로 지은 집이라는 황도일'),
 ('천뢰', 8, 0, '하늘의 감옥이라는 흑도일'),
 ('현무', 9, 0, '검은 거북이 숨는 흑도일, 잃어버림을 조심'),
 ('사명', 10, 1, '명을 맡은 신이 돕는 황도일'),
 ('구진', 11, 0, '얽히고 걸린다는 흑도일');

-- 생기복덕 여덟 날 (천기대요). luck: 길 / 보통 / 흉
CREATE TABLE saenggi (
    name     TEXT PRIMARY KEY,
    ord      INTEGER NOT NULL UNIQUE,
    luck     TEXT NOT NULL CHECK (luck IN ('길', '보통', '흉')),
    meaning  TEXT NOT NULL
);
INSERT INTO saenggi VALUES
 ('생기', 0, '길', '기운이 살아나는 날'),
 ('천의', 1, '길', '하늘이 돕는 날, 몸을 돌보는 일에 좋다고 본다'),
 ('절체', 2, '보통', '기운이 한풀 꺾이는 날'),
 ('유혼', 3, '보통', '마음이 들떠 떠도는 날'),
 ('화해', 4, '흉', '탈과 해(뜻밖의 사고와 손해)가 끼기 쉬운 날'),
 ('복덕', 5, '길', '복과 덕이 따르는 날'),
 ('절명', 6, '흉', '기운이 끊기기 쉬운 날'),
 ('귀혼', 7, '보통', '제자리로 돌아오는 날');

-- 28수 이름 (길흉은 한국 기준 자료를 확인하지 못해 넣지 않는다)
CREATE TABLE mansion (
    ord   INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
);
INSERT INTO mansion VALUES
 (0,'각'),(1,'항'),(2,'저'),(3,'방'),(4,'심'),(5,'미'),(6,'기'),(7,'두'),(8,'우'),(9,'녀'),
 (10,'허'),(11,'위'),(12,'실'),(13,'벽'),(14,'규'),(15,'루'),(16,'위'),(17,'묘'),(18,'필'),(19,'자'),
 (20,'삼'),(21,'정'),(22,'귀'),(23,'류'),(24,'성'),(25,'장'),(26,'익'),(27,'진');

-- 점성술 행성. 영역 가중치는 전통 상징(금성=사랑·돈, 토성=책임 등)을 따른다.
-- nature: 1 = 길성(금성·목성), -1 = 흉성(화성·토성), 0 = 중립
CREATE TABLE planet (
    code      TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    keywords  TEXT NOT NULL,
    nature    INTEGER NOT NULL CHECK (nature IN (-1, 0, 1)),
    w_love    REAL NOT NULL,
    w_career  REAL NOT NULL,
    w_money   REAL NOT NULL,
    orb       REAL NOT NULL          -- 트랜짓 허용 오차(도), 지나가는 행성 기준
);
INSERT INTO planet VALUES
 ('sun',     '태양', '나 자신, 활력, 인정받기',     0,  0.5, 1.0, 0.3, 3.0),
 ('moon',    '달',   '감정, 몸 상태, 가족',         0,  0.8, 0.3, 0.3, 5.0),
 ('mercury', '수성', '말, 생각, 연락, 문서',        0,  0.4, 0.8, 0.6, 3.0),
 ('venus',   '금성', '사랑, 즐거움, 돈 감각',       1,  1.0, 0.3, 0.8, 3.0),
 ('mars',    '화성', '의욕, 행동, 다툼',           -1,  0.6, 0.8, 0.4, 3.0),
 ('jupiter', '목성', '확장, 기회, 행운',            1,  0.6, 0.8, 1.0, 2.0),
 ('saturn',  '토성', '책임, 제약, 인내',           -1,  0.5, 1.0, 0.7, 2.0);

-- 점성술 각도. harmony: 1 = 부드러움, -1 = 긴장, 0 = 행성 성격을 따름(합)
CREATE TABLE aspect (
    name     TEXT PRIMARY KEY,
    angle    REAL NOT NULL,
    harmony  INTEGER NOT NULL CHECK (harmony IN (-1, 0, 1)),
    talk     TEXT NOT NULL
);
INSERT INTO aspect VALUES
 ('합',   0.0,   0,  '한데 겹쳐 힘이 모이는'),
 ('육합', 60.0,  1,  '가볍게 손잡는'),
 ('형',   90.0, -1,  '직각으로 부딪치는'),
 ('삼합', 120.0, 1,  '순하게 흘러가는'),
 ('충',   180.0, -1, '마주 보고 맞서는');

-- 하우스 (삶의 영역)
CREATE TABLE house (
    num   INTEGER PRIMARY KEY CHECK (num BETWEEN 1 AND 12),
    area  TEXT NOT NULL
);
INSERT INTO house VALUES
 (1,'나 자신과 몸'),(2,'돈과 가진 것'),(3,'말·연락·가까운 이동'),(4,'집과 가족'),
 (5,'연애와 즐거움'),(6,'일상 업무와 건강'),(7,'인연과 파트너'),(8,'함께 쓰는 돈과 변화'),
 (9,'배움과 먼 여행'),(10,'직업과 명예'),(11,'친구와 모임'),(12,'휴식과 마음속');

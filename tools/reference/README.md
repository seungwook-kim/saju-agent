# 기준 자료 대조 스크립트

앱의 계산을 외부 기준과 대조할 때 쓴 스크립트들이다. 앱 실행에는 필요 없다.
결과 일부는 `tests/data/` 에 고정해 두어 `pytest` 가 네트워크 없이 다시 확인한다.

| 스크립트 | 기준 | 만드는 테스트 데이터 |
|---|---|---|
| `saju_pillars.py` | lunar-python (6tail, MIT) | `tests/data/saju_pillars.json` |
| `almanac_and_saenggi.py` | lunar-python, 궁합닷컴 생기복덕 조견표 | `tests/data/almanac_lunar_python.json`, `tests/data/saenggi_table.json` |
| `iztro_charts.py` + `iztro_dump.js` | iztro (npm, MIT) | `tests/data/iztro_charts.json` |
| `iztro_liuyue_liuri.py` + `iztro_dump_horoscope.js` | iztro 운세(유월·유일) | 대조만 (1,335건 전 항목 일치) |

실행 예:

```bash
uv run --no-project --with lunar_python python tools/reference/saju_pillars.py
# iztro: 임시 폴더에서 npm i iztro 후 dump 스크립트를 그 폴더에 두고 실행
```

한국천문연구원 음양력 대조 결과는 `tests/data/kasi_lunar.json` 에 있다
(astro.kasi.re.kr/life/solc, 요청 사이 0.3초 간격).

`tools/data/almanac_terms.json` 은 lunar-python 이 내는 한자 이름을 한글로 옮기는 사전이다.
한자를 저장소에 두지 않으려고 유니코드 이스케이프로만 저장했다. 날짜별 '좋은 일/피할 일'
목록은 중국 통서 방식이라 한국 택일 관행과 달라 버렸다.

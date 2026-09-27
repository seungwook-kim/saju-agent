# 외부 자료와 라이선스 고지

이 저장소에 들어 있는 외부 자료와 그 라이선스다. 라이선스가 요구하는 고지문을 아래에 그대로 둔다.

| 파일 | 원본 | 라이선스 | 쓰는 방식 |
|---|---|---|---|
| `love_fortune/name_hanja.json` | Unicode Unihan 16.0 (부수·획수) | Unicode License v3 | 원획을 계산해 코드포인트와 함께 저장 |
| `love_fortune/name_hanja.json` | rutopio/Korean-Name-Hanja-Charset (대법원 인명용 한자 목록) | MIT | 인명용 한자와 음을 코드포인트와 함께 저장 |
| `love_fortune/name_hanja.json` | libhangul 한자 사전 (data/hanja/hanja.txt) | BSD 3조항 | 훈음(첫 뜻)을 코드포인트와 함께 저장 |
| `tests/data/iztro_charts.json` | iztro (자미두수 명반 계산 결과, 대조용) | MIT | 테스트 기준값 |
| `tests/data/saju_pillars.json`, `twelve_stages.json`, `almanac_lunar_python.json` | lunar-python (6tail, 대조용) | MIT | 테스트 기준값 |
| `tests/data/saenggi_table.json` | 생기복덕 전통 조견표 (우리궁합 표와 대조) | 전통 자료(사실) | 테스트 기준값 |
| `love_fortune/solar_terms_data.py` | NASA JPL DE421 천체력으로 계산 | 미국 정부 공개 자료 | 절기 시각 계산 결과 |
| `love_fortune/calendar_data.py`, `tests/data/kasi_lunar.json` | 한국천문연구원 음양력 자료 | 공공 자료 | 음력 변환표·대조값 |
| `love_fortune/tojeong_data.py` | 토정비결 괘사 (19세기 필사본, 저작권 만료) | 공유 저작물 | 괘사 독음만 두고 풀이는 이 앱이 새로 씀 |
| 화면 글씨체 (`app.css`) | 나눔스퀘어라운드 (네이버, 네이버 글꼴 서버에서 불러옴, 저장소에 넣지 않음) | SIL OFL 1.1 | 화면 본문·제목 글씨체 |
| `love_fortune/johu.py` | 궁통보감 조후용신 표 (청나라 고전, 저작권 만료. 정리표 다섯 곳과 위키문헌 원문으로 대조) | 공유 저작물 | 일간·태어난 달별 먼저 쓰는 기운의 순서만 두고 풀이는 이 앱이 새로 씀 |

참고한 사이트의 문장(81수리 해설, 토정비결 풀이, 사주 해설 등)은 옮기지 않았다. 대조로 확인한 사실(길흉 분류, 계산 규칙, 숫자표)만 쓰고
설명은 새로 썼다.

---

## Unicode License v3

UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 1991-2026 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.

---

## rutopio/Korean-Name-Hanja-Charset (MIT)

```
Copyright (c) 2024 ChingRu (rutopio@github)

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

---

## libhangul 한자 사전 (BSD 3-Clause)

```
Copyright (c) 2005,2006 Choe Hwanjin
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the author nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

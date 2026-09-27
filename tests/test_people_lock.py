"""'내 사주 바로 보기' 잠금: PIN 으로 암호화하면 저장소에 생년월일이 평문으로 남지 않는다 (node 로 화면 코드 실행)."""
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "love_fortune" / "static" / "app.js"

SCRIPT = r"""
const fs=require('fs');
const src=fs.readFileSync(process.argv[1],'utf8');
const code=src.slice(src.indexOf('const PEOPLE_KEY'),src.indexOf('function renderPeople(){'));
const store={};
globalThis.window=globalThis;globalThis.S={};
globalThis.localStorage={getItem:k=>k in store?store[k]:null,setItem:(k,v)=>{store[k]=String(v);},removeItem:k=>{delete store[k];}};
const test=new Function(code+`
return (async()=>{
  const out=[];
  peopleSave('나',{birth:'1990-05-05',birth_time:'14:30',sex:'female',city:'서울'});
  out.push(Object.values(STORE).join('').includes('1990'));            // 잠그기 전엔 평문
  const blob=await sealPeople(people(),'123456');
  localStorage.setItem(LOCK_KEY,JSON.stringify(blob));localStorage.removeItem(PEOPLE_KEY);
  out.push(!Object.values(STORE).join('').includes('1990'));           // 잠근 뒤엔 평문 없음
  out.push(people().length===0);                                       // PIN 없이 목록 안 보임
  let wrong=false;try{await openPeople(blob,'000000');}catch(_){wrong=true;}
  out.push(wrong);                                                     // 틀린 PIN 은 못 연다
  const l=await openPeople(blob,'123456');
  out.push(l[0].q.birth==='1990-05-05');
  S.pin='123456';S.pcache=l;
  peopleSave('엄마',{birth:'1965-01-02',sex:'female'});
  await new Promise(r=>setTimeout(r,1500));
  out.push(!Object.values(STORE).join('').includes('1965'));           // 연 상태에서 추가해도 암호화돼 저장
  const l2=await openPeople(lockBlob(),'123456');
  out.push(l2.length===2&&l2[0].nick==='엄마');
  return out;
})();`.replace(/STORE/g,'__store'));
globalThis.__store=store;
test().then(o=>{console.log(JSON.stringify(o));}).catch(e=>{console.log('ERR '+e);});
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node 가 없으면 건너뜀")
def test_people_lock_roundtrip():
    r = subprocess.run(["node", "-e", SCRIPT, str(APP)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.stdout.strip() == "[true,true,true,true,true,true,true]", r.stdout + r.stderr


def test_people_list_hides_birth():
    js = APP.read_text(encoding="utf-8")
    body = js[js.index("function renderPeople(){"):js.index("async function pinUnlock")]
    assert "personLine" not in js and "q.birth" not in body      # 목록 버튼에 생년월일을 그리지 않는다

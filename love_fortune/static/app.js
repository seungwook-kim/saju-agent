// 종합 사주 · 앱형 챕터 화면
// 흐름: 입력 → /api/v2/report (사실표·챕터 목록·계산 풀이) → 탭을 열면 부품과 계산 풀이를 바로 그리고,
// AI 풀이(/api/v2/chapter)가 도착하면 그 챕터를 바꿔 끼운다. 서버는 입력 직후부터 AI 풀이를 미리 만든다.
'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const pad=n=>String(n).padStart(2,'0');

const TAB_ORDER=['today','love','career','money','life'];
const TAB_NAME={today:'총운',love:'연애',career:'직장',money:'금전',life:'평생'};
const EL_STEM={갑:'목',을:'목',병:'화',정:'화',무:'토',기:'토',경:'금',신:'금',임:'수',계:'수'};
const EL_BRANCH={자:'수',축:'토',인:'목',묘:'목',진:'토',사:'화',오:'화',미:'토',신:'금',유:'금',술:'토',해:'수'};
const TAG_CLASS={'밀고 나갈 때':'t4','좋은 흐름':'t2','무난한 흐름':'','다듬을 때':'t-3','조심할 때':'t-9'};

const S={token:'',facts:null,outline:null,rules:{},ai:false,tab:'today',
  chapters:{},chat:[],queue:[],running:0,inflight:new Set()};

async function postJSON(url,obj){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});
  if(!r.ok){
    let m='서버 응답 '+r.status;
    try{const j=await r.json();if(j.error) m=j.error;}catch(_){}
    throw new Error(m);
  }
  return r.json();
}

// ---------------- 입력 → 결과

$('fMain').addEventListener('submit',async e=>{
  e.preventDefault();
  const form=e.target,btn=form.querySelector('.go');
  const q={};new FormData(form).forEach((v,k)=>{q[k]=v;});
  if(!q.birth){$('homeErr').innerHTML='<div class="err">생년월일을 골라 줘.</div>';return;}
  btn.disabled=true;btn.textContent='계산하는 중...';$('homeErr').innerHTML='';
  try{
    const j=await postJSON('/api/v2/report',q);
    Object.assign(S,{token:j.token,facts:j.facts,outline:j.outline,rules:j.rules||{},ai:j.ai,
      chapters:{},chat:[],queue:[],inflight:new Set(),tab:'today'});
    showResult();
  }catch(err){
    $('homeErr').innerHTML='<div class="err">'+esc(err.message)+'</div>';
  }finally{btn.disabled=false;btn.textContent='내 사주 펼쳐 보기';}
});
$('btnBack').addEventListener('click',()=>{
  S.queue=[];
  $('result').classList.remove('on');$('home').classList.add('on');
  document.body.dataset.theme='rose';window.scrollTo(0,0);
});

function showResult(){
  $('home').classList.remove('on');$('result').classList.add('on');
  $('tabs').innerHTML=TAB_ORDER.map(t=>'<button class="tab" type="button" data-tab="'+t+'">'+TAB_NAME[t]+'</button>').join('');
  openTab('today');
}
$('tabs').addEventListener('click',e=>{
  const b=e.target.closest('[data-tab]');if(b) openTab(b.dataset.tab);
});

function openTab(tab){
  S.tab=tab;S.queue=[];
  const o=S.outline[tab],f=S.facts;
  document.body.dataset.theme=o.theme;
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.tab===tab));
  const chips=['일주 '+f.natal.day_pillar,f.meta.age+'세',f.meta.sex,'오늘 '+f.meta.target];
  if(!f.meta.hour_known) chips.push('시간 모름: 시주 제외');
  let h='<div class="tab-hero"><div class="hero-title">'+esc(o.title)+' <span class="hand">'+esc(o.hand)+'</span></div>'+
    '<p class="hero-sub">'+esc(o.sub)+'</p><div class="meta-chips">'+
    chips.map((c,i)=>'<span class="chip'+(i===0?' a':'')+'">'+esc(c)+'</span>').join('')+'</div></div>';
  o.chapters.forEach((c,i)=>{
    h+='<section class="chapter" id="ch-'+c.id+'">'+
      '<div class="ch-label">CHAPTER · '+pad(i+1)+'</div>'+
      '<div class="ch-head"><div class="ch-emoji" aria-hidden="true">'+c.emoji+'</div><div class="ch-title">'+esc(c.title)+'</div></div>'+
      c.widgets.map(w=>widget(w)).join('')+
      '<div class="ch-body" data-body="'+c.id+'"></div></section>';
  });
  h+=chatCard();
  $('page').innerHTML=h;
  window.scrollTo(0,0);
  animate($('page'));
  o.chapters.forEach(c=>{
    const key=tab+'/'+c.id,ai=S.chapters[key];
    const rule=(S.rules[tab]||{})[c.id];
    if(ai) fillChapter(tab,c.id,ai,false);
    else if(rule) fillChapter(tab,c.id,rule,S.ai);
    else $('page').querySelector('[data-body="'+c.id+'"]').innerHTML=skeleton();
    if(!ai&&S.ai&&!S.inflight.has(key)) S.queue.push(c.id);
  });
  pump();
}

// ---------------- 챕터 풀이
// 계산 풀이를 먼저 보여 주고, AI 풀이는 지금 탭의 위쪽 챕터부터 셋씩 받아 바꿔 끼운다.

function skeleton(){
  return '<div class="skel w8"></div><div class="skel"></div><div class="skel w6"></div>';
}
function pump(){
  const tab=S.tab;
  while(S.running<3&&S.queue.length){
    const ch=S.queue.shift(),key=tab+'/'+ch;S.running++;S.inflight.add(key);
    postJSON('/api/v2/chapter',{token:S.token,tab,chapter:ch})
      .then(body=>{
        if(body.source==='ai') S.chapters[key]=body;
        if(S.tab===tab) fillChapter(tab,ch,body,false);
      })
      .catch(()=>{                 // AI 풀이를 못 받아도 계산 풀이는 그대로 둔다
        const rule=(S.rules[tab]||{})[ch];
        if(rule&&S.tab===tab) fillChapter(tab,ch,rule,false);
      })
      .finally(()=>{S.running--;S.inflight.delete(key);pump();});
  }
}
function fillChapter(tab,ch,b,pending){
  const el=document.querySelector('[data-body="'+ch+'"]');
  if(!el) return;
  const swap=el.dataset.src==='rule'&&b.source==='ai';
  let h='';
  if(b.headline) h+='<div class="headline">'+esc(b.headline)+'</div>';
  if(b.lead) h+='<p class="lead">'+esc(b.lead)+'</p>';
  (b.blocks||[]).forEach(x=>{h+=block(x);});
  if(b.closing) h+='<div class="closing">'+esc(b.closing)+'</div>';
  h+='<div class="src">'+(b.source==='ai'?'계산 결과를 근거로 쓴 AI 풀이':
    '계산 결과로 쓴 기본 풀이'+(pending?' · <span class="pending">AI가 더 자세한 풀이를 쓰는 중</span>':''))+'</div>';
  el.innerHTML=h;
  el.dataset.src=b.source;
  if(swap){el.style.animation='none';void el.offsetWidth;el.style.animation='rise .5s var(--ease)';}
}
function block(x){
  const t=x.title?'<h4>'+esc(x.title)+'</h4>':'';
  switch(x.type){
    case 'text': return '<div class="blk">'+t+'<p>'+esc(x.body)+'</p></div>';
    case 'quote': return '<div class="blk quote"><p>'+esc(x.body)+'</p></div>';
    case 'callout': return '<div class="blk callout">'+esc(x.body)+'</div>';
    case 'checklist': return '<div class="blk checklist">'+t+'<ul>'+x.items.map(i=>'<li>'+esc(i)+'</li>').join('')+'</ul></div>';
    case 'steps': return '<div class="blk">'+t+'<div class="steps">'+x.items.map((i,n)=>
      '<div class="step"><div class="n">STEP '+(n+1)+'</div><b>'+esc(i.title)+'</b><p>'+esc(i.body)+'</p></div>').join('')+'</div></div>';
    case 'cards': return '<div class="blk">'+t+'<div class="cards">'+x.items.map(i=>
      '<div class="c"><b>'+esc(i.title)+'</b><p>'+esc(i.body)+'</p></div>').join('')+'</div></div>';
  }
  return '';
}

// ---------------- 화면 부품 (계산값으로 바로 그림)

function widget(w){
  const [name,arg]=w.split(':');
  const f=S.facts;
  switch(name){
    case 'wonguk': return wonguk(f.natal);
    case 'gauge': return gauge(f.today);
    case 'systems': return systems(f.today);
    case 'almanac': return almanac(f.today);
    case 'animals': return animals(f.love.animals);
    case 'calendar': return calendar(f[arg].months,arg);
    case 'years': return years(f[arg].years,arg);
    case 'decades': return decades(f.life,f.meta.age);
  }
  return '';
}
function card(inner,title){return '<div class="card">'+(title?'<h4 style="margin:0 0 .6rem">'+esc(title)+'</h4>':'')+inner+'</div>';}

function wonguk(n){
  const order=['hour','day','month','year'];
  const cols=order.map(k=>n.pillars.find(p=>p.key===k)||null);
  const lab={hour:'시주',day:'일주',month:'월주',year:'년주'};
  let h='<div class="wonguk"><div></div>'+order.map(k=>'<div class="h">'+lab[k]+'</div>').join('');
  const row=(label,fn)=>{
    h+='<div class="rl">'+label+'</div>'+cols.map((p,i)=>p?'<div class="cell'+(order[i]==='day'?' me':'')+'">'+fn(p)+'</div>':'<div class="cell"><span class="sm">모름</span></div>').join('');
  };
  row('십신',p=>'<span class="sm">'+esc(p.stem_god)+'</span>');
  row('천간',p=>'<span class="big el-'+EL_STEM[p.stem]+'">'+esc(p.stem)+'</span><div class="sm">'+EL_STEM[p.stem]+'</div>');
  row('지지',p=>'<span class="big el-'+EL_BRANCH[p.branch]+'">'+esc(p.branch)+'</span><div class="sm">'+EL_BRANCH[p.branch]+'</div>');
  row('십신',p=>'<span class="sm">'+esc(p.branch_god)+'</span>');
  row('지장간',p=>'<span class="sm">'+p.hidden.map(esc).join(' ')+'</span>');
  row('12운성',p=>'<span class="sm">'+esc(p.stage)+'</span>');
  h+='</div>';
  const total=Object.values(n.elements).reduce((a,b)=>a+b,0)||1;
  h+='<div class="elbars">'+Object.entries(n.elements).map(([e,v])=>
    '<div class="elbar"><b class="el-'+e+'">'+e+'</b><div class="t"><i data-w="'+Math.round(v/total*100)+'"></i></div><span>'+v+'</span></div>').join('')+'</div>';
  const chips=[['일간 '+n.ilgan,'a'],[n.strength,''],[n.geguk,''],['용신 '+n.yongsin,'']];
  h+='<div class="chips">'+chips.map(([c,k])=>'<span class="chip '+k+'">'+esc(c)+'</span>').join('')+'</div>';
  const tags=[].concat(n.guiin||[],n.sinsal||[],n.pairs||[]);
  if(tags.length) h+='<div class="chips">'+tags.map(c=>'<span class="chip">'+esc(c)+'</span>').join('')+'</div>';
  return card(h);
}
function gauge(t){
  const s=t.scores;
  const bars=[['연애',s.love],['직장',s.career],['금전',s.money]];
  return card('<div class="gauge"><div class="ring" style="--v:'+s.total+'"><span>'+s.total+'</span></div>'+
    '<div><div style="font-weight:800;margin-bottom:.4rem">'+esc(t.heads.total)+'</div><div class="bars">'+
    bars.map(([k,v])=>'<div class="bar"><span>'+k+'</span><div class="t"><i data-w="'+v+'"></i></div><b>'+v+'</b></div>').join('')+
    '</div></div></div><p style="margin:.8rem 0 0">'+esc(t.agreement)+' '+esc(t.focus)+'</p>');
}
function systems(t){
  const cls={좋음:'good',보통:'mid',조심:'bad',나쁨:'bad'};
  return t.systems.map(x=>'<div class="sys"><div class="sys-h">'+esc(x.name)+
    '<span class="sig '+(cls[x.signal]||'mid')+'">'+esc(x.signal)+'</span></div><ul>'+
    x.lines.map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul></div>').join('');
}
function almanac(t){
  return card('<ul style="margin:0;padding-left:1.1rem">'+t.almanac.map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul>','오늘 달력 (택일)');
}
function animals(a){
  const g=(title,rows)=>'<div class="g"><h5>'+title+'</h5><div class="row">'+(rows.length?rows.map(r=>
    '<span class="a" title="'+esc(r.why.join(', '))+'">'+esc(r.animal)+'띠</span>').join(''):'<span class="sm">없음</span>')+'</div>'+
    (rows.some(r=>r.why.length)?'<p style="font-size:.8rem;color:var(--muted);margin:.4rem 0 0">'+rows.filter(r=>r.why.length).map(r=>esc(r.animal+': '+r.why.join(', '))).join(' · ')+'</p>':'')+'</div>';
  return '<div class="animals">'+g('내 띠('+esc(a.me)+')와 잘 맞는 띠',a.good)+g('무난한 띠',a.mid)+g('조심할 띠',a.bad)+'</div>';
}
function calendar(rows,dom){
  const id='cal-'+dom;
  return card('<div class="cal" data-cal-box="'+id+'">'+rows.map((r,i)=>
    '<button type="button" class="'+(TAG_CLASS[r.tag]||'')+'" data-i="'+i+'" data-dom="'+dom+'">'+
    '<b>'+esc(r.label)+'</b><small>'+esc(r.ym.slice(0,4))+' · '+esc(r.ganzhi)+'</small><div class="tag">'+esc(r.tag)+'</div></button>').join('')+
    '</div><div class="cal-why" id="'+id+'"></div>','앞으로 12개월 (눌러서 이유 보기)');
}
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-dom][data-i]');if(!b) return;
  const r=S.facts[b.dataset.dom].months[+b.dataset.i];
  const box=$('cal-'+b.dataset.dom);
  box.innerHTML='<b>'+esc(r.ym.slice(0,4)+'년 '+r.label)+' '+esc(r.ganzhi)+' ('+esc(r.god)+')</b>: '+esc(r.tag)+
    (r.why.length?'<br>'+r.why.map(esc).join(', '):'<br>특별히 걸리는 신호가 없는 달이야.');
  box.classList.add('on');
});
function years(rows,dom){
  return card('<div class="years">'+rows.map(r=>'<div class="y"><b>'+r.year+'</b><div class="sm">'+esc(r.ganzhi)+'년</div>'+
    '<div class="tag">'+esc(r.tag)+'</div><p>'+esc(r.why.join(', ')||'잔잔한 해')+'</p></div>').join('')+'</div>',
    {love:'연애',career:'직장',money:'금전'}[dom]+' · 앞으로 3년');
}
function decades(life,age){
  return '<div class="timeline">'+life.decades.map(d=>{
    const now=age>=d.range[0]&&age<=d.range[1];
    return '<div class="row"'+(now?' style="outline:2px solid var(--accent2)"':'')+'><b>'+d.range[0]+'~'+d.range[1]+'세'+(now?' · 지금':'')+'</b><br>'+
      esc(d.parts[1]||d.parts[0]||'')+'</div>';
  }).join('')+'</div>';
}

// ---------------- 애니메이션

function animate(root){
  setTimeout(()=>{
    root.querySelectorAll('[data-w]').forEach(i=>{i.style.width=i.dataset.w+'%';});
  },40);
}

// ---------------- 상담 채팅

function chatCard(){
  return '<section class="chapter"><div class="ch-label">ASK</div><div class="ch-head"><div class="ch-emoji" aria-hidden="true">💬</div>'+
    '<div class="ch-title">AI 상담에게 더 묻기</div></div><div class="card chat"><div class="msgs" id="chatMsgs">'+
    S.chat.map(m=>'<div class="msg '+(m.role==='user'?'me':'bot')+'">'+esc(m.content)+'</div>').join('')+'</div>'+
    '<form class="chatrow" id="chatForm"><input id="chatIn" maxlength="200" placeholder="예: 이번 달 연애운은 왜 이래?">'+
    '<button type="submit">전송</button></form>'+
    '<p class="fine" style="margin-top:8px">생년월일은 보내지 않고 계산 결과 요약만 보내. 단정적인 예언은 하지 않아.</p></div></section>';
}
document.addEventListener('submit',async e=>{
  if(e.target.id!=='chatForm') return;
  e.preventDefault();
  const input=$('chatIn'),box=$('chatMsgs'),msg=input.value.trim();
  if(!msg) return;
  input.value='';
  box.insertAdjacentHTML('beforeend','<div class="msg me">'+esc(msg)+'</div><div class="msg bot" data-tmp="1">생각 중...</div>');
  box.scrollTop=box.scrollHeight;
  try{
    const j=await postJSON('/api/chat',{token:S.token,message:msg,history:S.chat.slice(-10)});
    box.querySelector('[data-tmp]').outerHTML='<div class="msg bot">'+esc(j.reply)+'<small>'+esc(j.model||'')+'</small></div>';
    S.chat.push({role:'user',content:msg},{role:'assistant',content:j.reply});
  }catch(err){
    box.querySelector('[data-tmp]').outerHTML='<div class="msg bot">'+esc(err.message)+'</div>';
  }
  box.scrollTop=box.scrollHeight;
});

// ---------------- 생년월일 캘린더 선택기
// 글자로 입력하지 않고 연대, 연도, 월, 일 순서로 눌러서 고른다.
// 음력은 그해 실제 달 목록(윤달 포함)과 그달 일수를 서버에서 받아 보여 준다.
const DP={form:null,name:'',cal:'solar',y:0,m:0,d:0,leap:false,step:'year',decade:1990,cache:{}};
const NOW=new Date(),THIS_Y=NOW.getFullYear(),MIN_Y=1900;
const WK=['일','월','화','수','목','금','토'];
function dpF(form,name){
  return {val:form.querySelector('input[name="'+name+'"]'),leap:form.querySelector('input[name="leap"]'),
    cal:form.querySelector('select[name="calendar"]'),btn:form.querySelector('[data-dp="'+name+'"]')};
}
function dpText(cal,v,leap,ym){
  const head=cal==='lunar'?'음력 ':'양력 ';
  if(!v&&ym){const p=ym.split('-').map(Number);return head+p[0]+'년 '+p[1]+'월 · 날짜를 다시 골라 줘';}
  if(!v) return '눌러서 선택';
  const p=v.split('-').map(Number);
  return head+p[0]+'년 '+(leap?'윤':'')+p[1]+'월 '+p[2]+'일';
}
function dpRefresh(form,name){
  const f=dpF(form,name);
  f.btn.textContent=dpText(f.cal.value,f.val.value,f.leap.value==='1',f.val.dataset.ym);
}
async function lunarMonths(y){
  if(!DP.cache[y]){
    const r=await fetch('/api/lunar-year?y='+y);
    if(!r.ok) throw new Error('음력 달력을 불러오지 못했어');
    DP.cache[y]=(await r.json()).months;
  }
  return DP.cache[y];
}
function dpOpen(form,name){
  const f=dpF(form,name);
  Object.assign(DP,{form,name,cal:f.cal.value,y:0,m:0,d:0,leap:false,step:'year'});
  const v=f.val.value||f.val.dataset.ym||'';
  if(v){
    const p=v.split('-').map(Number);
    DP.y=p[0];DP.m=p[1];DP.d=p[2]||0;DP.leap=f.leap.value==='1';
    if(!DP.d) DP.step='day';
  }
  DP.decade=Math.floor((DP.y||1990)/10)*10;
  $('dpCal').textContent=DP.cal==='lunar'?'음력':'양력';
  $('dp').classList.add('on');$('dpScrim').classList.add('on');
  dpRender();
}
function dpClose(){
  $('dp').classList.remove('on');$('dpScrim').classList.remove('on');
  const f=DP.form&&dpF(DP.form,DP.name);if(f) f.btn.focus();
}
function dpBtn(label,attrs,cls,sub){
  return '<button type="button" class="'+(cls||'')+'" '+attrs+'>'+esc(label)+(sub?'<small>'+esc(sub)+'</small>':'')+'</button>';
}
async function dpRender(){
  const c=[];
  c.push(dpBtn(DP.y?DP.y+'년':'연도','data-go="year"',DP.step==='year'?'on':''));
  c.push(dpBtn(DP.m?(DP.leap?'윤':'')+DP.m+'월':'월','data-go="month"'+(DP.y?'':' disabled'),DP.step==='month'?'on':''));
  c.push(dpBtn(DP.d&&DP.step!=='year'&&DP.step!=='month'?DP.d+'일':'일','data-go="day"'+(DP.m?'':' disabled'),DP.step==='day'?'on':''));
  $('dpCrumbs').innerHTML=c.join('');
  let h='';
  if(DP.step==='year'){
    h+='<div class="dp-sub">연대를 먼저 골라 줘</div><div class="dp-grid dp-g4">';
    for(let dc=MIN_Y;dc<=THIS_Y;dc+=10) h+=dpBtn(dc+'년대','data-dec="'+dc+'"',dc===DP.decade?'on':'');
    h+='</div><div class="dp-sub">'+DP.decade+'년대에서 태어난 해</div><div class="dp-grid dp-g5">';
    for(let y=DP.decade;y<DP.decade+10;y++) h+=dpBtn(y,'data-y="'+y+'"'+(y>THIS_Y?' disabled':''),y===DP.y?'on':'');
    h+='</div>';
  }else if(DP.step==='month'){
    h+='<div class="dp-sub">'+DP.y+'년 '+(DP.cal==='lunar'?'음력 ':'')+'태어난 달</div><div class="dp-grid dp-g4">';
    if(DP.cal==='lunar'){
      let ms;
      try{ms=await lunarMonths(DP.y);}catch(e){$('dpBody').innerHTML='<div class="err">'+esc(e.message)+'</div>';return;}
      ms.forEach(x=>{h+=dpBtn((x.leap?'윤':'')+x.m+'월','data-m="'+x.m+'" data-leap="'+(x.leap?1:0)+'"',
        (x.leap?'leap ':'')+(x.m===DP.m&&x.leap===DP.leap?'on':''),x.days+'일');});
    }else{
      for(let m=1;m<=12;m++){
        const future=DP.y===THIS_Y&&m>NOW.getMonth()+1;
        h+=dpBtn(m+'월','data-m="'+m+'" data-leap="0"'+(future?' disabled':''),m===DP.m?'on':'');
      }
    }
    h+='</div>';
  }else{
    h+='<div class="dp-sub">'+DP.y+'년 '+(DP.cal==='lunar'?'음력 ':'')+(DP.leap?'윤':'')+DP.m+'월에서 태어난 날</div>';
    if(DP.cal==='lunar'){
      const ms=await lunarMonths(DP.y);
      const mo=ms.find(x=>x.m===DP.m&&x.leap===DP.leap);
      const n=mo?mo.days:30;
      h+='<div class="dp-grid dp-g7">';
      for(let d=1;d<=n;d++) h+=dpBtn(d,'data-d="'+d+'"',d===DP.d?'on':'');
      h+='</div><div class="dp-sub">이 달은 '+n+'일까지 있어. 음력 날짜라 요일은 표시하지 않아.</div>';
    }else{
      const first=new Date(DP.y,DP.m-1,1).getDay(),n=new Date(DP.y,DP.m,0).getDate();
      h+='<div class="dp-grid dp-g7">'+WK.map((w,i)=>'<div class="dp-wk'+(i===0?' sun':'')+'">'+w+'</div>').join('');
      for(let i=0;i<first;i++) h+='<div></div>';
      for(let d=1;d<=n;d++){
        const future=new Date(DP.y,DP.m-1,d)>NOW;
        const sun=(first+d-1)%7===0;
        h+=dpBtn(d,'data-d="'+d+'"'+(future?' disabled':''),(sun?'sun ':'')+(d===DP.d?'on':''));
      }
      h+='</div>';
    }
  }
  $('dpBody').innerHTML=h;
  const on=$('dpBody').querySelector('.dp-g5 .on, .dp-g7 .on')||$('dpBody').querySelector('button:not(:disabled)');
  if(on) on.focus({preventScroll:true});
}
$('dp').addEventListener('click',e=>{
  const b=e.target.closest('button');
  if(!b||b.disabled||b.id==='dpClose') return;
  if(b.dataset.go){DP.step=b.dataset.go;dpRender();return;}
  if(b.dataset.dec){DP.decade=+b.dataset.dec;dpRender();return;}
  if(b.dataset.y){DP.y=+b.dataset.y;DP.m=0;DP.d=0;DP.leap=false;DP.step='month';dpRender();return;}
  if(b.dataset.m){DP.m=+b.dataset.m;DP.leap=b.dataset.leap==='1';DP.d=0;DP.step='day';dpRender();return;}
  if(b.dataset.d){
    DP.d=+b.dataset.d;
    const f=dpF(DP.form,DP.name);
    f.val.value=DP.y+'-'+pad(DP.m)+'-'+pad(DP.d);
    delete f.val.dataset.ym;
    f.leap.value=DP.leap?'1':'';
    dpRefresh(DP.form,DP.name);
    dpClose();
  }
});
$('dpClose').addEventListener('click',dpClose);
$('dpScrim').addEventListener('click',dpClose);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('dp').classList.contains('on')) dpClose();});
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-dp]');
  if(b) dpOpen(b.form,b.dataset.dp);
});
// 양력과 음력을 바꿔도 고른 연·월·일 숫자는 그대로 두고 해석만 바꾼다.
// 바꾼 달력에 그 날이 없으면 연·월은 두고 날짜만 다시 고르게 캘린더를 연다.
async function dayExists(cal,y,m,d){
  if(cal==='lunar'){
    try{const mo=(await lunarMonths(y)).find(x=>x.m===m&&!x.leap);return !!mo&&d<=mo.days;}
    catch(e){return true;}
  }
  const dt=new Date(y,m-1,d);
  return dt.getMonth()===m-1&&dt<=NOW;
}
document.querySelectorAll('select[data-cal]').forEach(sel=>{
  sel.addEventListener('change',async()=>{
    const form=sel.form,name=sel.dataset.cal,f=dpF(form,name);
    f.leap.value='';
    const v=f.val.value;
    if(v){
      const p=v.split('-').map(Number);
      if(!(await dayExists(sel.value,p[0],p[1],p[2]))){
        f.val.value='';f.val.dataset.ym=p[0]+'-'+pad(p[1]);
        dpRefresh(form,name);dpOpen(form,name);return;
      }
    }
    dpRefresh(form,name);
  });
});
document.querySelector('input[name="unknown_time"]').addEventListener('change',e=>{
  document.querySelector('input[name="birth_time"]').disabled=e.target.checked;
});
document.querySelectorAll('[data-dp]').forEach(b=>dpRefresh(b.form,b.dataset.dp));

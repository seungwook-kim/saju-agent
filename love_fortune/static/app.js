// 종합 사주 · 앱형 챕터 화면
// 흐름: 입력 → /api/v2/report (사실표·챕터 목록·계산 풀이) → 탭을 열면 부품과 계산 풀이를 바로 그리고,
// AI 풀이(/api/v2/chapter)가 도착하면 그 챕터를 바꿔 끼운다. 서버는 입력 직후부터 AI 풀이를 미리 만든다.
'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const pad=n=>String(n).padStart(2,'0');

const TAB_ORDER=['today','love','career','money','newyear','life','past','when','match','pick','name'];
const TAB_NAME={today:'총운',love:'연애',career:'직장',money:'금전',newyear:'신년',life:'평생',past:'되짚기',when:'시간 찾기',match:'궁합',pick:'길일',name:'이름'};
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
  const remember=q.remember==='1',nick=String(q.nick||'').trim().slice(0,12)||'나';
  delete q.remember;delete q.nick;                   // 기억용 칸은 서버에 보내지 않는다
  if(!q.birth){$('homeErr').innerHTML='<div class="err">생년월일을 골라 줘.</div>';return;}
  btn.disabled=true;btn.textContent='계산하는 중...';$('homeErr').innerHTML='';
  try{
    const j=await postJSON('/api/v2/report',q);
    if(remember){peopleSave(nick,q);form.querySelector('[name="remember"]').checked=false;toggleNick();renderPeople();}
    S.person=q;                         // 궁합·길일에 다시 쓴다 (브라우저 메모리에만)
    S.shareId=null;S.pastAns={};
    Object.assign(S,{token:j.token,facts:j.facts,outline:j.outline,rules:j.rules||{},ai:j.ai,chatOn:!!j.chat,
      chapters:{},chat:[],queue:[],inflight:new Set(),tab:'today'});
    showResult();
  }catch(err){
    $('homeErr').innerHTML='<div class="err">'+esc(err.message)+'</div>';
  }finally{btn.disabled=false;btn.textContent='내 사주 펼쳐 보기';}
});
$('btnBack').addEventListener('click',()=>{
  S.queue=[];renderPeople();closeAsk();
  $('result').classList.remove('on');$('home').classList.add('on');
  document.body.dataset.theme='rose';window.scrollTo(0,0);
});

function showResult(){
  $('askFab').hidden=!S.chatOn;if(!S.chatOn) closeAsk();     // 공개 서버에서는 채팅을 잠시 막아 둔다
  loadGloss().then(()=>{if(S.tab&&S.outline[S.tab]) openTab(S.tab);});
  $('home').classList.remove('on');$('result').classList.add('on');
  $('tabs').innerHTML=TAB_ORDER.map(t=>'<button class="tab" type="button" data-tab="'+t+'">'+TAB_NAME[t]+'</button>').join('');
  tabEdges();
  openTab('today');
}
// 탭 줄은 가로로 넘긴다. 예전엔 숨은 가로 스크롤이라 PC에서 뒤쪽 탭에 닿을 수 없었다.
// 그래서 스크롤바를 보이게 두고, 좌우 화살표·마우스 휠·끌기로도 넘기고, 고른 탭은 가운데로 옮긴다.
function tabEdges(){
  const t=$('tabs');if(!t) return;
  $('tabL').classList.toggle('on',t.scrollLeft>4);
  $('tabR').classList.toggle('on',t.scrollLeft+t.clientWidth<t.scrollWidth-4);
}
function centerTab(){
  const t=$('tabs'),b=t&&t.querySelector('.tab.on');if(!b) return;
  t.scrollTo({left:b.offsetLeft-t.clientWidth/2+b.offsetWidth/2,behavior:'smooth'});
  setTimeout(tabEdges,450);            // 부드러운 스크롤이 끝난 뒤 화살표를 다시 맞춘다
}
$('tabs').addEventListener('scroll',tabEdges,{passive:true});
$('tabs').addEventListener('scrollend',tabEdges);
window.addEventListener('resize',tabEdges);
$('tabL').addEventListener('click',()=>$('tabs').scrollBy({left:-$('tabs').clientWidth*0.7,behavior:'smooth'}));
$('tabR').addEventListener('click',()=>$('tabs').scrollBy({left:$('tabs').clientWidth*0.7,behavior:'smooth'}));
$('tabs').addEventListener('wheel',e=>{            // 세로 휠을 가로 이동으로
  const t=$('tabs');
  if(t.scrollWidth<=t.clientWidth||Math.abs(e.deltaX)>Math.abs(e.deltaY)) return;
  t.scrollLeft+=e.deltaY;e.preventDefault();
},{passive:false});
(function dragScroll(){                               // 마우스로 끌어서 넘기기 (조금 움직이면 클릭은 막는다)
  const t=$('tabs');let x0=0,s0=0,down=false,moved=false;
  t.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse') return;down=true;moved=false;x0=e.clientX;s0=t.scrollLeft;});
  window.addEventListener('pointermove',e=>{if(!down) return;const dx=e.clientX-x0;if(Math.abs(dx)>5){moved=true;t.scrollLeft=s0-dx;}});
  window.addEventListener('pointerup',()=>{down=false;});
  t.addEventListener('click',e=>{if(moved){e.stopPropagation();e.preventDefault();moved=false;}},true);
})();
$('tabs').addEventListener('click',e=>{
  const b=e.target.closest('[data-tab]');if(b) openTab(b.dataset.tab);
});

function openTab(tab){
  if(TOOLS[tab]) return openTool(tab);
  S.tab=tab;S.queue=[];
  const o=S.outline[tab],f=S.facts;
  document.body.dataset.theme=o.theme;
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.tab===tab));
  centerTab();
  const chips=['일주 '+f.natal.day_pillar,'만 '+f.meta.age+'세',f.meta.sex,'오늘 '+f.meta.target];
  if(!f.meta.hour_known) chips.push('시간 모름: 시주 제외');
  const bd=(f.natal.boundary||{}).items||[];
  let h='<div class="tab-hero">'+heroArt(tab)+'<div class="hero-title">'+esc(o.title)+' <span class="hand">'+esc(o.hand)+'</span></div>'+
    '<p class="hero-sub">'+esc(o.sub)+'</p><div class="meta-chips">'+
    chips.map((c,i)=>'<span class="chip'+(i===0?' a':'')+'">'+esc(c)+'</span>').join('')+
    (bd.length?'<button type="button" class="chip warn" id="bdChip">경계 출생: 기둥이 바뀔 수 있어</button>':'')+'</div></div>'+
    (bd.length?'<div class="card bd-card" id="bdCard" hidden>'+bd.map(i=>'<p>'+esc(i.text)+'</p>').join('')+
      '<p class="fine">'+esc(f.natal.boundary.note||'')+'</p></div>':'');
  o.chapters.forEach((c,i)=>{
    h+='<section class="chapter" id="ch-'+c.id+'">'+
      '<div class="ch-label">CHAPTER · '+pad(i+1)+'</div>'+
      '<div class="ch-head"><div class="ch-emoji" aria-hidden="true">'+c.emoji+'</div><div class="ch-title">'+esc(c.title)+'</div></div>'+
      c.widgets.map(w=>widget(w)).join('')+
      '<div class="ch-body" data-body="'+c.id+'"></div>'+
      (c.pick&&c.pick.length?'<details class="evid" data-pick="'+esc(JSON.stringify(c.pick))+'"><summary>근거 보기: 이 챕터가 본 계산값</summary><div class="evid-body"></div></details>':'')+
      '</section>';
  });
  if(tab==='love') h+=sokSection();
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
  let h='';const used=new Set();
  if(b.headline) h+='<div class="headline">'+esc(b.headline)+'</div>';
  if(b.lead) h+='<p class="lead">'+linkTerms(esc(b.lead),used)+'</p>';
  (b.blocks||[]).forEach(x=>{h+=block(x,used);});
  if(b.closing) h+='<div class="closing">'+esc(b.closing)+'</div>';
  h+='<div class="src">'+(b.source==='ai'?'계산 결과를 근거로 쓴 AI 풀이':
    '계산 결과로 쓴 기본 풀이'+(pending?' · <span class="pending">AI가 더 자세한 풀이를 쓰는 중</span>':''))+'</div>';
  el.innerHTML=h;
  el.dataset.src=b.source;
  if(swap){el.style.animation='none';void el.offsetWidth;el.style.animation='rise .5s var(--ease)';}
}
function block(x,used){
  used=used||new Set();
  const L=s=>linkTerms(esc(s),used);
  const t=x.title?'<h4>'+esc(x.title)+'</h4>':'';
  switch(x.type){
    case 'text': return '<div class="blk">'+t+'<p>'+L(x.body)+'</p></div>';
    case 'quote': return '<div class="blk quote"><p>'+esc(x.body)+'</p></div>';
    case 'callout': return '<div class="blk callout">'+L(x.body)+'</div>';
    case 'checklist': return '<div class="blk checklist">'+t+'<ul>'+x.items.map(i=>'<li>'+L(i)+'</li>').join('')+'</ul></div>';
    case 'steps': return '<div class="blk">'+t+'<div class="steps">'+x.items.map((i,n)=>
      '<div class="step"><div class="n">STEP '+(n+1)+'</div><b>'+esc(i.title)+'</b><p>'+L(i.body)+'</p></div>').join('')+'</div></div>';
    case 'cards': return '<div class="blk">'+t+'<div class="cards">'+x.items.map(i=>
      '<div class="c"><b>'+esc(i.title)+'</b><p>'+L(i.body)+'</p></div>').join('')+'</div></div>';
  }
  return '';
}

// ---------------- 화면 부품 (계산값으로 바로 그림)

function widget(w){
  const [name,arg]=w.split(':');
  const f=S.facts;
  switch(name){
    case 'wonguk': return wonguk(f.natal);
    case 'gauge': return arg==='today'?gauge(f.today):dgauge(f.today.domains[arg],arg);
    case 'dsys': return dsys(f.today.domains[arg],arg);
    case 'systems': return systems(f.today);
    case 'almanac': return almanac(f.today);
    case 'animals': return animals(f.love.animals);
    case 'calendar': return calendar(f[arg].months,arg)+'<button type="button" class="ghost ics-btn" data-ics="'+arg+'">📅 좋은 달·조심할 달을 캘린더 앱에 넣기</button><div id="ics-'+arg+'"></div>';
    case 'consensus': return consensus((f.insights||{}).consensus,arg);
    case 'years': return years(f[arg].years,arg);
    case 'decades': return decades(f.life,f.meta.age);
    case 'dayunrel': return dayunRel(f.life.dayun_rel||[]);
    case 'mingpan': return mingpan(f.natal.ziwei,f.meta);
    case 'ny': return nyCard(f.newyear);
    case 'ilju': return iljuCard(f.natal.ilju);
    case 'nycal': return nyCal(f.newyear);
    case 'tojeong': return tjCard(f.newyear.tojeong);
    case 'wheel': return wheel(f.natal.astro.wheel);
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
  h+=ohaeng(n.elements);
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
    '</div></div></div><p class="fine" style="margin:.7rem 0 0">총운 = 연애·직장·금전 점수의 평균 + 오늘 공통 기운</p>'+
    '<p style="margin:.5rem 0 0">'+esc(t.agreement)+' '+esc(t.focus)+'</p>');
}
// 토정비결 괘 카드
function tjCard(t){
  const tone={good:['좋음','up'],mid:['엇갈림',''],care:['조심','down']}[t.tone];
  return '<div class="ilju"><div class="tj-num">'+t.gua+'</div><div class="ilju-t">'+esc(t.read)+'</div>'+
    '<div class="chips" style="justify-content:center"><span class="pill '+tone[1]+'">'+tone[0]+'</span></div>'+
    '<p style="margin:.6rem 0 0">'+esc(t.mean)+'</p></div>';
}
// 일주 카드
function iljuCard(c){
  return '<div class="ilju"><div class="ilju-big"><span class="el-'+EL_STEM[c.pillar[0]]+'">'+esc(c.pillar[0])+'</span>'+
    '<span class="el-'+EL_BRANCH[c.pillar[1]]+'">'+esc(c.pillar[1])+'</span></div>'+
    '<div class="ilju-t">'+esc(c.title)+'</div><div class="ilju-m">요즘 부르는 말: '+esc(c.modern)+'</div>'+
    '<div class="chips" style="justify-content:center">'+['십이운성 '+c.stage,'배우자 자리 '+c.spouse_god].concat(c.marks.map(m=>m.name)).map(x=>'<span class="chip a">'+esc(x)+'</span>').join('')+'</div></div>';
}
// 신년운세: 한 해 요약 카드와 열두 달 표
const NY_CLS={'밀고 나갈 때':'t4','좋은 흐름':'t2','무난한 흐름':'','다듬을 때':'t-3','조심할 때':'t-9'};
function nyCard(ny){
  const w={love:'연애',career:'일',money:'돈'};
  return card('<div style="text-align:center"><div style="font-size:2.2rem;font-weight:900;letter-spacing:-.03em">'+ny.year+
    ' <span class="accent">'+esc(ny.ganzhi)+'</span></div><p class="fine" style="margin:.2rem 0 .8rem">만 '+ny.age+'세의 한 해 · 나에게 '+esc(ny.god)+'</p></div>'+
    '<div class="cards">'+['love','career','money'].map(d=>'<div class="c"><b>'+w[d]+'</b><p><span class="pill '+
      (['밀고 나갈 때','좋은 흐름'].includes(ny.signals[d].tag)?'up':['다듬을 때','조심할 때'].includes(ny.signals[d].tag)?'down':'')+'">'+
      esc(ny.signals[d].tag)+'</span></p></div>').join('')+'</div>');
}
function nyCal(ny){
  const w={love:'연애',career:'일',money:'돈'};
  let h='<div class="nycal"><div></div>'+ny.months.love.map(r=>'<div class="nh">'+esc(r.label)+'</div>').join('');
  ['love','career','money'].forEach(d=>{
    h+='<div class="nr">'+w[d]+'</div>'+ny.months[d].map(r=>'<div class="nd '+(NY_CLS[r.tag]||'')+'" title="'+esc(r.label+' '+r.ganzhi+': '+r.tag+(r.why.length?' ('+r.why.join(', ')+')':''))+'"></div>').join('');
  });
  return card(h+'</div><div class="legend"><span class="sw t4"></span>밀고 나갈 때 <span class="sw t2"></span>좋은 흐름 '+
    '<span class="sw"></span>무난 <span class="sw t-3"></span>다듬을 때 <span class="sw t-9"></span>조심할 때 (칸을 길게 누르면 이유)</div>',ny.year+'년 열두 달');
}
// 연애·직장·금전 탭: 오늘 그 영역 점수와 세 체계가 더하고 뺀 신호
const DOM_WORD={love:'연애',career:'직장',money:'금전'};
function sign(p){return p>0?'+'+p:String(p);}
function dgauge(d,dom){
  return card('<div class="gauge"><div class="ring" style="--v:'+d.score+'"><span>'+d.score+'</span></div>'+
    '<div><div style="font-weight:800;margin-bottom:.5rem">'+esc(d.head)+'</div><div class="chips" style="margin:0">'+
    d.systems.map(s=>'<span class="chip'+(s.points>0?' a':'')+'">'+esc(s.name)+' '+sign(s.points)+'</span>').join('')+
    '</div><p class="fine" style="margin:.5rem 0 0">오늘 '+DOM_WORD[dom]+' 점수 · 칩은 체계별 가감 신호</p></div></div>');
}
function dsys(d,dom){
  const up=d.systems.filter(s=>s.points>0).length,dn=d.systems.filter(s=>s.points<0).length,n=d.systems.length;
  return '<div class="agree-line">세 체계 중 <b>'+up+'개</b>가 좋은 쪽, <b>'+dn+'개</b>가 조심 쪽, '+(n-up-dn)+'개는 보통이야.'+
    (up===n?' 다 같은 쪽이라 믿을 만한 신호야.':up&&dn?' 체계끼리 엇갈리는 날이야.':'')+'</div>'+d.systems.map(s=>{
    const cls=s.points>0?'good':s.points<0?'bad':'mid';
    const common=s.common||[];
    const lines=s.lines.length||common.length?s.lines:['오늘 '+DOM_WORD[dom]+'에 따로 걸리는 신호는 없어.'];
    return '<div class="sys"><div class="sys-h">'+esc(s.name)+'<span class="sig '+cls+'">'+DOM_WORD[dom]+' '+sign(s.points)+'</span></div><ul>'+
      lines.map(l=>'<li>'+esc(l)+'</li>').join('')+
      common.map(l=>'<li class="common"><span class="cm">모든 운 공통</span>'+esc(l)+'</li>').join('')+'</ul></div>';
  }).join('');
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

// 대운 x 원국: 대운마다 해·달·날·시 자리와 합(손잡음)·충(부딪침)·형·파·해
const REL_SHORT={'천간합':'간합','천간충':'간충','합':'합','삼합':'삼합','충':'충','형':'형','파':'파','해':'해'};
const REL_TONE={'천간합':'good','합':'good','삼합':'good','충':'hard','천간충':'hard','형':'mid','파':'mid','해':'mid'};
function dayunRel(rows){
  if(!rows.length) return '';
  const cols=[['year','해'],['month','달'],['day','날'],['hour','시']].filter(c=>rows[0].cells[c[0]]);
  const cell=ks=>ks&&ks.length?ks.map(k=>'<span class="rb '+REL_TONE[k]+'">'+REL_SHORT[k]+'</span>').join(''):'<span class="rb none">·</span>';
  return '<div class="drel"><table><thead><tr><th>나이</th><th>대운</th>'+cols.map(c=>'<th>'+c[1]+'</th>').join('')+'</tr></thead><tbody>'+
    rows.map(r=>'<tr'+(r.now?' class="now"':'')+'><td>'+r.from+'~'+r.to+(r.now?'<small>지금</small>':'')+'</td><td><b>'+esc(r.ganzhi)+'</b></td>'+
      cols.map(c=>'<td>'+cell(r.cells[c[0]])+'</td>').join('')+'</tr>').join('')+
    '</tbody></table><p class="fine">해·달·날·시는 태어난 해(집안·윗사람)·달(일터)·날(나와 배우자)·시(자녀·앞날) 자리야. '+
    '<span class="rb good">합</span>은 손잡음, <span class="rb hard">충</span>은 부딪침, <span class="rb mid">형·파·해</span>는 조임·틀어짐·서운함. 간합·간충은 하늘 글자끼리야.</p></div>';
}

// ---------------- 애니메이션

function animate(root){
  setTimeout(()=>{
    root.querySelectorAll('[data-w]').forEach(i=>{i.style.width=i.dataset.w+'%';});
  },40);
}

// ---------------- 상담 채팅

// 결과 화면 오른쪽 아래 버튼으로 여는 패널. 탭을 옮겨도 대화는 그대로 남는다.
const ASK_HINT='<div class="msg bot">지금 본 사주 계산 결과를 바탕으로 답해 줄게. 궁금한 걸 편하게 물어봐.</div>';
function renderChat(){
  $('chatMsgs').innerHTML=ASK_HINT+S.chat.map(m=>'<div class="msg '+(m.role==='user'?'me':'bot')+'">'+esc(m.content)+'</div>').join('');
}
function openAsk(){
  renderChat();
  $('askPanel').classList.add('on');$('askScrim').classList.add('on');
  $('askPanel').setAttribute('aria-hidden','false');$('askFab').setAttribute('aria-expanded','true');
  document.body.classList.add('ask-open');
  const box=$('chatMsgs');box.scrollTop=box.scrollHeight;
  if(!NARROW.matches) setTimeout(()=>$('chatIn').focus(),60);   // 폰은 열자마자 키보드가 올라와 대화를 가리니 자동 포커스 안 함
  fitAsk();
}
// 폰: 키보드가 올라오면 보이는 영역(visualViewport)에 맞춰 패널을 줄여 입력칸이 키보드 위에 오게 한다
const NARROW=matchMedia('(max-width:640px)');
function fitAsk(){
  const p=$('askPanel'),vv=window.visualViewport;
  if(!vv||!NARROW.matches||!p.classList.contains('on')){p.style.height='';p.style.bottom='';return;}
  const kb=Math.max(0,window.innerHeight-vv.height-vv.offsetTop);
  p.style.bottom=kb+'px';
  p.style.height=kb>0?Math.round(vv.height*0.92)+'px':'';
  const box=$('chatMsgs');box.scrollTop=box.scrollHeight;
}
if(window.visualViewport){visualViewport.addEventListener('resize',fitAsk);visualViewport.addEventListener('scroll',fitAsk);}
function closeAsk(){
  $('askPanel').classList.remove('on');$('askScrim').classList.remove('on');
  $('askPanel').setAttribute('aria-hidden','true');$('askFab').setAttribute('aria-expanded','false');
  document.body.classList.remove('ask-open');
  $('askPanel').style.height='';$('askPanel').style.bottom='';
}
$('askFab').addEventListener('click',()=>$('askPanel').classList.contains('on')?closeAsk():openAsk());
$('askClose').addEventListener('click',closeAsk);
$('askScrim').addEventListener('click',closeAsk);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('askPanel').classList.contains('on')) closeAsk();});
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
    if(typeof j.left==='number'&&j.left>=0) $('chatLeft').textContent='오늘 남은 질문 '+j.left+'번. ';
    S.chat.push({role:'user',content:msg},{role:'assistant',content:j.reply});
  }catch(err){
    box.querySelector('[data-tmp]').outerHTML='<div class="msg bot">'+esc(err.message)+'</div>';
  }
  box.scrollTop=box.scrollHeight;
});


// ---------------- 궁합·길일 (계산만, AI 없음)
const TOOLS={
  past:{title:'지나온 해 되짚기',hand:'Look back',theme:'lilac',sub:'계산이 가리킨 신호를 네 기억과 맞춰 봐'},
  when:{title:'태어난 시간 찾기',hand:'Birth time',theme:'sky',sub:'기억나는 큰일로 12시진 후보를 좁혀 봐'},
  match:{title:'두 사람 궁합',hand:'Match',theme:'rose',sub:'사주·자미두수·점성술로 본 두 사람의 결'},
  pick:{title:'길일 고르기',hand:'Lucky day',theme:'mint',sub:'기간 안에서 나에게 좋은 날 순서'},
  name:{title:'이름 풀이',hand:'Name',theme:'sky',sub:'소리·획수·내 사주로 이름을 봐'},
};
S.tools={};
function toolHero(o,tab){
  return '<div class="tab-hero">'+heroArt(tab)+'<div class="hero-title">'+esc(o.title)+' <span class="hand">'+esc(o.hand)+'</span></div>'+
    '<p class="hero-sub">'+esc(o.sub)+'</p></div>';
}
function openTool(tab){
  S.tab=tab;S.queue=[];
  const o=TOOLS[tab];
  document.body.dataset.theme=o.theme;
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.tab===tab));
  centerTab();
  let h=toolHero(o,tab);
  if(tab==='past'){
    $('page').innerHTML=h+pastView(S.facts.past);
    window.scrollTo(0,0);pastTally();
    return;
  }
  if(tab==='when'){
    $('page').innerHTML=h+whenForm();window.scrollTo(0,0);
    if(S.tools.when) $('toolOut').innerHTML=S.tools.when;
    return;
  }
  if(tab==='name'){
    $('page').innerHTML=h+nameForm();window.scrollTo(0,0);
    if(S.tools.name) $('toolOut').innerHTML=S.tools.name;
    return;
  }
  if(tab==='match'){
    const sex2=S.person&&S.person.sex==='female'?'male':'female';
    const pl=people();
    h+='<form class="card form" id="fMatch" autocomplete="off"><h4 style="margin:0">상대의 정보</h4>'+
      (pl.length?'<div class="ppl-pick"><span>저장한 사람 불러오기</span>'+
        pl.map((x,i)=>'<button type="button" class="chip" data-p2="'+i+'">'+esc(x.nick)+'</button>').join('')+'</div>':'')+
      '<div class="row2"><div class="f"><span>생년월일</span><button type="button" class="datebtn" data-dp="birth2">눌러서 선택</button>'+
      '<input type="hidden" name="birth2" value=""><input type="hidden" name="leap2" value=""></div>'+
      '<label class="f"><span>달력</span><select name="calendar2" data-cal="birth2"><option value="solar">양력</option><option value="lunar">음력</option></select></label></div>'+
      '<div class="row2"><label class="f"><span>태어난 시간</span><input name="birth2_time" type="time" value="12:00"></label>'+
      '<label class="check"><input name="unknown_time2" type="checkbox" value="1"> 시간 모름</label></div>'+
      '<div class="row2"><label class="f"><span>성별</span><select name="sex2"><option value="male"'+(sex2==='male'?' selected':'')+'>남자</option>'+
      '<option value="female"'+(sex2==='female'?' selected':'')+'>여자</option></select></label>'+
      '<label class="f"><span>태어난 도시</span><input name="city2" value="서울"></label></div>'+
      '<button class="go" type="submit">궁합 보기</button>'+
      '<p class="fine">상대의 생년월일은 계산에만 쓰고 저장하지 않아.</p></form><div id="toolOut"></div>';
  }else{
    const d0=new Date(),d1=new Date(Date.now()+30*864e5);
    const iso=d=>d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
    h+='<form class="card form" id="fPick" autocomplete="off">'+
      '<div class="row2"><label class="f"><span>시작 날짜</span><input name="from_date" type="date" value="'+iso(d0)+'"></label>'+
      '<label class="f"><span>끝 날짜</span><input name="to_date" type="date" value="'+iso(d1)+'"></label></div>'+
      '<label class="f"><span>무엇을 위한 날</span><select name="domain"><option value="total">전체</option><option value="love">연애·만남</option>'+
      '<option value="career">일·면접·계약</option><option value="money">돈·거래</option></select></label>'+
      '<button class="go" type="submit">좋은 날 찾기</button></form><div id="toolOut"></div>';
  }
  $('page').innerHTML=h;
  window.scrollTo(0,0);
  if(S.tools[tab]) $('toolOut').innerHTML=S.tools[tab];
  animate($('page'));
}
document.addEventListener('submit',async e=>{
  const id=e.target.id;
  if(id!=='fMatch'&&id!=='fPick') return;
  e.preventDefault();
  if(!S.person){                      // 저장 링크로 연 결과엔 생년월일이 없다 (저장하지 않으니까)
    $('toolOut').innerHTML='<div class="err">저장 링크로 연 결과라 내 생년월일이 없어. 처음 화면에서 입력하거나 \'내 사주 바로 보기\'로 열면 궁합·길일을 볼 수 있어.</div>';
    return;
  }
  const form=e.target,btn=form.querySelector('.go'),q={...S.person};
  new FormData(form).forEach((v,k)=>{q[k]=v;});
  if(id==='fMatch'&&!q.birth2){$('toolOut').innerHTML='<div class="err">상대의 생년월일을 골라 줘.</div>';return;}
  btn.disabled=true;const label=btn.textContent;btn.textContent='계산하는 중...';
  try{
    const j=await postJSON(id==='fMatch'?'/api/match':'/api/pick',q);
    if(id==='fMatch') S.matchData=j.data;
    const html=id==='fMatch'?matchView(j.data):pickView(j.data);
    S.tools[id==='fMatch'?'match':'pick']=html;
    $('toolOut').innerHTML=html;animate($('toolOut'));
    $('toolOut').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){$('toolOut').innerHTML='<div class="err">'+esc(err.message)+'</div>';}
  finally{btn.disabled=false;btn.textContent=label;}
});
function section(n,emoji,title,inner){
  return '<section class="chapter"><div class="ch-label">CHAPTER · '+pad(n)+'</div><div class="ch-head">'+
    '<div class="ch-emoji" aria-hidden="true">'+emoji+'</div><div class="ch-title">'+esc(title)+'</div></div>'+inner+'</section>';
}
function matchView(d){
  const who=(x,t)=>'<div class="c"><b>'+t+'</b><p>일간 '+esc(x.ilgan)+' · '+esc(x.animal)+'띠 · 태양 '+esc(x.sun)+'</p></div>';
  let h=section(1,'💞','두 사람 점수',card('<div class="gauge"><div class="ring" style="--v:'+d.score+'"><span>'+d.score+'</span></div>'+
    '<div><div style="font-weight:800">'+esc(d.head)+'</div><p class="fine" style="margin:.5rem 0 0">점수는 출발점일 뿐, 맞춰 가는 방향을 보는 참고값이야.</p></div></div>'));
  h+=section(2,'🔍','둘의 결',card('<div class="cards">'+who(d.a,'나')+who(d.b,'상대')+'</div>')+
    d.story.map(x=>'<p class="blk">'+esc(x)+'</p>').join(''));
  if(d.strengths.length) h+=section(3,'🤝','잘 맞는 점','<div class="blk checklist"><ul>'+d.strengths.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>');
  if(d.cautions.length) h+=section(4,'🧭','맞춰 갈 점','<div class="blk checklist"><ul>'+d.cautions.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>');
  if(d.dates){
    const row=r=>'<div class="duo"><b>'+esc(r.label)+' <small>'+esc(r.ganzhi)+'</small></b>'+
      '<div class="bar"><span>나</span><div class="t"><i data-w="'+r.me+'"></i></div><b>'+r.me+'</b></div>'+
      '<div class="bar"><span>상대</span><div class="t"><i data-w="'+r.you+'"></i></div><b>'+r.you+'</b></div></div>';
    h+=section(5,'🗓️','둘이 만나기 좋은 날 (앞으로 '+d.dates.days+'일)',card(d.dates.good.map(row).join(''),'둘 다 연애 흐름이 괜찮은 날')+
      card(d.dates.tense.map(row).join('')+'<p class="fine" style="margin:.4rem 0 0">이런 날은 큰 이야기보다 가볍게 보내면 좋아.</p>','둘 다 예민하기 쉬운 날'));
  }
  if(d.info.length) h+=section(6,'📎','참고',card('<ul style="margin:0;padding-left:1.1rem">'+d.info.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>'));
  if(d.sok) h+=sokPairView(d.sok);
  return h;
}
function pickView(d){
  const key=d.domain==='total'?null:d.domain;
  const val=r=>key?r[key]:Math.round((r.love+r.career+r.money)/3);
  const top=d.rows.slice(0,5);
  let h=section(1,'🗓️',d.dom_name+' 좋은 날 순서',d.story.map(x=>'<p class="blk">'+esc(x)+'</p>').join(''));
  h+=section(2,'🏅','상위 다섯 날',card('<div class="bars">'+top.map(r=>'<div class="bar" style="grid-template-columns:110px 1fr 34px">'+
    '<span>'+r.rank+'위 '+esc(r.label)+'</span><div class="t"><i data-w="'+val(r)+'"></i></div><b>'+val(r)+'</b></div>').join('')+'</div>'+
    '<p class="fine" style="margin:.6rem 0 0">'+top.map(r=>esc(r.label)+' '+esc(r.ganzhi)+'일 ('+esc(r.god)+')').join(' · ')+'</p>'));
  h+=section(3,'📋','기간 전체',card('<div class="cal">'+d.rows.slice().sort((a,b)=>a.rank-b.rank).map(r=>
    '<div class="'+(r.rank<=5?'t4':r.rank<=10?'t2':'')+'">'+
    '<b style="display:block">'+esc(r.label)+'</b><small>'+esc(r.ganzhi)+' · '+val(r)+'점</small></div>').join('')+'</div>'));
  return h;
}


// ---------------- 지나온 해 되짚기: 계산이 가리킨 신호를 사용자가 기억과 맞춰 본다 (답은 이 화면 메모리에만)
const MARK_ICON={gyowun:'🔄',daxian:'🧭',saturn:'🪐',jupiter:'✨'};
const PAST_SYS={gyowun:'사주',daxian:'자미두수',saturn:'점성술',jupiter:'점성술'};
S.pastKind={};
S.pastAns=S.pastAns||{};
function ansBtns(key){
  const a=S.pastAns[key]||'';
  return '<div class="ans" data-key="'+esc(key)+'">'+[['yes','맞았어'],['no','아니야'],['skip','기억 안 나']].map(([v,t])=>
    '<button type="button" data-v="'+v+'" class="'+(a===v?'on '+v:'')+'">'+t+'</button>').join('')+'</div>';
}
function pastView(p){
  if(!p||!p.rows.length) return '<div class="card"><p>되짚어 볼 지난해가 아직 없어.</p></div>';
  let h='<div class="card tally" id="pastTally"></div>';
  h+='<p class="fine" style="margin:0 4px 10px">'+esc(p.note)+' 교운기는 대운이 바뀌는 앞뒤 해, 토성 회귀는 토성이 태어날 때 자리로 돌아오는 때야. '+
    '계산이 맞힌 걸 증명하는 게 아니라, 네 기억과 얼마나 겹치는지 스스로 보는 놀이야.</p>';
  p.rows.slice().reverse().forEach(r=>{
    if(!r.signals.length&&!r.marks.length) return;
    h+='<div class="yr-card"><div class="yr-head"><b>'+r.year+'</b><span>만 '+r.age+'세 · '+esc(r.ganzhi)+'년</span></div>';
    r.marks.forEach((m,i)=>{
      S.pastKind[r.year+'m'+i]=PAST_SYS[m.kind]||'사주';
      h+='<div class="claim mark"><div><span class="ico">'+(MARK_ICON[m.kind]||'•')+'</span>'+esc(m.text)+
        '<small>'+(m.kind==='jupiter'?'이 해에 새 기회가 오거나 넓어진 일이 있었어?':'이 해에 일·관계·사는 곳 같은 큰 변화가 있었어?')+'</small></div>'+ansBtns(r.year+'m'+i)+'</div>';
    });
    r.signals.forEach(sg=>{
      S.pastKind[r.year+sg.domain]='사주';
      h+='<div class="claim '+sg.dir+'"><div><span class="pill '+sg.dir+'">'+esc(sg.word)+' '+esc(sg.tag)+'</span>'+
        (sg.why.length?'<small>'+esc(sg.why.join(', '))+'</small>':'')+
        '<small>'+(sg.dir==='up'?esc(sg.word)+' 쪽이 잘 풀리거나 기회가 있었어?':esc(sg.word)+' 쪽이 답답하거나 힘들었어?')+'</small></div>'+
        ansBtns(r.year+sg.domain)+'</div>';
    });
    h+='</div>';
  });
  return h;
}
function pastTally(){
  const box=$('pastTally');if(!box) return;
  const v=Object.values(S.pastAns),yes=v.filter(x=>x==='yes').length,no=v.filter(x=>x==='no').length,n=yes+no;
  const total=document.querySelectorAll('.ans').length;
  box.innerHTML='<div class="gauge"><div class="ring" style="--v:'+(n?Math.round(yes/n*100):0)+'"><span>'+(n?Math.round(yes/n*100)+'%':'-')+'</span></div>'+
    '<div><div style="font-weight:800">내 기억과 겹친 정도</div><p class="fine" style="margin:.3rem 0 0">맞았어 '+yes+' · 아니야 '+no+
    ' · 답한 것 '+v.length+' / '+total+'</p><p class="fine" style="margin:.3rem 0 0">'+
    (n>=5?(yes/n>=0.6?'꽤 많이 겹쳤어. 앞으로의 흐름도 같은 계산으로 봤으니 참고해 봐.':'겹친 게 많지 않아. 사주는 경향일 뿐이라 그럴 수 있어.'):'다섯 개 넘게 고르면 겹친 정도를 알려 줄게.')+
    '</p></div></div>'+pastBySystem();
}
// 체계별로 내 기억과 얼마나 맞았나: 나한테 잘 맞는 체계 찾기
function pastBySystem(){
  const st={};
  Object.entries(S.pastAns).forEach(([k,v])=>{
    if(v!=='yes'&&v!=='no') return;
    const sys=S.pastKind[k]||'사주';st[sys]=st[sys]||{yes:0,no:0};st[sys][v]++;
  });
  const names=['사주','자미두수','점성술'].filter(x=>st[x]);
  if(!names.length) return '';
  const rate=x=>st[x].yes/(st[x].yes+st[x].no);
  const ok=names.filter(x=>st[x].yes+st[x].no>=3).sort((a,b)=>rate(b)-rate(a));
  return '<div class="sys-tally">'+names.map(x=>{const n=st[x].yes+st[x].no,p=Math.round(rate(x)*100);
      return '<div class="bar"><span>'+x+'</span><div class="t"><i style="width:'+p+'%"></i></div><b>'+st[x].yes+'/'+n+'</b></div>';}).join('')+
    '<p class="fine" style="margin:.4rem 0 0">'+(ok.length>=2?'지금까지는 <b>'+ok[0]+'</b> 신호가 네 기억과 제일 잘 맞았어 ('+Math.round(rate(ok[0])*100)+'%). 답이 적으면 우연일 수 있어.':
      '체계마다 세 개 이상 답하면 어느 체계가 너한테 잘 맞는지 비교해 줄게.')+'</p></div>';
}
document.addEventListener('click',e=>{
  const b=e.target.closest('.ans button');if(!b) return;
  const box=b.parentElement,key=box.dataset.key;
  S.pastAns[key]=S.pastAns[key]===b.dataset.v?'':b.dataset.v;
  if(!S.pastAns[key]) delete S.pastAns[key];
  box.querySelectorAll('button').forEach(x=>{x.className=S.pastAns[key]===x.dataset.v?'on '+x.dataset.v:'';});
  pastTally();
});


// ---------------- 이름 풀이 (소리·획수·사주)
const EL_CLS={목:'el-목',화:'el-화',토:'el-토',금:'el-금',수:'el-수'};
const REL_TXT={same:'같은 기운',gen:'상생',ke:'상극'};
function nameForm(){
  return '<form class="card form" id="fName" autocomplete="off"><div class="row2">'+
    '<label class="f"><span>성 (한글)</span><input name="surname" maxlength="2" placeholder="예: 김"></label>'+
    '<label class="f"><span>이름 (한글)</span><input name="given" maxlength="3" placeholder="예: 지현"></label></div>'+
    '<button class="ghost" type="button" id="nmPick">한자도 고르기 (선택)</button><div id="nmHanja"></div>'+
    '<button class="go" type="submit">이름 풀이 보기</button>'+
    '<p class="fine">한자를 고르면 획수(원획법)로 원형이정 네 격과 81수리까지 봐. 안 고르면 소리만 봐. 이름은 저장하지 않아.</p></form><div id="toolOut"></div>';
}
async function nmPick(){
  const f=$('fName'),name=(f.surname.value.trim()+f.given.value.trim());
  const ns=f.surname.value.trim().length;
  if(!name){$('nmHanja').innerHTML='<div class="err">성과 이름을 먼저 넣어 줘.</div>';return;}
  $('nmHanja').innerHTML='<p class="fine">불러오는 중...</p>';
  let h='';
  for(let i=0;i<name.length;i++){
    const r=await fetch('/api/name/hanja?r='+encodeURIComponent(name[i])+'&s='+(i<ns?1:0)).then(x=>x.json()).catch(()=>({items:[]}));
    h+='<label class="f"><span>'+esc(name[i])+(i<ns?' (성)':'')+'</span><select data-nmi="'+i+'"><option value="">한자 없음 / 모름</option>'+
      (r.items||[]).map(x=>'<option value="'+x.cp+'">'+esc(x.hun)+' · '+x.strokes+'획</option>').join('')+'</select></label>';
  }
  $('nmHanja').innerHTML='<div class="nm-grid">'+h+'</div><p class="fine">뜻(훈음)과 획수로 골라. 성은 많이 쓰는 한자가 맨 위야.</p>';
}
function nameView(d){
  const chain=s=>'<div class="nm-chain">'+d.name.split('').map((c,i)=>'<span class="nm-syl"><b>'+esc(c)+'</b><i class="'+EL_CLS[s.elements[i]]+'">'+s.elements[i]+'</i></span>'+
    (i<s.relations.length?'<span class="nm-rel '+s.relations[i]+'">'+REL_TXT[s.relations[i]]+'</span>':'')).join('')+'</div>';
  const mj=d.sound.major,mn=d.sound.minor;
  let h=section(1,'🔊','소리로 본 이름 (발음오행)',card(chain(mj)+'<p style="margin:.5rem 0 0">'+esc(mj.school)+'로 보면 소리 흐름이 <b>'+esc(mj.verdict)+'</b>이야. '+
    (mj.relations.includes('ke')?'상극(서로 누르는 사이)이 있어 부를 때 기운이 부딪친다고 보는 쪽이야.':'글자끼리 같은 기운이거나 서로 살리는 흐름이야.')+'</p>')+
    card(chain(mn)+'<p style="margin:.5rem 0 0">'+esc(mn.school)+'로 보면 <b>'+esc(mn.verdict)+'</b>이야. 두 학설은 ㅇㅎ과 ㅁㅂㅍ을 거꾸로 봐서 결과가 다를 수 있어.</p>','다른 학설로 보면'));
  h+=section(2,'☯️','모음의 음양',card('<div class="chips">'+d.name.split('').map((c,i)=>'<span class="chip'+(d.vowel.marks[i]==='양'?' a':'')+'">'+esc(c)+' '+d.vowel.marks[i]+'</span>').join('')+'</div>'+
    '<p style="margin:.5rem 0 0">'+(d.vowel.balanced?'밝은 모음(양)과 어두운 모음(음)이 섞여 소리의 균형이 좋은 편이야.':'모음이 한쪽('+d.vowel.marks[0]+')으로만 모여 있어. 작명에서는 둘이 섞이는 쪽을 더 좋게 봐.')+'</p>'));
  if(d.suri){
    const s=d.suri,cls={good:'up',bad:'down',half:'',split:''};
    h+=section(3,'🔢','획수로 본 이름 (원형이정 81수리)',
      '<div class="cards">'+['won','hyeong','i','jeong'].map(k=>{const g=s.ge[k];return '<div class="c"><b>'+g.label+' '+g.num+'수 <span class="pill '+cls[g.tag]+'">'+g.tag_kr+'</span></b>'+
        '<p><small>'+esc(g.period)+' · '+esc(g.name)+'</small><br>'+esc(g.mean)+'</p></div>';}).join('')+'</div>'+
      card('<p style="margin:0">글자별 원획: '+d.name.split('').map((c,i)=>esc(c)+' '+s.strokes[i]+'획('+s.yinyang[i]+')').join(' · ')+'</p>'+
        '<p style="margin:.4rem 0 0">'+(s.yy_balanced?'획수의 홀짝(음양)이 섞여 있어 균형이 좋은 편이야.':'획수가 모두 '+s.yinyang[0]+'이라 음양이 한쪽으로 쏠려 있어.')+'</p>'+
        (s.note?'<p class="fine" style="margin:.4rem 0 0">'+esc(s.note)+'</p>':'')+
        '<p class="fine" style="margin:.4rem 0 0">81수리 길흉은 네 곳의 작명 자료를 대조해 다수결로 정했고, 둘로 갈린 수는 엇갈림으로 적었어.</p>'));
  }else{
    h+=section(3,'🔢','획수로 본 이름',card('<p style="margin:0">한자를 모두 고르면 원형이정 네 격과 81수리 길흉까지 볼 수 있어.</p>'));
  }
  if(d.saju){
    const m=d.saju.missing,f=d.saju.filled;
    h+=section(4,'🧩','내 사주와 함께',card('<p style="margin:0">'+(m.length?'내 원국(여덟 글자)에는 '+m.join('·')+' 기운이 비어 있어. '+
      (f.length?'이름 소리(다수설)가 '+f.join('·')+' 기운을 보태 줘서 빈자리를 채우는 쪽이야.':'이름 소리에는 이 기운이 없어. 작명에서는 빈 기운을 이름으로 보태는 방법을 쓰기도 해.'):
      '내 원국에는 다섯 기운이 다 있어서, 이름 소리로 따로 채울 빈자리는 없어.')+'</p>'));
  }
  return h;
}
document.addEventListener('click',e=>{if(e.target.id==='nmPick'){e.preventDefault();nmPick();}});
document.addEventListener('submit',async e=>{
  if(e.target.id!=='fName') return;
  e.preventDefault();
  const f=e.target,btn=f.querySelector('.go');
  const name=f.surname.value.trim()+f.given.value.trim();
  const hanja=name.split('').map((_,i)=>{const s=f.querySelector('[data-nmi="'+i+'"]');return s&&s.value?+s.value:null;});
  btn.disabled=true;
  try{
    const d=await postJSON('/api/name',{surname:f.surname.value.trim(),given:f.given.value.trim(),hanja,token:S.token});
    const html=nameView(d);S.tools.name=html;$('toolOut').innerHTML=html;
    $('toolOut').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){$('toolOut').innerHTML='<div class="err">'+esc(err.message)+'</div>';}
  finally{btn.disabled=false;}
});


document.addEventListener('click',e=>{if(e.target.id==='bdChip'){const c=$('bdCard');if(c) c.hidden=!c.hidden;}});

// ---------------- 용어 눌러서 뜻 보기 (용어 풀이집 /api/glossary)
const TERM_SKIP=new Set(['사주','태양','금성','수성','화성','목성','토성','음력','기질','궁합','타로','주역','오미쿠지','생명수','달','양']);
let TERM_RE=null;
async function loadGloss(){
  if(S.gloss) return;
  try{S.gloss=await fetch('/api/glossary').then(r=>r.json());}catch(_){S.gloss={};return;}
  const keys=Object.keys(S.gloss).filter(k=>k.length>=2&&!TERM_SKIP.has(k)).sort((a,b)=>b.length-a.length);
  TERM_RE=keys.length?new RegExp('('+keys.map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')','g'):null;
}
function linkTerms(escaped,used){
  if(!TERM_RE) return escaped;
  return escaped.replace(TERM_RE,m=>{if(used.has(m)) return m;used.add(m);return '<button type="button" class="term" data-t="'+m+'">'+m+'</button>';});
}
document.addEventListener('click',e=>{
  const b=e.target.closest('.term'),tip=$('termTip');
  if(!b){if(tip&&!e.target.closest('#termTip')) tip.classList.remove('on');return;}
  const r=b.getBoundingClientRect();
  tip.innerHTML='<b>'+esc(b.dataset.t)+'</b>'+esc((S.gloss||{})[b.dataset.t]||'');
  tip.style.left=Math.max(8,Math.min(window.innerWidth-296,r.left+window.scrollX-20))+'px';
  tip.style.top=(r.bottom+window.scrollY+6)+'px';
  tip.classList.add('on');
});


// ---------------- 근거 보기: 챕터가 본 계산값 (AI 풀이도 이 값만 받아서 쓴다)
const PATH_LABEL={
  'career.best':'좋은 달 (일)','career.extra':'일과 관련된 하늘의 별','career.fit_jobs':'잘 맞는 분야','career.guan':'원국의 일 별(관성)',
  'career.guanlu':'자미두수 일 자리(관록궁)','career.months':'앞으로 12개월 (일)','career.palaces':'일 관련 자미두수 궁','career.years':'앞으로 3년 (일)',
  'life.current':'지금 연대','life.dayun_narr':'대운 여덟 걸음','life.dayun_rel':'대운과 원국이 만나는 자리','life.decades':'연대별 흐름','life.phases':'초년·중년·말년',
  'love.animals':'띠 궁합','love.best':'좋은 달 (연애)','love.day_stage':'태어난 날 기운 단계','love.dohwa':'도화(끌림 별)','love.hongyeom':'홍염',
  'love.meet_paths':'만날 자리','love.months':'앞으로 12개월 (연애)','love.moon':'달 별자리','love.spouse_seat':'배우자 자리','love.spouse_star':'배우자 별',
  'love.this_year':'올해 연애','love.venus':'금성 별자리','love.years':'앞으로 3년 (연애)','love.ziwei_spouse':'자미두수 배우자 자리(부처궁)',
  'money.best':'좋은 달 (돈)','money.cai':'원국의 돈 별(재성)','money.caibo':'자미두수 돈 자리(재백궁)','money.extra':'돈과 관련된 하늘의 별',
  'money.months':'앞으로 12개월 (돈)','money.palaces':'돈 관련 자미두수 궁','money.years':'앞으로 3년 (돈)',
  'natal':'원국 요약','natal.astro':'출생 차트','natal.character':'타고난 기질','natal.classic_sinsal':'신살','natal.dayun':'대운','natal.elements':'오행 개수',
  'natal.geguk':'격국','natal.geguk_mean':'격국의 뜻','natal.guiin':'귀인','natal.ilgan':'일간','natal.ilju':'일주','natal.johu':'계절로 본 용신(조후)',
  'natal.strength':'기운의 세기','natal.yongsin':'힘의 세기로 본 용신(억부)',
  'newyear.age':'그해 만 나이','newyear.age_kr':'그해 세는나이','newyear.best':'그해 좋은 달','newyear.dayun_note':'교운기','newyear.ganzhi':'그해 간지',
  'newyear.god':'그해 들어오는 기운','newyear.months':'그해 열두 달','newyear.rel':'그해와 배우자 자리','newyear.signals':'그해 영역별 신호',
  'newyear.sky':'목성·토성','newyear.tojeong':'토정비결','newyear.year':'그해','newyear.ziwei':'자미두수 그해 운',
  'today.agreement':'세 체계 합의','today.almanac':'오늘 달력','today.domains':'영역별 오늘','today.domains.career':'오늘 직장',
  'today.domains.love':'오늘 연애','today.domains.money':'오늘 금전','today.focus':'오늘의 초점','today.heads':'한 줄 요약','today.keywords':'키워드',
  'today.scores':'점수','today.systems':'세 체계가 본 오늘','today.total_reasons':'총운 근거'};
const KEY_LABEL={sun:'태양',moon:'달',venus:'금성',mars:'화성',asc:'상승궁',mc:'천정',aspects:'각도',sign:'별자리',style:'스타일',ideal:'끌리는 상대',
  how:'다가가는 법',need:'필요한 것',star:'별',look:'인상',mind:'마음',job:'일',meet:'만나는 곳',tip:'팁',main:'먼저 쓰는 기운',order:'순서',palace:'궁',
  palace_talk:'뜻',hua:'사화',score:'점수',head:'한 줄',reasons:'근거',signal:'신호',points:'가감',tips:'해 볼 것',avoid:'피할 것',
  love:'연애',career:'직장',money:'금전',total:'총운',all:'공통',tag:'흐름',read:'괘',mean:'뜻',note:'참고',year:'해',age:'나이',rel:'관계',god:'기운',
  common:'모든 운 공통',only:'이 영역만'};
const EV_SKIP=new Set(['wheel','key','stem','branch','boundary','ilju','ziwei','pillars','palaces','steps','agree_with_eokbu','hour_known','text_len']);
const NATAL_KEYS=['day_pillar','character','strength','geguk','geguk_mean','yongsin','johu','elements','classic_sinsal','guiin','dayun'];
function getPath(o,p){return p.split('.').reduce((a,k)=>a==null?a:a[k],o);}
function evLines(v,depth){
  depth=depth||0;const out=[];
  if(v==null||v==='') return out;
  if(typeof v!=='object'){out.push(String(v));return out;}
  if(Array.isArray(v)){
    v.slice(0,14).forEach(x=>{
      if(x&&typeof x==='object'&&!Array.isArray(x)){
        if(x.ym||x.label||x.year||x.gz||x.ganzhi){
          const head=[x.ym||x.year||'',x.gz||x.ganzhi||'',x.tag||''].filter(Boolean).join(' ');
          const why=Array.isArray(x.why)?x.why.join(', '):(typeof x.line==='string'?x.line:'');
          out.push(head+(why?': '+why:''));
        }else out.push(...evLines(x,depth+1).slice(0,4));
      }else if(x!=null&&x!=='') out.push(String(x));
    });
    if(v.length>14) out.push('… 외 '+(v.length-14)+'개');
    return out;
  }
  if(depth>2) return out;
  Object.entries(v).forEach(([k,x])=>{
    if(EV_SKIP.has(k)) return;
    const lab=KEY_LABEL[k];
    if(x&&typeof x==='object') evLines(x,depth+1).slice(0,6).forEach(s=>out.push((lab?lab+': ':'')+s));
    else if(x!=null&&x!=='') out.push((lab?lab+': ':'')+String(x));
  });
  return out;
}
function evidenceHTML(pick){
  const f=S.facts;
  return pick.map(p=>{
    let v=getPath(f,p);
    if(p==='natal'&&v){const o={};NATAL_KEYS.forEach(k=>{if(v[k]!=null) o[k]=v[k];});v=o;}
    const lines=evLines(v).slice(0,12);
    if(!lines.length) return '';
    return '<div class="ev"><b>'+esc(PATH_LABEL[p]||p)+'</b><ul>'+lines.map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul></div>';
  }).join('')+'<p class="fine">AI 풀이는 이 값들만 받아서 썼고, 여기 없는 숫자나 단정하는 말이 든 문장은 화면에 나오기 전에 걸러져.</p>';
}
document.addEventListener('toggle',e=>{
  const d=e.target;
  if(!d.classList||!d.classList.contains('evid')||!d.open) return;
  const b=d.querySelector('.evid-body');
  if(b.dataset.done) return;
  try{b.innerHTML=evidenceHTML(JSON.parse(d.dataset.pick||'[]'));}catch(_){b.innerHTML='<p class="fine">근거를 불러오지 못했어.</p>';}
  b.dataset.done='1';
},true);

// ---------------- 세 체계 합의도 (앞으로 10년)
function consensus(rows,dom){
  if(!rows||!rows.length) return '';
  const ic=v=>v==null?'<span class="cs na">-</span>':v>0?'<span class="cs up">▲</span>':v<0?'<span class="cs dn">▼</span>':'<span class="cs mid">·</span>';
  return card('<div class="tbl"><table class="xt cons"><tr><th>해</th><th>나이</th><th>사주</th><th>자미두수</th><th>점성술</th><th>합의</th></tr>'+
    rows.map((r,i)=>{
      const c=r.domains[dom];
      const lab=c.up&&!c.down?c.up+'/'+c.n+' 좋음':c.down&&!c.up?c.down+'/'+c.n+' 조심':c.up&&c.down?'엇갈림':'잔잔';
      const cls=c.up>=2&&!c.down?'hot':c.up&&!c.down?'warm':c.down&&!c.up?'cold':'';
      return '<tr class="'+cls+'" data-cons="'+dom+'" data-i="'+i+'"><td><b>'+r.year+'</b></td><td>'+r.age+'</td><td>'+ic(c.saju)+'</td><td>'+ic(c.ziwei)+'</td><td>'+ic(c.astro)+'</td><td>'+lab+'</td></tr>';
    }).join('')+'</table></div><div class="cal-why" id="cons-'+dom+'"></div>'+
    '<p class="fine" style="margin-top:6px">▲ 좋은 쪽 · ▼ 조심 · · 보통 · - 태어난 시간을 몰라 못 봄. 줄을 누르면 이유가 나와. 세 체계가 같은 쪽을 가리킬수록 믿을 만한 흐름으로 봐.</p>',
    '세 체계가 같은 말을 할까? (앞으로 10년)');
}
document.addEventListener('click',e=>{
  const tr=e.target.closest('tr[data-cons]');if(!tr) return;
  const dom=tr.dataset.cons,r=S.facts.insights.consensus[+tr.dataset.i],c=r.domains[dom],w=c.why;
  const box=$('cons-'+dom);
  box.innerHTML='<b>'+r.year+'년 ('+esc(r.ganzhi)+') '+esc(DOM_WORD[dom])+'</b><br>사주: '+esc(w.saju)+
    (w.ziwei?'<br>자미두수: '+esc(w.ziwei):'')+(w.astro?'<br>점성술: '+esc(w.astro):'');
  box.classList.add('on');
});

// ---------------- 캘린더 앱으로 내보내기 (.ics, 서버 저장 없이 이 기기에서 만든다)
const DOM_TIP={love:['만남 자리를 늘려 봐 (소개·모임·앱)','큰 결정은 서두르지 말고 오해는 바로 풀어'],
  career:['밀고 나가 보기 좋은 달','무리하지 말고 다듬는 달'],money:['기회를 잡아 보기 좋은 달','지출을 조심하는 달']};
function icsEsc(s){return String(s).replace(/\\/g,'\\\\').replace(/;/g,'\\;').replace(/,/g,'\\,').replace(/\n/g,'\\n');}
function icsFold(line){
  const enc=new TextEncoder(),out=[];let cur='',n=0;
  for(const ch of line){const b=enc.encode(ch).length;if(n+b>73){out.push(cur);cur=' ';n=1;}cur+=ch;n+=b;}
  out.push(cur);return out.join('\r\n');
}
function icsNext(s){const d=new Date(s+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+1);return d.toISOString().slice(0,10).replace(/-/g,'');}
function buildIcs(dom){
  const f=S.facts,rows=(f[dom]||{}).months||[],W=DOM_WORD[dom];
  const stamp=new Date().toISOString().replace(/[-:]/g,'').slice(0,15)+'Z',ev=[];
  rows.forEach(r=>{
    if(!r.from||!r.to||!r.score) return;
    ev.push(['사주 '+W+': '+r.tag,r.from,r.to,(r.why.join(', ')||'')+'\n'+(r.score>0?DOM_TIP[dom][0]:DOM_TIP[dom][1])]);
  });
  const g=(f.insights||{}).golden;
  if(dom==='love'&&g&&g.month) ev.push(['나의 연애 골든타임',g.month.from,g.month.to,g.month.parts.join(', ')]);
  if(!ev.length) return null;
  const L=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//saju-agent//KO','CALSCALE:GREGORIAN','X-WR-CALNAME:'+icsEsc('사주 '+W+' 흐름')];
  ev.forEach((e,i)=>L.push('BEGIN:VEVENT','UID:saju-'+dom+'-'+e[1].replace(/-/g,'')+'-'+i+'@saju-agent','DTSTAMP:'+stamp,
    'DTSTART;VALUE=DATE:'+e[1].replace(/-/g,''),'DTEND;VALUE=DATE:'+icsNext(e[2]),icsFold('SUMMARY:'+icsEsc(e[0])),
    icsFold('DESCRIPTION:'+icsEsc(e[3])),'TRANSP:TRANSPARENT','END:VEVENT'));
  L.push('END:VCALENDAR');
  return L.join('\r\n')+'\r\n';
}
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-ics]');if(!b) return;
  const dom=b.dataset.ics,txt=buildIcs(dom),out=$('ics-'+dom);
  if(!txt){out.innerHTML='<p class="fine">앞으로 12개월에 따로 걸리는 달이 없어서 넣을 일정이 없어.</p>';return;}
  const url=URL.createObjectURL(new Blob([txt],{type:'text/calendar;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='saju-'+dom+'.ics';document.body.appendChild(a);a.click();a.remove();
  out.innerHTML='<p class="fine">좋은 달·조심할 달을 종일 일정으로 담았어. 내려받은 파일을 열면 구글·애플 캘린더에 들어가.</p>';
});

// ---------------- 태어난 시간 찾기 (인생 사건으로 12시진 후보 좁히기)
const EVENT_KINDS=[['love','연애 시작·결혼'],['breakup','이별·이혼'],['move','이사·이민'],['job','취업·이직·승진'],
  ['health','큰 병·사고·수술'],['child','아이 출생'],['money','큰돈이 들어오거나 나감'],['family','가족을 떠나보냄']];
function evRow(y0){
  const ys=[];for(let y=THIS_Y;y>=y0;y--) ys.push(y);
  return '<div class="ev-row"><select name="ey"><option value="">연도</option>'+ys.map(y=>'<option>'+y+'</option>').join('')+'</select>'+
    '<select name="ek">'+EVENT_KINDS.map(([k,t])=>'<option value="'+k+'">'+t+'</option>').join('')+'</select>'+
    '<button type="button" class="ghost ev-del" aria-label="이 사건 지우기">×</button></div>';
}
function whenForm(){
  if(!S.person) return '<div class="card"><p>저장 링크로 연 결과라 생년월일이 없어. 처음 화면에서 입력하면 쓸 수 있어.</p></div>';
  const y0=+S.person.birth.slice(0,4);
  return '<div class="card"><p style="margin:0">태어난 시간을 모르거나 헷갈릴 때, 기억나는 큰일 몇 개로 12시진(2시간 단위) 중 어디가 맞는지 좁혀 봐. '+
    '점성술의 출생시간 보정처럼 사건이 난 해에 그 시간대의 명반·차트가 맞는 자리를 가리켰는지 세는 방식이야.</p>'+
    '<p class="fine" style="margin-top:6px">재미·참고용이야. 사건이 많을수록 좁혀지고, 다섯 개 이상을 권해. 입력한 사건은 저장하지 않아.</p></div>'+
    '<form class="card form" id="fWhen"><div id="evRows">'+evRow(y0)+evRow(y0)+evRow(y0)+'</div>'+
    '<button type="button" class="ghost" id="evAdd">사건 추가</button><button class="go" type="submit">후보 시간 보기</button></form><div id="toolOut"></div>';
}
function whenView(d){
  const top=d.candidates.slice(0,3),max=Math.max(1,d.candidates[0].score);
  let h=card('<p style="margin:0"><b>'+esc(d.note)+'</b></p><p class="fine" style="margin-top:6px">사건 '+d.events+'개로 12시진을 비교했어. 1등과 2등 차이 '+d.gap+'점.</p>','결과');
  h+='<div class="cards" style="margin-bottom:12px">'+top.map((c,i)=>'<div class="c"><b>'+(i+1)+'위 · '+esc(c.label)+'</b><p>시계 시각 '+esc(c.clock)+
    '<br>시주 '+esc(c.hour_pillar||'-')+' · 상승궁 '+esc(c.asc)+'<br>점수 '+c.score+'</p>'+
    '<button type="button" class="ghost use-time" data-h="'+c.hour+'" data-m="'+c.minute+'">이 시간으로 다시 보기</button></div>').join('')+'</div>';
  h+=card('<ul style="margin:0;padding-left:1.1rem">'+d.candidates[0].hits.map(x=>'<li><b>'+x.year+' '+esc(x.kind)+'</b>: '+
    esc(x.why.join(', ')||'맞는 신호 없음')+'</li>').join('')+'</ul>','1위 시간대에서 사건마다 맞은 것');
  h+=card(d.candidates.map(c=>'<div class="bar"><span>'+esc(c.label)+'</span><div class="t"><i data-w="'+Math.round(c.score/max*100)+'"></i></div><b>'+c.score+'</b></div>').join('')+
    '<p class="fine" style="margin-top:6px">시계 시각은 태어난 곳의 진태양시 보정을 뺀 값이야. 밤 11시 전후 출생은 날짜가 바뀔 수 있어.</p>','12시진 전체 점수');
  return h;
}
document.addEventListener('click',e=>{
  if(e.target.id==='evAdd'){const box=$('evRows');if(box.children.length<10) box.insertAdjacentHTML('beforeend',evRow(+S.person.birth.slice(0,4)));return;}
  const del=e.target.closest('.ev-del');if(del){if($('evRows').children.length>1) del.parentElement.remove();return;}
  const u=e.target.closest('.use-time');
  if(u){
    const f=$('fMain');f.querySelector('[name=birth_time]').value=pad(+u.dataset.h)+':'+pad(+u.dataset.m);
    const unk=f.querySelector('[name=unknown_time]');unk.checked=false;f.querySelector('[name=birth_time]').disabled=false;
    f.requestSubmit?f.requestSubmit():f.querySelector('.go').click();
  }
});
document.addEventListener('submit',async e=>{
  if(e.target.id!=='fWhen') return;
  e.preventDefault();
  const events=[...e.target.querySelectorAll('.ev-row')].map(r=>({year:r.querySelector('[name=ey]').value,kind:r.querySelector('[name=ek]').value})).filter(x=>x.year);
  if(!events.length){$('toolOut').innerHTML='<div class="err">사건 연도를 하나 이상 골라 줘.</div>';return;}
  const btn=e.target.querySelector('.go');btn.disabled=true;btn.textContent='계산하는 중...';
  try{
    const d=await postJSON('/api/v2/rectify',{...S.person,events});
    S.tools.when=whenView(d);$('toolOut').innerHTML=S.tools.when;animate($('toolOut'));
    $('toolOut').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){$('toolOut').innerHTML='<div class="err">'+esc(err.message)+'</div>';}
  finally{btn.disabled=false;btn.textContent='후보 시간 보기';}
});

// ---------------- 속궁합 (19): 성인 확인을 켠 사람에게만 보인다 (확인 여부는 이 브라우저에만 저장)
const ADULT_KEY='saju.adult';
function isAdult(){try{return localStorage.getItem(ADULT_KEY)==='1';}catch(_){return !!S.adult;}}
function setAdult(v){S.adult=v;try{v?localStorage.setItem(ADULT_KEY,'1'):localStorage.removeItem(ADULT_KEY);}catch(_){}}
function adultGate(){
  return card('<p style="margin:0 0 8px">속궁합은 성인용 풀이라 솔직한 표현이 들어가. 만 19세 이상만 켜 줘.</p>'+
    '<label class="check" style="padding-top:0"><input type="checkbox" class="adult-ok"> 만 19세 이상이고, 속궁합을 솔직한 말로 볼게</label>');
}
function sokSection(){
  const s=S.facts.sok;if(!s) return '';
  let inner;
  if(!isAdult()) inner=adultGate();
  else inner=card('<ul class="sok"><li><b>욕망 별(화성) '+esc(s.mars.sign)+'</b>'+esc(s.mars.text)+'</li>'+
      '<li><b>끌림 별(금성) '+esc(s.venus.sign)+'</b>'+esc(s.venus.text)+'</li>'+
      (s.moon_mars?'<li><b>속마음(달)과 욕망(화성)</b>'+esc(s.moon_mars)+'</li>':'')+'</ul>','너의 밤 스타일')+
    card('<div class="tbl"><table class="xt"><tr><th class="l">볼 것</th><th class="l">불붙는 조합</th><th class="l">삐걱대는 조합</th></tr>'+
      '<tr><td class="l">상대 욕망 별(화성)</td><td class="l">'+esc(s.partner_mars.good.join(' · '))+'</td><td class="l">'+esc(s.partner_mars.hard.join(' · '))+'</td></tr>'+
      '<tr><td class="l">상대 끌림 별(금성)</td><td class="l">'+esc(s.partner_venus.good.join(' · '))+'</td><td class="l">'+esc(s.partner_venus.hard.join(' · '))+'</td></tr>'+
      '<tr><td class="l">상대 태어난 날 글자</td><td class="l">'+esc(s.day_branch.good.join(' · '))+'</td><td class="l">'+esc(s.day_branch.hard.join(' · '))+'</td></tr>'+
      '</table></div><p class="fine" style="margin-top:6px">궁합 탭에서 상대 생일을 넣으면 두 사람 속궁합도 같이 나와.</p>','이런 상대랑 불붙어')+
    '<p style="text-align:right;margin:4px 0 0"><button type="button" class="linkbtn adult-off">19 모드 끄기</button></p>';
  return '<section class="chapter" id="ch-sok"><div class="ch-label">CHAPTER · 19</div><div class="ch-head"><div class="ch-emoji" aria-hidden="true">🔞</div>'+
    '<div class="ch-title">속궁합 (19)</div></div>'+inner+
    '<div class="src">여러 별자리 해설과 사주 궁합 해설이 공통으로 말하는 결만 모았어. 재미로 봐 줘.</div></section>';
}
function sokPairView(sp){
  const b=t=>({good:'<span class="pill p-good">불붙음</span>',warn:'<span class="pill p-warn">삐걱 주의</span>',mid:'<span class="pill p-mid">무난</span>'}[t]);
  if(!isAdult()) return section(7,'🔞','속궁합 (19)',adultGate());
  return section(7,'🔞','속궁합 (19)',card('<div class="tbl"><table class="xt">'+sp.rows.map(r=>'<tr><td class="l">'+esc(r.label)+' ('+esc(r.aspect)+')</td><td>'+b(r.tone)+
    '</td><td class="l">'+esc(r.text)+'</td></tr>').join('')+'<tr><td class="l">태어난 날 글자</td><td>'+b(sp.day.tone)+'</td><td class="l">'+esc(sp.day.text)+'</td></tr></table></div>'+
    '<p class="fine" style="margin-top:6px">나: 화성 '+esc(sp.a.mars)+' · 금성 '+esc(sp.a.venus)+' / 상대: 화성 '+esc(sp.b.mars)+' · 금성 '+esc(sp.b.venus)+'. 불붙는 조합 '+sp.good+'/'+sp.total+'.</p>')+
    '<p style="text-align:right;margin:4px 0 0"><button type="button" class="linkbtn adult-off">19 모드 끄기</button></p>');
}
function rerenderAdult(){
  if(S.tab==='match'&&S.matchData){S.tools.match=matchView(S.matchData);$('toolOut').innerHTML=S.tools.match;animate($('toolOut'));}
  else if(S.tab==='love'){const y=window.scrollY;openTab('love');window.scrollTo(0,y);}
}
document.addEventListener('change',e=>{if(e.target.classList&&e.target.classList.contains('adult-ok')&&e.target.checked){setAdult(true);rerenderAdult();}});
document.addEventListener('click',e=>{if(e.target.closest('.adult-off')){setAdult(false);rerenderAdult();}});

// ---------------- 나의 연애 골든타임 카드
function goldenInfo(){
  const g=(S.facts.insights||{}).golden;if(!g||!g.month) return null;
  const m=g.month,lines=[m.from.replace(/-/g,'.')+' ~ '+m.to.replace(/-/g,'.')+' · '+m.ganzhi+'월',(m.parts||[]).join(' · ')];
  if(g.year) lines.push('세 체계가 가장 많이 겹치는 해: '+g.year.year+'년 (만 '+g.year.age+'살, '+g.year.n+'개 중 '+g.year.up+'개 좋음)');
  return {title:'나의 연애 골든타임',hand:'Golden Time',score:null,big:m.year+'.'+pad(m.month),head:'앞으로 24개월 중 연애 신호가 가장 센 달',lines,
    chips:['일주 '+S.facts.natal.day_pillar,'신호 세기 '+m.power]};
}

// ---------------- 생년월일 캘린더 선택기
// 글자로 입력하지 않고 연대, 연도, 월, 일 순서로 눌러서 고른다.
// 음력은 그해 실제 달 목록(윤달 포함)과 그달 일수를 서버에서 받아 보여 준다.
const DP={form:null,name:'',cal:'solar',y:0,m:0,d:0,leap:false,step:'year',decade:1990,cache:{}};
const NOW=new Date(),THIS_Y=NOW.getFullYear(),MIN_Y=1900;
const WK=['일','월','화','수','목','금','토'];
function dpF(form,name){
  const n2=name==='birth2'?'2':'';
  return {val:form.querySelector('input[name="'+name+'"]'),leap:form.querySelector('input[name="leap'+n2+'"]'),
    cal:form.querySelector('select[name="calendar'+n2+'"]'),btn:form.querySelector('[data-dp="'+name+'"]')};
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
document.addEventListener('change',async e=>{
  const sel=e.target.closest('select[data-cal]');
  if(sel){
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
    return;
  }
  const unk=e.target.closest('input[type="checkbox"][name^="unknown_time"]');
  if(unk){
    const t=unk.form.querySelector('input[name="'+(unk.name==='unknown_time2'?'birth2_time':'birth_time')+'"]');
    if(t) t.disabled=unk.checked;
  }
});
document.querySelectorAll('[data-dp]').forEach(b=>dpRefresh(b.form,b.dataset.dp));

// ---------------- 저장·공유
// 링크: 서버에 계산 결과(사실표)만 저장하고 /r/<id> 로 다시 연다.

// ---------------- 내 사주 바로 보기 (이 기기에 기억)
// '이 기기에 기억하기'를 켠 사람만 입력값을 이 브라우저(localStorage)에 둔다. 서버에는 저장하지 않는다.
// 같은 와이파이(같은 IP)를 쓰는 다른 사람에게 보이지 않도록 IP 가 아니라 기기별로 둔다.
const PEOPLE_KEY='saju.people',PEOPLE_MAX=6;
const P_FIELDS=['birth','leap','calendar','birth_time','unknown_time','sex','city','zi'];
try{localStorage.removeItem('saju.recent');}catch(_){}      // 예전 '최근 저장한 결과' 목록은 없앴다
// ---- 잠금 (PIN): 저장한 사람 목록을 PIN 으로 암호화한다 (PBKDF2 20만 번 + AES-GCM).
// 같은 기기를 쓰는 사람이 PIN 없이 목록을 보지 못하게 하는 용도. 브라우저 암호화는 https·localhost 에서만 된다.
const LOCK_KEY='saju.people.lock';
const canLock=!!(window.crypto&&crypto.subtle);
S.pin=null;S.pcache=null;
let sealSeq=0;
function lockBlob(){try{return JSON.parse(localStorage.getItem(LOCK_KEY)||'null');}catch(_){return null;}}
function isLocked(){return !!lockBlob();}
const b64=u=>btoa(String.fromCharCode(...new Uint8Array(u)));
const ub64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function pinKey(pin,salt){
  const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(pin),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:200000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
}
async function sealPeople(list,pin){
  const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
  const ct=await crypto.subtle.encrypt({name:'AES-GCM',iv},await pinKey(pin,salt),new TextEncoder().encode(JSON.stringify(list)));
  return {v:1,salt:b64(salt),iv:b64(iv),ct:b64(ct)};
}
async function openPeople(blob,pin){
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:ub64(blob.iv)},await pinKey(pin,ub64(blob.salt)),ub64(blob.ct));
  return JSON.parse(new TextDecoder().decode(pt));
}
function saveSealed(list){
  const my=++sealSeq;
  return sealPeople(list,S.pin).then(b=>{if(my===sealSeq){try{localStorage.setItem(LOCK_KEY,JSON.stringify(b));}catch(_){}}});
}
const PIN_OK=/^\d{4,8}$/;
function people(){
  if(isLocked()) return (S.pcache||[]).filter(x=>x&&x.q&&x.q.birth);     // 잠겨 있으면 PIN 으로 연 뒤에만 보인다
  try{const l=JSON.parse(localStorage.getItem(PEOPLE_KEY)||'[]');return Array.isArray(l)?l.filter(x=>x&&x.q&&x.q.birth):[];}
  catch(_){return [];}
}
function peopleSet(l){
  l=l.slice(0,PEOPLE_MAX);
  if(isLocked()){if(!S.pin) return false;S.pcache=l;saveSealed(l);return true;}
  try{localStorage.setItem(PEOPLE_KEY,JSON.stringify(l));return true;}catch(_){return false;}
}
function personKey(q){return [q.birth,q.leap||'',q.calendar,q.unknown_time?'':q.birth_time,q.sex,q.city].join('|');}
function peopleSave(nick,q){
  const p={};P_FIELDS.forEach(k=>{if(q[k]!=null&&q[k]!=='') p[k]=q[k];});
  const key=personKey(p),l=people().filter(x=>personKey(x.q)!==key&&x.nick!==nick);
  l.unshift({nick,q:p});
  return peopleSet(l);
}
function renderPeople(){
  const box=$('people');
  if(isLocked()&&!S.pcache){                        // 잠겨 있고 아직 안 연 상태: PIN 칸만 보인다
    box.innerHTML='<div class="card"><h4 class="ppl-h">내 사주 바로 보기 🔒</h4>'+
      (canLock?'<div class="pin-row"><input type="password" id="pinIn" inputmode="numeric" maxlength="8" placeholder="PIN" aria-label="PIN" autocomplete="off">'+
        '<button type="button" class="go" id="pinOpen">열기</button></div><div id="pinMsg" class="fine"></div>':
        '<p class="fine">잠긴 목록은 https 주소나 이 컴퓨터(localhost)에서 열었을 때만 풀 수 있어.</p>')+
      '<p class="fine" style="margin-top:6px"><button type="button" class="linkbtn" id="pinForgot">PIN을 잊었어 (저장한 사람 모두 지우기)</button></p></div>';
    return;
  }
  const l=people();
  if(!l.length&&!isLocked()){box.innerHTML='';return;}
  const act=isLocked()?'<button type="button" class="linkbtn" id="lockClose">다시 잠그기</button> · <button type="button" class="linkbtn" id="lockOff">잠금 풀기</button>':
    canLock?'<button type="button" class="linkbtn" id="lockStart">🔒 PIN 잠금 걸기</button>':
    '<span>잠금은 https 주소나 이 컴퓨터(localhost)에서 열었을 때만 걸 수 있어.</span>';
  box.innerHTML='<div class="card"><h4 class="ppl-h">내 사주 바로 보기'+(isLocked()?' 🔓':'')+'</h4><div class="ppl">'+
    l.map((x,i)=>'<div class="ppl-row"><button type="button" class="ppl-go" data-pi="'+i+'"><b>'+esc(x.nick)+'</b>'+
      '<small>눌러서 바로 보기</small></button>'+
      '<button type="button" class="ppl-del" data-pdel="'+i+'" aria-label="'+esc(x.nick)+' 지우기">지우기</button></div>').join('')+
    '</div><p class="fine">생년월일은 화면에 보이지 않게 숨겨 뒀어. 이 기기(브라우저)에만 저장돼 있고, '+
    (isLocked()?'PIN으로 잠겨 있어.':'잠금을 걸면 같은 기기를 쓰는 사람도 PIN 없이는 못 봐.')+'</p>'+
    '<p class="fine ppl-act">'+act+'</p><div id="lockForm"></div></div>';
}
async function pinUnlock(){
  const pin=($('pinIn')||{}).value||'',msg=$('pinMsg');
  if(!PIN_OK.test(pin)){msg.textContent='숫자 4~8자리로 넣어 줘.';return;}
  msg.textContent='여는 중...';
  try{S.pcache=await openPeople(lockBlob(),pin);S.pin=pin;renderPeople();}
  catch(_){msg.textContent='PIN이 달라.';}
}
async function pinLock(){
  const a=$('pinNew').value,b=$('pinNew2').value,msg=$('lockMsg');
  if(!PIN_OK.test(a)){msg.textContent='숫자 4~8자리로 정해 줘 (6자리 이상을 권해).';return;}
  if(a!==b){msg.textContent='두 PIN이 달라.';return;}
  const l=people();
  try{
    const blob=await sealPeople(l,a);
    localStorage.setItem(LOCK_KEY,JSON.stringify(blob));localStorage.removeItem(PEOPLE_KEY);
    S.pin=a;S.pcache=l;renderPeople();
  }catch(_){msg.textContent='잠금을 걸지 못했어.';}
}
// 저장한 값으로 입력칸을 채운다. n: 나는 '', 궁합 상대는 '2'
function fillForm(form,q,n){
  const set=(name,v)=>{const el=form.querySelector('[name="'+name+'"]');if(el&&v!=null) el.value=v;};
  const tname=n?'birth2_time':'birth_time';
  set('birth'+n,q.birth);set('leap'+n,q.leap||'');set('calendar'+n,q.calendar||'solar');
  set(tname,q.birth_time||'12:00');set('sex'+n,q.sex||'male');set('city'+n,q.city||'서울');
  if(!n) set('zi',q.zi||'next');
  const u=form.querySelector('[name="unknown_time'+n+'"]'),t=form.querySelector('[name="'+tname+'"]');
  if(u){u.checked=!!q.unknown_time;if(t) t.disabled=u.checked;}
  const b=form.querySelector('[name="birth'+n+'"]');if(b) delete b.dataset.ym;
  dpRefresh(form,'birth'+n);
}
function toggleNick(){
  const f=$('fMain'),rm=f.querySelector('[name="remember"]');
  if(rm.checked&&isLocked()&&!S.pcache){
    rm.checked=false;$('homeErr').innerHTML='<div class="err">잠긴 목록에 추가하려면 위에서 PIN으로 먼저 열어 줘.</div>';
  }
  const on=rm.checked,nk=f.querySelector('[name="nick"]');
  nk.hidden=!on;
  if(on&&!nk.value&&!people().length) nk.value='나';
}
$('fMain').querySelector('[name="remember"]').addEventListener('change',toggleNick);
$('people').addEventListener('keydown',e=>{if(e.target.id==='pinIn'&&e.key==='Enter'){e.preventDefault();pinUnlock();}});
$('people').addEventListener('click',e=>{
  const id=e.target.id;
  if(id==='pinOpen') return void pinUnlock();
  if(id==='lockStart'){
    $('lockForm').innerHTML='<div class="pin-row"><input type="password" id="pinNew" inputmode="numeric" maxlength="8" placeholder="새 PIN (숫자 4~8자리)" autocomplete="new-password">'+
      '<input type="password" id="pinNew2" inputmode="numeric" maxlength="8" placeholder="한 번 더" autocomplete="new-password">'+
      '<button type="button" class="go" id="lockDo">걸기</button></div><div id="lockMsg" class="fine">PIN은 서버로 보내지 않고, 잊으면 저장한 사람을 되살릴 수 없어.</div>';
    return;
  }
  if(id==='lockDo') return void pinLock();
  if(id==='lockClose'){S.pin=null;S.pcache=null;renderPeople();return;}
  if(id==='lockOff'){
    try{localStorage.setItem(PEOPLE_KEY,JSON.stringify(S.pcache||[]));localStorage.removeItem(LOCK_KEY);}catch(_){}
    S.pin=null;S.pcache=null;renderPeople();return;
  }
  if(id==='pinForgot'){
    const b=e.target;
    if(b.dataset.sure!=='1'){b.dataset.sure='1';b.textContent='정말 모두 지울까? (되살릴 수 없어)';return;}
    try{localStorage.removeItem(LOCK_KEY);}catch(_){}
    S.pin=null;S.pcache=null;renderPeople();return;
  }
  const go=e.target.closest('[data-pi]'),del=e.target.closest('[data-pdel]');
  if(go){
    const l=people(),i=+go.dataset.pi,x=l[i];if(!x) return;
    l.splice(i,1);l.unshift(x);peopleSet(l);          // 방금 연 사람을 맨 위로
    const f=$('fMain');fillForm(f,x.q,'');
    f.querySelector('[name="remember"]').checked=false;toggleNick();
    f.requestSubmit?f.requestSubmit():f.querySelector('.go').click();
    return;
  }
  if(del){
    if(del.dataset.sure!=='1'){del.dataset.sure='1';del.textContent='정말 지울까?';del.classList.add('sure');return;}
    const l=people();l.splice(+del.dataset.pdel,1);peopleSet(l);renderPeople();
  }
});
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-p2]');
  if(!b) return;
  const x=people()[+b.dataset.p2];
  if(x&&$('fMatch')) fillForm($('fMatch'),x.q,'2');
});
function openSheet(){$('sheet').classList.add('on');$('shScrim').classList.add('on');$('shLinkOut').innerHTML='';$('shCardOut').innerHTML='';}
function closeSheet(){$('sheet').classList.remove('on');$('shScrim').classList.remove('on');}
$('btnShare').addEventListener('click',openSheet);
$('shClose').addEventListener('click',closeSheet);
$('shScrim').addEventListener('click',closeSheet);
$('shLink').addEventListener('click',async()=>{
  const b=$('shLink');b.disabled=true;
  try{
    const j=S.shareId?{id:S.shareId,path:'/r/'+S.shareId}:await postJSON('/api/v2/share',{token:S.token});
    S.shareId=j.id;
    const url=location.origin+j.path,f=S.facts;
    $('shLinkOut').innerHTML='<div class="linkbox"><input readonly value="'+esc(url)+'"><button class="ghost" type="button" id="shCopy">복사</button></div>'+
      '<p class="fine">이 주소로 언제든 다시 열 수 있어. 오늘 운세 부분은 저장한 날('+esc(f.meta.target)+') 기준이야.</p>';
    $('shCopy').onclick=async()=>{try{await navigator.clipboard.writeText(url);$('shCopy').textContent='복사됨';}catch(_){$('shLinkOut').querySelector('input').select();}};
  }catch(e){$('shLinkOut').innerHTML='<div class="err">'+esc(e.message)+'</div>';}
  finally{b.disabled=false;}
});
function cardInfo(){
  const f=S.facts,t=f.today,tab=S.tab,o=S.outline[tab]||TOOLS[tab]||{title:'종합 사주',hand:''};
  const chips=['일주 '+f.natal.day_pillar,...(t.keywords||[]).slice(0,2)];
  if(tab==='today') return {title:o.title,hand:o.hand,score:t.scores.total,head:t.heads.total,
    lines:['연애 '+t.scores.love+' · 직장 '+t.scores.career+' · 금전 '+t.scores.money,t.focus],chips};
  if(t.domains[tab]){const d=t.domains[tab];return {title:o.title,hand:o.hand,score:d.score,head:d.head,lines:d.reasons.slice(0,2),chips};}
  if(tab==='life'){const c=f.natal.ilju;return {title:c.pillar+' 일주',hand:c.title,score:null,head:f.natal.character.split('. ')[0]+'.',
    lines:[f.natal.geguk_mean,'요즘 부르는 말: '+c.modern],chips:['십이운성 '+c.stage,f.natal.strength,...c.marks.map(m=>m.name)].slice(0,4)};}
  if(tab==='newyear'){const ny=f.newyear;return {title:ny.year+' '+ny.ganzhi+'년',hand:'New Year',score:null,head:ny.rel,
    lines:['연애 '+ny.signals.love.tag+' · 일 '+ny.signals.career.tag+' · 돈 '+ny.signals.money.tag],chips:['만 '+ny.age+'세','나에게 '+ny.god.split('(')[0]]};}
  const r=$('toolOut')&&$('toolOut').querySelector('.ring span');
  return {title:o.title,hand:o.hand,score:r?+r.textContent:null,
    head:($('toolOut')&&$('toolOut').querySelector('.gauge b, .gauge div div'))?.textContent||o.sub||'',lines:[],chips};
}
function openSheetGold(){const g=$('shGold');if(g) g.hidden=!goldenInfo();}
$('btnShare').addEventListener('click',openSheetGold);
$('shGold').addEventListener('click',()=>{
  const info=goldenInfo();if(!info) return;
  shareCard(info).toBlob(blob=>{
    const url=URL.createObjectURL(blob);
    $('shCardOut').innerHTML='<img class="card-preview" src="'+url+'" alt="골든타임 카드 미리보기">'+
      '<a class="go dl" href="'+url+'" download="saju-golden-time.png">이미지 내려받기</a>';
  },'image/png');
});
$('shCard').addEventListener('click',()=>{
  const c=shareCard(cardInfo());
  c.toBlob(async blob=>{
    const file=new File([blob],'saju-'+S.tab+'.png',{type:'image/png'});
    if(navigator.canShare&&navigator.canShare({files:[file]})){
      try{await navigator.share({files:[file],title:'종합 사주'});return;}catch(_){}
    }
    const url=URL.createObjectURL(blob);
    $('shCardOut').innerHTML='<img class="card-preview" src="'+url+'" alt="공유 카드 미리보기">'+
      '<a class="go dl" href="'+url+'" download="saju-'+S.tab+'.png">이미지 내려받기</a>';
  },'image/png');
});
// 저장 링크로 들어오면 그 결과를 연다
(async function openShared(){
  renderPeople();
  const m=location.pathname.match(/^\/r\/([A-Za-z0-9_-]{8,16})$/);
  if(!m) return;
  try{
    const j=await postJSON('/api/v2/shared',{id:m[1]});
    Object.assign(S,{token:j.token,facts:j.facts,outline:j.outline,rules:j.rules||{},ai:j.ai,chatOn:!!j.chat,shareId:m[1],pastAns:{},
      chapters:{},chat:[],queue:[],inflight:new Set(),tab:'today',person:null});
    showResult();
  }catch(e){$('homeErr').innerHTML='<div class="err">'+esc(e.message)+'</div>';}
})();

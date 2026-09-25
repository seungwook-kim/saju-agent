// 종합 사주 · 그림 부품 (GPU 없이 SVG·캔버스로 그린다)
// - 자미두수 12궁 명반, 점성 출생 차트 원, 오행 상생도, 탭 머리 그림, 공유용 이미지 카드
'use strict';

const MAIN14=['자미','천기','태양','무곡','천동','염정','천부','태음','탐랑','거문','천상','천량','칠살','파군'];
const HUA_CLS={'록':'h-rok','권':'h-gwon','과':'h-gwa','기':'h-gi'};
const EL_COLOR={목:'#2f9e5d',화:'#e0503a',토:'#b7852c',금:'#8a8f98',수:'#2f6fc6'};

// ---------------- 자미두수 명반 (전통 배치: 위 사오미신, 오른쪽 유술, 아래 해자축인, 왼쪽 묘진)
const PAL_POS={사:[0,0],오:[0,1],미:[0,2],신:[0,3],진:[1,0],유:[1,3],묘:[2,0],술:[2,3],인:[3,0],축:[3,1],자:[3,2],해:[3,3]};
function mingpan(zw,meta){
  if(!zw) return '<div class="card"><p class="fine" style="margin:0">태어난 시간을 몰라 자미두수 명반은 그리지 않았어.</p></div>';
  let cells='';
  zw.palaces.forEach(p=>{
    const [r,c]=PAL_POS[p.branch]||[0,0];
    const mains=p.stars.filter(s=>MAIN14.includes(s)),minors=p.stars.filter(s=>!MAIN14.includes(s));
    const hua=Object.entries(p.hua||{}).map(([s,h])=>'<span class="hua '+(HUA_CLS[h]||'')+'" title="'+esc(s)+' 화'+esc(h)+'">'+esc(h)+'</span>').join('');
    cells+='<div class="pal'+(p.now_daxian?' now':'')+(p.name==='명궁'?' ming':'')+'" style="grid-row:'+(r+1)+';grid-column:'+(c+1)+'">'+
      '<div class="pal-top"><b>'+esc(p.name.replace('(배우자)',''))+'</b>'+(p.liunian?'<span class="yr">올해</span>':'')+'</div>'+
      '<div class="pal-main">'+(mains.length?mains.map(esc).join(' '):'<span class="sm">주성 없음</span>')+hua+'</div>'+
      '<div class="pal-min">'+minors.slice(0,4).map(esc).join(' ')+'</div>'+
      '<div class="pal-bot"><span>'+esc(p.ganzhi)+'</span><span>'+(p.daxian?p.daxian[0]+'~'+p.daxian[1]:'')+'</span></div></div>';
  });
  const guo=(zw.guo||'').split(' · ');
  cells+='<div class="pal-center"><b>자미두수 명반</b>'+guo.map(x=>'<span>'+esc(x)+'</span>').join('')+
    '<span class="fine">테두리 굵은 칸 = 지금 10년(대한, 세는나이 '+meta.age_kr+'세) · 올해 = 유년 명궁</span></div>';
  return '<div class="card mingpan-card"><div class="mingpan">'+cells+'</div>'+
    '<div class="legend"><span class="hua h-rok">록</span>복이 붙음 <span class="hua h-gwon">권</span>힘이 실림 '+
    '<span class="hua h-gwa">과</span>이름이 남 <span class="hua h-gi">기</span>막힘이 걸림 (태어난 해의 사화)</div></div>';
}

// ---------------- 점성 출생 차트 원
const SIGN_SHORT=['양','황소','쌍둥이','게','사자','처녀','천칭','전갈','사수','염소','물병','물고기'];
const SIGN_EL=['불','흙','공기','물','불','흙','공기','물','불','흙','공기','물'];
const SIGN_EL_COLOR={불:'#fde2dc',흙:'#f3ead8',공기:'#e3eefb',물:'#dff1ee'};
const BODY_COLOR={sun:'#e8a100',moon:'#8a8f98',mercury:'#7c6f79',venus:'#d6456d',mars:'#e0503a',jupiter:'#7652c6',saturn:'#3b4f6b'};
const ASP_COLOR={'삼합':'#2a9a6e','육합':'#3b77c9','형':'#e0503a','충':'#c2413b'};
function wheel(w){
  const S=340,cx=S/2,cy=S/2,R1=160,R2=128,R3=98;
  const asc=w.asc==null?0:w.asc;
  const pt=(lon,r)=>{const t=Math.PI+(lon-asc)*Math.PI/180;return [cx+r*Math.cos(t),cy-r*Math.sin(t)];};
  let g='';
  for(let i=0;i<12;i++){           // 별자리 칸
    const a0=i*30,a1=a0+30,[x0,y0]=pt(a0,R1),[x1,y1]=pt(a1,R1),[x2,y2]=pt(a1,R2),[x3,y3]=pt(a0,R2);
    g+='<path d="M'+x0+' '+y0+' A'+R1+' '+R1+' 0 0 0 '+x1+' '+y1+' L'+x2+' '+y2+' A'+R2+' '+R2+' 0 0 1 '+x3+' '+y3+'Z" fill="'+SIGN_EL_COLOR[SIGN_EL[i]]+'" stroke="#fff" stroke-width="2"/>';
    const [tx,ty]=pt(a0+15,(R1+R2)/2);
    g+='<text x="'+tx+'" y="'+ty+'" class="w-sign">'+SIGN_SHORT[i]+'</text>';
  }
  g+='<circle cx="'+cx+'" cy="'+cy+'" r="'+R3+'" fill="#fff" stroke="#eee"/>';
  const byKey={};
  const placed=[];                  // 가까운 행성은 안쪽으로 밀어 겹치지 않게
  w.bodies.slice().sort((a,b)=>a.lon-b.lon).forEach(b=>{
    let r=R2-16;
    while(placed.some(p=>Math.abs(((p.lon-b.lon+540)%360)-180)<9&&p.r===r)) r-=20;
    placed.push({lon:b.lon,r});byKey[b.key]={b,r};
  });
  w.aspects.forEach(a=>{
    if(!ASP_COLOR[a.type]) return;
    const [x0,y0]=pt(byKey[a.a].b.lon,R3-4),[x1,y1]=pt(byKey[a.b].b.lon,R3-4);
    g+='<line x1="'+x0+'" y1="'+y0+'" x2="'+x1+'" y2="'+y1+'" stroke="'+ASP_COLOR[a.type]+'" stroke-width="1.4" opacity=".7"/>';
  });
  Object.values(byKey).forEach(({b,r})=>{
    const [x,y]=pt(b.lon,r),[tx,ty]=pt(b.lon,R3-4);
    g+='<line x1="'+tx+'" y1="'+ty+'" x2="'+x+'" y2="'+y+'" stroke="#ddd"/>'+
      '<circle cx="'+x+'" cy="'+y+'" r="11" fill="'+BODY_COLOR[b.key]+'"/>'+
      '<text x="'+x+'" y="'+y+'" class="w-body">'+esc(b.name.slice(0,1))+'</text>'+
      (b.retro?'<text x="'+(x+13)+'" y="'+(y-9)+'" class="w-retro">R</text>':'');
  });
  if(w.asc!=null){const [x,y]=pt(asc,R1+4);g+='<text x="'+(x-2)+'" y="'+y+'" class="w-asc">ASC</text>';}
  const legend=w.bodies.map(b=>'<span><i style="background:'+BODY_COLOR[b.key]+'"></i>'+esc(b.name)+' '+esc(b.sign)+(b.retro?' (역행)':'')+'</span>').join('');
  return '<div class="card"><svg class="wheel" viewBox="-34 -6 '+(S+40)+' '+(S+12)+'" role="img" aria-label="출생 차트">'+g+'</svg>'+
    '<div class="w-legend">'+legend+'</div><div class="legend"><span class="ln" style="background:#2a9a6e"></span>삼합 '+
    '<span class="ln" style="background:#3b77c9"></span>육합 (순한 각도) <span class="ln" style="background:#e0503a"></span>형·충 (맞서는 각도)'+
    (w.asc==null?'<br>태어난 시간을 몰라 상승점 없이 양자리를 왼쪽에 두고 그렸어.':'')+'</div></div>';
}

// ---------------- 오행 상생도 (목→화→토→금→수→목)
function ohaeng(el){
  const order=['목','화','토','금','수'],S=240,cx=120,cy=124,R=84;
  const pos=order.map((e,i)=>{const t=-Math.PI/2+i*2*Math.PI/5;return [cx+R*Math.cos(t),cy+R*Math.sin(t)];});
  let g='<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#ccc"/></marker></defs>';
  for(let i=0;i<5;i++){               // 상생 화살표
    const [x0,y0]=pos[i],[x1,y1]=pos[(i+1)%5],k=0.28;
    g+='<line x1="'+(x0+(x1-x0)*k)+'" y1="'+(y0+(y1-y0)*k)+'" x2="'+(x1-(x1-x0)*k)+'" y2="'+(y1-(y1-y0)*k)+'" stroke="#ccc" stroke-width="2" marker-end="url(#arr)"/>';
  }
  const max=Math.max(1,...order.map(e=>el[e]||0));
  order.forEach((e,i)=>{
    const n=el[e]||0,r=14+14*n/max,[x,y]=pos[i];
    g+='<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+EL_COLOR[e]+'" opacity="'+(n?0.9:0.18)+'"/>'+
      '<text x="'+x+'" y="'+(y-1)+'" class="o-name">'+e+'</text><text x="'+x+'" y="'+(y+13)+'" class="o-n">'+n+'</text>';
  });
  const none=order.filter(e=>!el[e]),big=order.filter(e=>el[e]===max&&max>=3);
  const note=(none.length?none.join('·')+' 기운이 비어 있고':'다섯 기운이 모두 있고')+(big.length?', '+big.join('·')+' 기운이 가장 많아.':'.');
  return '<div class="ohaeng"><svg viewBox="0 0 '+S+' '+S+'" role="img" aria-label="오행 분포">'+g+'</svg>'+
    '<p class="fine">원은 여덟 글자 속 오행 개수, 화살표는 서로 살려 주는 순서(상생)야. '+esc(note)+'</p></div>';
}

// ---------------- 탭 머리 그림 (단색 선 그림, 테마 색을 따른다)
const HERO_ART={
  today:'<circle cx="60" cy="44" r="18"/><g>'+[0,45,90,135,180,225,270,315].map(a=>{const t=a*Math.PI/180;return '<line x1="'+(60+26*Math.cos(t))+'" y1="'+(44+26*Math.sin(t))+'" x2="'+(60+34*Math.cos(t))+'" y2="'+(44+34*Math.sin(t))+'"/>';}).join('')+'</g>',
  love:'<path d="M60 74 C20 48 30 18 50 22 C56 23 59 28 60 32 C61 28 64 23 70 22 C90 18 100 48 60 74Z"/><path d="M96 30 C88 24 90 14 96 16 C98 16 99 18 100 19 C101 18 102 16 104 16 C110 14 112 24 104 30 L100 33Z" class="soft"/>',
  career:'<rect x="30" y="34" width="60" height="38" rx="6"/><path d="M48 34 V26 H72 V34"/><line x1="30" y1="50" x2="90" y2="50"/>',
  money:'<ellipse cx="50" cy="60" rx="22" ry="8"/><path d="M28 60 V50 M72 60 V50"/><ellipse cx="50" cy="50" rx="22" ry="8"/><ellipse cx="74" cy="36" rx="18" ry="7" class="soft"/><path d="M56 36 V28 M92 36 V28" class="soft"/><ellipse cx="74" cy="28" rx="18" ry="7" class="soft"/>',
  life:'<path d="M14 74 L44 34 L60 52 L76 30 L106 74Z"/><circle cx="92" cy="20" r="7" class="soft"/>',
  match:'<circle cx="46" cy="46" r="22"/><circle cx="74" cy="46" r="22" class="soft"/>',
  pick:'<rect x="30" y="24" width="60" height="50" rx="6"/><line x1="30" y1="38" x2="90" y2="38"/><path d="M44 18 V30 M76 18 V30"/><path d="M50 56 l7 7 l14 -16" class="soft"/>',
};
function heroArt(tab){
  const a=HERO_ART[tab];
  return a?'<svg class="hero-art" viewBox="0 0 120 84" aria-hidden="true">'+a+'</svg>':'';
}

// ---------------- 공유용 이미지 카드 (캔버스, 1080x1350)
function themeColors(){
  const cs=getComputedStyle(document.body);
  return {bg:cs.getPropertyValue('--bg').trim(),bg2:cs.getPropertyValue('--bg2').trim(),
    accent:cs.getPropertyValue('--accent').trim(),accent2:cs.getPropertyValue('--accent2').trim()};
}
function wrapText(ctx,text,x,y,maxW,lh,maxLines){
  // 글자 단위로 줄을 나누고, 줄 수를 넘으면 마지막 줄 끝을 말줄임표로 바꾼다
  const lines=[];let line='';
  for(const ch of String(text)){
    if(ctx.measureText(line+ch).width>maxW){lines.push(line);line=ch;}
    else line+=ch;
  }
  if(line) lines.push(line);
  const shown=lines.slice(0,maxLines);
  if(lines.length>maxLines){
    let last=shown[maxLines-1];
    while(last&&ctx.measureText(last+'…').width>maxW) last=last.slice(0,-1);
    shown[maxLines-1]=last+'…';
  }
  shown.forEach(l=>{ctx.fillText(l,x,y);y+=lh;});
  return y;
}
function shareCard(info){
  // info: {title, hand, score|null, head, lines[], chips[]}
  const W=1080,H=1350,c=document.createElement('canvas');c.width=W;c.height=H;
  const x=c.getContext('2d'),col=themeColors(),font='"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif';
  const g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,col.bg);g.addColorStop(1,col.bg2);
  x.fillStyle=g;x.fillRect(0,0,W,H);
  x.fillStyle='#fff';x.beginPath();x.roundRect(60,60,W-120,H-120,48);x.fill();
  x.textAlign='center';x.fillStyle=col.accent;x.font='800 40px '+font;x.fillText('종합 사주',W/2,150);
  x.fillStyle='#2b2230';x.font='900 72px '+font;x.fillText(info.title,W/2,250);
  x.fillStyle=col.accent;x.font='italic 700 54px "Segoe Script","Brush Script MT",cursive';x.fillText(info.hand,W/2,320);
  let y=380;
  if(info.score!=null){
    const cx=W/2,cy=y+150,r=130;
    x.lineWidth=34;x.strokeStyle=col.bg2;x.beginPath();x.arc(cx,cy,r,0,Math.PI*2);x.stroke();
    x.strokeStyle=col.accent;x.lineCap='round';x.beginPath();x.arc(cx,cy,r,-Math.PI/2,-Math.PI/2+Math.PI*2*info.score/100);x.stroke();
    x.fillStyle='#2b2230';x.font='900 110px '+font;x.textBaseline='middle';x.fillText(String(info.score),cx,cy+4);x.textBaseline='alphabetic';
    y=cy+r+90;
  }
  x.fillStyle='#2b2230';x.font='800 46px '+font;y=wrapText(x,info.head,W/2,y,W-220,62,3);
  x.fillStyle='#5b4f58';x.font='500 36px '+font;y+=10;
  (info.lines||[]).slice(0,4).forEach(l=>{y=wrapText(x,l,W/2,y,W-240,52,2)+6;});
  if(info.chips&&info.chips.length){
    x.font='700 34px '+font;let cw=info.chips.map(t=>x.measureText(t).width+56),tot=cw.reduce((a,b)=>a+b,0)+(cw.length-1)*18,cx0=(W-tot)/2;
    const cy=Math.min(y+30,H-230);
    info.chips.forEach((t,i)=>{x.fillStyle=col.bg;x.beginPath();x.roundRect(cx0,cy,cw[i],64,32);x.fill();
      x.fillStyle=col.accent;x.fillText(t,cx0+cw[i]/2,cy+44);cx0+=cw[i]+18;});
  }
  x.fillStyle='#a89aa4';x.font='500 28px '+font;x.fillText('사주·자미두수·점성술 계산으로 본 흐름이야 · 재미로 봐 줘',W/2,H-110);
  return c;
}

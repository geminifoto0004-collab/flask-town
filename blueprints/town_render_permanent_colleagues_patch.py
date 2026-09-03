"""Dedicated browser renderer for permanent TiDB colleagues beyond native slots.

The historical game canvas owns three mature native officer sprites. Permanent
colleagues added later must not depend on the generic visitor renderer's
lifecycle. This independent transparent layer reads /api/town/colleagues as its
authoritative roster and /api/town/world for presence, position and scripts.
"""


def patch_render_permanent_colleagues(html: str) -> str:
    if 'town-permanent-colleagues-runtime' in html:
        return html

    css = r'''
<style id="town-permanent-colleagues-style">
#town-permanent-colleague-overlay{position:absolute;inset:6px;width:calc(100% - 12px);height:calc(100% - 12px);pointer-events:none;image-rendering:pixelated;image-rendering:crisp-edges;z-index:14;background:transparent!important}
</style>
'''

    js = r'''
<script id="town-permanent-colleagues-runtime">
(()=>{
  const app=document.getElementById('customs-sim');
  const wrap=app&&app.querySelector('.game-wrap');
  const base=app&&app.querySelector('.game-wrap canvas');
  if(!app||!wrap||!base)return;

  let canvas=document.getElementById('town-permanent-colleague-overlay');
  if(!canvas){canvas=document.createElement('canvas');canvas.id='town-permanent-colleague-overlay';canvas.width=640;canvas.height=400;wrap.appendChild(canvas);}
  const c=canvas.getContext('2d');if(!c)return;c.imageSmoothingEnabled=false;

  const people=new Map();
  const nativeIds=new Set();
  const nativePos=new Map();
  let refreshing=false,last=performance.now(),lastRosterKey='';
  window.__townPermanentColleagueIds=new Set();

  function log(text){const box=app.querySelector('#eventLog');if(!box)return;const d=document.createElement('div');d.textContent='> '+text;box.appendChild(d);box.scrollTop=box.scrollHeight;}
  function px(x,y,w,h,color){c.fillStyle=color;c.fillRect(Math.round(x/2)*2,Math.round(y/2)*2,Math.max(2,Math.round(w/2)*2),Math.max(2,Math.round(h/2)*2));}
  function isFemale(value){const g=String(value||'').trim().toLowerCase();return g==='f'||g==='female'||g==='mujer'||g==='femenino'||g==='女'||g.includes('female')||g.includes('mujer');}
  function hourFromWorld(world){
    const text=String(world&&world.iquiqueTime||world&&world.now||'');
    const m=text.match(/T(\d{2}):/);if(m)return Number(m[1]);
    return new Date().getHours();
  }
  function isNight(world){const h=hourFromWorld(world);return h>=20||h<7;}
  function targetPos(id){
    const key=String(id||'').toUpperCase();
    if(people.has(key)){const p=people.get(key);return {x:p.x,y:p.y};}
    return nativePos.get(key)||null;
  }
  function moveToward(p,t,speed,dt){const dx=t.x-p.x,dy=t.y-p.y,d=Math.hypot(dx,dy);if(d<2){p.x=t.x;p.y=t.y;return true;}const step=Math.min(d,Math.max(10,speed)*dt);p.x+=dx/d*step;p.y+=dy/d*step;return false;}
  function stepId(s){return String(s&&s.stepId||s&&s.id||'');}
  function randomOfficeTarget(){
    // Stay inside the office floor and avoid the sea/harbor strip. The native
    // office uses roughly x=92..548, y=138..258 for safe walking space.
    return {x:105+Math.random()*430,y:150+Math.random()*96};
  }
  function planIdle(p){
    if(!p.visible||p.current||p.queue.length)return;
    p.idleTimer=6+Math.random()*14;
    p.idleTarget=randomOfficeTarget();
    p.idleSpeed=18+Math.random()*12;
  }
  function startStep(p,s){
    // Any server/AI command immediately owns the actor and cancels free-roam.
    p.idleTarget=null;p.idleTimer=4+Math.random()*8;
    p.current={...s,elapsed:0};const kind=String(s&&s.type||'');
    if(kind==='move_entity'){
      const t=targetPos(s.target);
      const tx=t?t.x:(Number.isFinite(Number(s.x))?Number(s.x):p.x);
      const ty=t?t.y:(Number.isFinite(Number(s.y))?Number(s.y):p.y);
      p.current.target={x:tx,y:ty};p.current.speed=Number(s.speed)||38;
    }else if(kind==='say'){
      const zh=document.getElementById('dialogueLangSelect')?.value!=='es';
      p.speech=String(zh&&(s.text_zh||s.textZh)?(s.text_zh||s.textZh):(s.text||''));
      p.current.duration=Math.max(4,Math.min(12,2.8+p.speech.length*.08));
    }else if(kind==='wait')p.current.duration=Math.max(.5,Math.min(120,Number(s.seconds)||1));
    else if(kind==='leave'){p.current.target={x:620,y:292};p.current.speed=44;}
  }
  function finishStep(p){const s=p.current;if(!s)return;const id=stepId(s);if(id)p.done.add(id);if(s.type==='say')p.speech='';if(s.type==='leave')p.visible=false;p.current=null;p.idleTimer=4+Math.random()*10;}
  function tick(p,dt){
    if(!p.visible)return;
    // Server scripts always beat autonomous life.
    if(!p.current&&p.queue.length)startStep(p,p.queue.shift());
    const s=p.current;
    if(s){
      s.elapsed+=dt;
      if(s.type==='move_entity'||s.type==='leave'){if(!s.target||moveToward(p,s.target,s.speed||38,dt))finishStep(p);}
      else if(s.type==='say'||s.type==='wait'){if(s.elapsed>=Number(s.duration||1))finishStep(p);}
      else finishStep(p);
      return;
    }

    // Free local life for permanent colleagues. They wander only when idle and
    // visible; a new AI/admin script cancels this immediately on the next frame.
    p.idleTimer=(Number(p.idleTimer)||0)-dt;
    if(p.idleTarget){
      if(moveToward(p,p.idleTarget,p.idleSpeed||24,dt)){p.idleTarget=null;p.idleTimer=3+Math.random()*9;}
      return;
    }
    if(p.idleTimer<=0)planIdle(p);
  }
  function label(text,x,y){const t=String(text||'').toUpperCase();c.font='bold 7px monospace';const w=Math.max(32,Math.ceil(c.measureText(t).width)+8);px(x-w/2,y-35,w,10,'rgba(22,31,40,.9)');c.fillStyle='#fff';c.textAlign='center';c.fillText(t,Math.round(x),Math.round(y-27));}
  function bubble(p){if(!p.speech)return;c.font='8px sans-serif';const text=p.speech.slice(0,42),w=Math.min(210,Math.max(62,c.measureText(text).width+18));const x=Math.max(6,Math.min(640-w-6,p.x-w/2)),y=Math.max(6,p.y-70);px(x,y,w,23,'rgba(250,252,255,.96)');px(p.x-2,y+23,6,5,'rgba(250,252,255,.96)');c.fillStyle='#1d2730';c.textAlign='left';c.fillText(text,x+8,y+15);}
  function drawFemale(p,x,y,body,accent){
    // Original compact female office sprite: longer hair and slightly narrower
    // torso while preserving the same customs-office pixel scale/uniform.
    px(x-7,y+12,6,3,'#334454');px(x+2,y+12,6,3,'#334454');
    px(x-7,y+3,6,10,'#334454');px(x+2,y+3,6,10,'#334454');
    px(x-8,y-10,16,14,body);px(x-7,y-8,14,3,accent);
    px(x-8,y-25,16,5,'#4a352b');px(x-9,y-22,4,17,'#4a352b');px(x+5,y-22,4,17,'#4a352b');
    px(x-6,y-22,12,13,'#c99570');px(x-4,y-16,2,2,'#172126');px(x+3,y-16,2,2,'#172126');px(x-2,y-11,5,2,'#9a5d52');
    px(x-12,y-7,4,11,body);px(x+9,y-7,4,11,body);
  }
  function drawMale(p,x,y,body,accent){
    px(x-7,y+4,6,10,'#334454');px(x+2,y+4,6,10,'#334454');
    px(x-10,y-10,20,15,body);px(x-8,y-8,16,3,accent);px(x-7,y-23,14,14,'#c99570');px(x-9,y-25,18,5,'#4a352b');
    px(x-4,y-16,2,2,'#172126');px(x+3,y-16,2,2,'#172126');px(x-2,y-11,5,2,'#9a5d52');px(x-13,y-7,4,12,body);px(x+10,y-7,4,12,body);
  }
  function draw(p){
    if(!p.visible)return;const x=p.x,y=p.y,body=p.bodyColor||'#536f86',accent=p.accentColor||'#d4a74a';
    px(x-8,y+14,18,3,'rgba(0,0,0,.20)');
    if(p.female)drawFemale(p,x,y,body,accent);else drawMale(p,x,y,body,accent);
    label(p.name,x,y);bubble(p);
  }

  function merge(roster,world){
    const rows=Array.isArray(roster&&roster.characters)?roster.characters:[];
    const rosterKey=rows.map(r=>String(r&&r.id||'').toUpperCase()).filter(Boolean).join(',');
    if(rosterKey&&rosterKey!==lastRosterKey){lastRosterKey=rosterKey;log('正式同事(TiDB)：'+rosterKey);}
    const agents=Array.isArray(world&&world.agents)?world.agents:[];
    const generics=Array.isArray(world&&world.genericEntities)?world.genericEntities:[];
    const presence=world&&world.characterPresence&&typeof world.characterPresence==='object'?world.characterPresence:{};
    nativeIds.clear();rows.slice(0,3).forEach(r=>nativeIds.add(String(r&&r.id||'').toUpperCase()));
    nativePos.clear();agents.forEach(a=>{const id=String(a&&a.name||a&&a.slot||'').toUpperCase();if(id&&nativeIds.has(id))nativePos.set(id,{x:Number(a&&a.x)||320,y:Number(a&&a.y)||236});});
    const agentById=new Map(agents.map(a=>[String(a&&a.name||a&&a.slot||'').toUpperCase(),a||{}]));
    const genericById=new Map(generics.map(g=>[String(g&&g.id||'').toUpperCase(),g||{}]));
    const extras=rows.slice(3);
    const valid=new Set();
    const night=isNight(world);
    extras.forEach((row,index)=>{
      const id=String(row&&row.id||'').toUpperCase();if(!id)return;valid.add(id);
      const agent=agentById.get(id)||{};const generic=genericById.get(id)||null;const pr=presence[id]||{};
      const explicitlyOn=String(pr.dutyState||agent.dutyState||'')==='on';
      const explicitlyOff=String(pr.dutyState||agent.dutyState||'')==='off'||pr.manualOffDuty===true||agent.manualOffDuty===true;
      const nightShift=id===String(world&&world.nightShiftAgent||'').toUpperCase();
      const visible=!!generic||explicitlyOn||(!explicitlyOff&&(!night||nightShift));
      let p=people.get(id);
      const col=index%4,line=Math.floor(index/4);
      const raw=generic||agent;
      const seedX=Number.isFinite(Number(raw&&raw.x))?Number(raw.x):(135+col*115);
      const seedY=Number.isFinite(Number(raw&&raw.y))?Number(raw.y):(220+line*42);
      if(!p){p={id,name:String(row.name||id),gender:String(row.gender||''),female:isFemale(row.gender),x:seedX,y:seedY,bodyColor:'#536f86',accentColor:'#d4a74a',visible,queue:[],current:null,done:new Set(),speech:'',idleTimer:2+Math.random()*7,idleTarget:null,idleSpeed:24};people.set(id,p);}
      p.name=String(row.name||id);p.gender=String(row.gender||'');p.female=isFemale(row.gender);p.visible=visible;
      // Do not snap an existing colleague back to a server seed every poll;
      // local walking must remain smooth. Explicit movement arrives as script.
      const queued=new Set(p.queue.map(stepId));if(p.current)queued.add(stepId(p.current));
      (Array.isArray(generic&&generic.script)?generic.script:[]).forEach(s=>{const sid=stepId(s);if(sid&&!p.done.has(sid)&&!queued.has(sid)){p.queue.push({...s});queued.add(sid);}});
    });
    [...people.keys()].forEach(id=>{if(!valid.has(id))people.delete(id);});
    window.__townPermanentColleagueIds=new Set(valid);
    window.__townPermanentColleagueVisibleIds=()=>[...people.values()].filter(p=>p.visible).map(p=>p.id);
  }

  async function refresh(){
    if(refreshing)return;refreshing=true;
    try{
      const [rr,rw]=await Promise.all([
        fetch('/api/town/colleagues',{headers:{Accept:'application/json'},cache:'no-store'}),
        fetch('/api/town/world',{headers:{Accept:'application/json'},cache:'no-store'})
      ]);
      if(!rr.ok||!rw.ok)return;
      const roster=await rr.json(),wd=await rw.json();merge(roster,wd&&wd.world||{});
    }catch(_e){}finally{refreshing=false;}
  }
  function frame(now){const dt=Math.min(.05,(now-last)/1000);last=now;c.clearRect(0,0,640,400);people.forEach(p=>{tick(p,dt);draw(p);});requestAnimationFrame(frame);}
  refresh();setInterval(refresh,1800);requestAnimationFrame(frame);
  window.TOWN_PERMANENT_COLLEAGUE_RENDERER=true;
})();
</script>
'''

    if 'town-permanent-colleagues-style' not in html:
        html = html.replace('</head>', css + '</head>', 1) if '</head>' in html else css + html
    if 'town-permanent-colleagues-runtime' not in html:
        html = html.replace('</body>', js + '</body>', 1) if '</body>' in html else html + js
    return html

"""Render TiDB-owned core characters on the live game actor positions.

The historical browser snapshot still owns the mature movement/pathfinding loop.
This patch exposes that live actor array to a TiDB-driven presentation layer so
character identity can change without turning the new characters into static
billboards.  No story names are hardcoded here; TiDB/world order is mapped onto
legacy movement slots until the old renderer is fully retired.
"""


def patch_render_core_characters(html: str) -> str:
    expose = "try{window.__townVisualAgents=agents;}catch(_townExposeErr){}"
    anchors = [
        "function drawAgent(a){",
        "function drawOfficer(a){",
        "function updateAgent(a,dt){",
        "function updateOfficer(a,dt){",
    ]
    for anchor in anchors:
        if anchor in html:
            html = html.replace(anchor, anchor + expose, 1)
            break
    if "window.__townVisualAgents=agents" not in html:
        for anchor in ["agents.forEach(a=>{", "agents.forEach(a => {"]:
            if anchor in html:
                html = html.replace(anchor, expose + anchor, 1)
                break

    css = r'''
<style id="town-core-character-style">
#town-core-character-overlay{position:absolute;inset:6px;width:calc(100% - 12px);height:calc(100% - 12px);pointer-events:none;image-rendering:pixelated;image-rendering:crisp-edges;z-index:18;background:transparent!important}
</style>
'''
    js = r'''
<script id="town-core-character-runtime">
(()=>{
  const app=document.getElementById('customs-sim');
  const wrap=app&&app.querySelector('.game-wrap');
  if(!app||!wrap)return;
  let canvas=document.getElementById('town-core-character-overlay');
  if(!canvas){canvas=document.createElement('canvas');canvas.id='town-core-character-overlay';canvas.width=640;canvas.height=400;wrap.appendChild(canvas);}
  const c=canvas.getContext('2d');if(!c)return;c.imageSmoothingEnabled=false;
  let core=[];let refreshing=false;
  const motion=new Map();
  const fallback=[{x:96,y:236},{x:320,y:236},{x:500,y:236}];

  function px(x,y,w,h,color){c.fillStyle=color;c.fillRect(Math.round(x/2)*2,Math.round(y/2)*2,Math.max(2,Math.round(w/2)*2),Math.max(2,Math.round(h/2)*2));}
  function hash(s){let h=2166136261;for(const ch of String(s||'')){h^=ch.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
  function palette(id){const sets=[['#416b87','#d39b55'],['#765b8e','#c98958'],['#4f7b66','#c99a4d'],['#845b61','#5e7895'],['#596b87','#a86f62'],['#6b705c','#bb8854']];return sets[hash(id)%sets.length];}
  function profile(a){return (a&&a.profile&&typeof a.profile==='object')?a.profile:{};}
  function finite(v){return Number.isFinite(Number(v));}

  function liveActor(index,a){
    const live=Array.isArray(window.__townVisualAgents)?window.__townVisualAgents:[];
    if(live[index]&&finite(live[index].x)&&finite(live[index].y))return live[index];
    const id=String(a&&((a.id||a.characterId||a.name||a.slot))||'').toUpperCase();
    const hit=live.find(v=>String(v&&((v.id||v.characterId||v.name||v.slot))||'').toUpperCase()===id);
    return hit&&finite(hit.x)&&finite(hit.y)?hit:null;
  }

  function pose(index,a,now){
    const id=String(a&&((a.id||a.characterId||a.name||a.slot))||index);
    let m=motion.get(id);
    const live=liveActor(index,a);
    const fb=fallback[index%fallback.length];
    const tx=live?Number(live.x):(finite(a&&a.x)?Number(a.x):fb.x);
    const ty=live?Number(live.y):(finite(a&&a.y)?Number(a.y):fb.y);
    if(!m){m={x:tx,y:ty,lastX:tx,lastY:ty,lastAt:now,facing:'down',moving:false,step:0};motion.set(id,m);}
    const dx=tx-m.x,dy=ty-m.y,dist=Math.hypot(dx,dy);
    const gain=(live&&live.x!==undefined)?0.42:0.18;
    m.x+=dx*Math.min(1,gain);m.y+=dy*Math.min(1,gain);
    const vx=m.x-m.lastX,vy=m.y-m.lastY;
    m.moving=Math.hypot(vx,vy)>.12 || dist>1.2;
    if(Math.abs(vx)>Math.abs(vy)&&Math.abs(vx)>.05)m.facing=vx>0?'right':'left';
    else if(Math.abs(vy)>.05)m.facing=vy>0?'down':'up';
    if(m.moving)m.step+=.22;else m.step=0;
    m.lastX=m.x;m.lastY=m.y;m.lastAt=now;
    return m;
  }

  function label(a,x,y){
    const text=String(a.displayName||a.name||a.characterId||a.slot||'').toUpperCase();if(!text)return;
    c.font='bold 7px monospace';
    const w=Math.max(38,Math.ceil(c.measureText(text).width)+10);
    px(x-w/2-2,y-39,w+4,12,'rgba(18,27,34,.98)');
    c.fillStyle='#fff';c.textAlign='center';c.fillText(text,Math.round(x),Math.round(y-31));
  }

  function drawCharacter(a,index,now){
    const m=pose(index,a,now),x=m.x,y=m.y;
    const p=profile(a),id=String(a.name||a.characterId||a.slot||index);
    const gender=String(p.gender||a.gender||'').toLowerCase();
    const birth=Number(p.birthYear||a.birthYear||0),age=birth?new Date().getFullYear()-birth:35;
    const colors=palette(id),body=colors[0],accent=colors[1];
    const skin=age>=55?'#c79a79':'#d6a17d';
    const hair=age>=55?'#a7a39b':((hash(id)>>3)%2?'#3b2d26':'#241f22');
    const bob=m.moving?Math.round(Math.sin(m.step)*1.5):0;
    const stride=m.moving?(Math.sin(m.step)>0?2:-2):0;

    px(x-9,y+12,18,3,'rgba(0,0,0,.22)');
    px(x-8-stride/2,y+4+bob,7,10,'#2f4050');
    px(x+1+stride/2,y+4-bob,7,10,'#2f4050');
    px(x-11,y-10+bob,22,16,body);px(x-8,y-8+bob,16,3,accent);
    px(x-14,y-7+bob,5,12,body);px(x+10,y-7+bob,5,12,body);
    px(x-8,y-23+bob,16,14,skin);

    if(gender.includes('female')||gender.includes('mujer')||gender.includes('woman')){
      px(x-10,y-27+bob,20,6,hair);px(x-10,y-22+bob,4,15,hair);px(x+7,y-22+bob,4,15,hair);
    }else{
      px(x-10,y-27+bob,20,6,hair);px(x-9,y-23+bob,18,3,hair);
    }

    if(m.facing!=='up'){
      const eyeShift=m.facing==='left'?-2:(m.facing==='right'?2:0);
      px(x-5+eyeShift,y-16+bob,2,2,'#172126');px(x+3+eyeShift,y-16+bob,2,2,'#172126');
      if(age>=55){px(x-6,y-12+bob,4,2,'#b88970');px(x+3,y-12+bob,4,2,'#b88970');}
      else px(x-2,y-11+bob,5,2,'#9a5d52');
    }else{
      px(x-6,y-17+bob,12,4,hair);
    }
    if(String(a.workStyle||p.workStyle||'').toLowerCase().includes('dilig'))px(x+12,y-4+bob,5,8,'#e5d08b');
    label(a,x,y+bob);
  }

  function frame(now){c.clearRect(0,0,640,400);core.forEach((a,i)=>drawCharacter(a,i,now));requestAnimationFrame(frame);}

  async function refresh(){
    if(refreshing)return;refreshing=true;
    try{
      const r=await fetch('/api/town/world',{headers:{Accept:'application/json'},cache:'no-store'});if(!r.ok)return;
      const data=await r.json(),world=data&&data.world||{};
      core=Array.isArray(world.agents)?world.agents.filter(v=>v&&String(v.name||v.characterId||v.slot||'')):[];
    }catch(_e){}finally{refreshing=false;}
  }

  refresh();setInterval(refresh,650);requestAnimationFrame(frame);
})();
</script>
'''
    if 'town-core-character-style' not in html:
        html = html.replace('</head>', css + '</head>', 1) if '</head>' in html else css + html
    if 'town-core-character-runtime' not in html:
        html = html.replace('</body>', js + '</body>', 1) if '</body>' in html else html + js
    return html

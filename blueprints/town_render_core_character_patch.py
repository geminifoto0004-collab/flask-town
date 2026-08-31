"""Render TiDB-owned core characters above the historical fixed officer sprites.

The legacy browser snapshot still paints its original three officer sprites on
the base canvas. This overlay reads /api/town/world and composes each active
core character from profile data. If the world snapshot does not yet contain
coordinates, stable desk-slot fallbacks keep the dynamic characters visible.
"""


def patch_render_core_characters(html: str) -> str:
    css = r'''
<style id="town-core-character-style">
.game-wrap{position:relative!important}
#town-core-character-overlay{position:absolute;left:6px;top:6px;width:calc(100% - 12px);height:calc(100% - 12px);pointer-events:none;image-rendering:pixelated;image-rendering:crisp-edges;z-index:999;background:transparent!important}
</style>
'''
    js = r'''
<script id="town-core-character-runtime">
(()=>{
  const app=document.getElementById('customs-sim');
  const wrap=app&&app.querySelector('.game-wrap');
  if(!app||!wrap)return;
  if(getComputedStyle(wrap).position==='static')wrap.style.position='relative';
  let canvas=document.getElementById('town-core-character-overlay');
  if(!canvas){
    canvas=document.createElement('canvas');
    canvas.id='town-core-character-overlay';
    canvas.width=640;canvas.height=400;
    wrap.appendChild(canvas);
  }
  const c=canvas.getContext('2d');if(!c)return;c.imageSmoothingEnabled=false;
  let agents=[];let refreshing=false;
  const deskSlots=[{x:145,y:236},{x:320,y:236},{x:500,y:236}];

  function px(x,y,w,h,color){
    c.fillStyle=color;
    c.fillRect(Math.round(x/2)*2,Math.round(y/2)*2,Math.max(2,Math.round(w/2)*2),Math.max(2,Math.round(h/2)*2));
  }
  function hash(s){let h=2166136261;for(const ch of String(s||'')){h^=ch.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
  function palette(id){
    const sets=[['#416b87','#d39b55'],['#765b8e','#c98958'],['#4f7b66','#c99a4d'],['#845b61','#5e7895'],['#596b87','#a86f62'],['#6b705c','#bb8854']];
    return sets[hash(id)%sets.length];
  }
  function profile(a){return (a&&a.profile&&typeof a.profile==='object')?a.profile:{};}
  function resolvedPos(a,index){
    const x=Number(a&&a.x),y=Number(a&&a.y);
    if(Number.isFinite(x)&&Number.isFinite(y)&&x>=20&&x<=620&&y>=80&&y<=370)return {x,y};
    return deskSlots[index%deskSlots.length];
  }
  function label(a,x,y){
    const text=String(a.displayName||a.name||a.slot||'').toUpperCase();if(!text)return;
    c.font='bold 7px monospace';const w=Math.max(32,Math.ceil(c.measureText(text).width)+8);
    px(x-w/2,y-42,w,11,'rgba(18,27,34,.96)');c.fillStyle='#fff';c.textAlign='center';c.fillText(text,Math.round(x),Math.round(y-34));
  }
  function drawCharacter(a,index){
    const pos=resolvedPos(a,index),x=pos.x,y=pos.y;
    const p=profile(a),id=String(a.name||a.slot||index);
    const gender=String(p.gender||a.gender||'').toLowerCase();
    const birth=Number(p.birthYear||a.birthYear||0);const age=birth?new Date().getFullYear()-birth:35;
    const colors=palette(id),body=colors[0],accent=colors[1];
    const skin=age>=55?'#c79a79':'#d6a17d';
    const hair=age>=55?'#aaa59d':((hash(id)>>3)%2?'#3b2d26':'#241f22');

    // Erase the historical label/sprite footprint at the same slot.
    px(x-22,y-46,44,61,'#c89461');

    // New sprite.
    px(x-8,y+12,16,3,'rgba(0,0,0,.20)');
    px(x-7,y+4,6,10,'#2f4050');px(x+2,y+4,6,10,'#2f4050');
    px(x-10,y-10,20,15,body);px(x-8,y-8,16,3,accent);
    px(x-13,y-7,4,12,body);px(x+10,y-7,4,12,body);
    px(x-7,y-23,14,14,skin);
    if(gender.includes('female')||gender.includes('mujer')||gender.includes('woman')){
      px(x-9,y-26,18,6,hair);px(x-9,y-21,4,14,hair);px(x+6,y-21,4,14,hair);
    }else{
      px(x-9,y-26,18,6,hair);px(x-8,y-22,16,3,hair);
    }
    px(x-4,y-16,2,2,'#172126');px(x+3,y-16,2,2,'#172126');
    if(age>=55){px(x-6,y-12,4,2,'#b88970');px(x+3,y-12,4,2,'#b88970');}
    else px(x-2,y-11,5,2,'#9a5d52');
    if(String(a.workStyle||p.workStyle||'').toLowerCase().includes('dilig'))px(x+11,y-4,5,8,'#e5d08b');
    label(a,x,y);
  }
  function frame(){c.clearRect(0,0,640,400);agents.forEach(drawCharacter);requestAnimationFrame(frame);}
  async function refresh(){
    if(refreshing)return;refreshing=true;
    try{
      const r=await fetch('/api/town/world',{headers:{Accept:'application/json'},cache:'no-store'});if(!r.ok)return;
      const data=await r.json();const world=data&&data.world||{};
      const incoming=Array.isArray(world.agents)?world.agents.filter(v=>v&&String(v.name||v.slot||'')):[];
      agents=incoming;
    }catch(_e){}finally{refreshing=false;}
  }
  refresh();setInterval(refresh,800);requestAnimationFrame(frame);
})();
</script>
'''
    if 'town-core-character-style' not in html:
        html = html.replace('</head>', css + '</head>', 1) if '</head>' in html else css + html
    if 'town-core-character-runtime' not in html:
        html = html.replace('</body>', js + '</body>', 1) if '</body>' in html else html + js
    return html

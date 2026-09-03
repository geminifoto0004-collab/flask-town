"""Render TiDB colleagues beyond the three legacy native sprite slots.

The mature browser game owns three historical officer sprites. TiDB may contain
more permanent colleagues. Build synthetic persistent human sprites for every
additional database-defined colleague by combining world.agents with the
server-owned world.characterProfiles list. Also expose the authoritative TiDB
roster in the event log so nighttime/off-duty visibility cannot hide whether a
new colleague was actually created.
"""


def patch_render_extra_colleagues(html: str) -> str:
    if 'town-extra-colleagues-runtime' in html:
        return html

    marker = "    const incoming=Array.isArray(world&&world.genericEntities)?world.genericEntities:[];\n"
    replacement = r'''    const incomingBase=Array.isArray(world&&world.genericEntities)?world.genericEntities:[];
    const profileRows=Array.isArray(world&&world.characterProfiles)?world.characterProfiles:[];
    const nativeIds=new Set(agents.slice(0,3).map(a=>String(a&&a.name||a&&a.slot||'').toUpperCase()).filter(Boolean));
    const colleagueById=new Map();

    agents.forEach(a=>{
      const id=String(a&&a.name||a&&a.slot||'').toUpperCase();
      if(id)colleagueById.set(id,a||{});
    });
    profileRows.forEach(p=>{
      const id=String(p&&p.name||p&&p.id||p&&p.character_id||'').toUpperCase();
      if(!id)return;
      const existing=colleagueById.get(id)||{};
      colleagueById.set(id,{...existing,name:id,displayName:String(existing.displayName||p&&p.displayName||id),profile:(p&&p.profile)||existing.profile||{}});
    });

    const extraSource=[...colleagueById.entries()]
      .filter(([id])=>id&&!nativeIds.has(id))
      .map(([,a])=>a);
    const extraColleagues=extraSource.map((a,index)=>{
      const id=String(a&&a.name||a&&a.slot||'').toUpperCase();
      const col=index%4,row=Math.floor(index/4);
      const x=Number.isFinite(Number(a&&a.x))?Number(a.x):(120+col*120);
      const y=Number.isFinite(Number(a&&a.y))?Number(a.y):(205+row*44);
      return {
        id,
        name:String(a&&a.displayName||id),
        entityType:'human',
        zone:'office',
        x,y,
        bodyColor:String(a&&a.bodyColor||'#536f86'),
        accentColor:String(a&&a.accentColor||'#d4a74a'),
        carrying:[],
        script:[],
        permanentColleague:true
      };
    }).filter(v=>v.id);

    const genericIds=new Set(incomingBase.map(v=>String(v&&v.id||'').toUpperCase()));
    const incoming=incomingBase.concat(extraColleagues.filter(v=>!genericIds.has(String(v.id).toUpperCase())));
    window.__townExtraColleagueIds=()=>extraColleagues.map(v=>v.id);
'''
    patched = marker in html
    if patched:
        html = html.replace(marker, replacement, 1)

    roster_js = r'''
<script id="town-extra-colleagues-runtime">
window.TOWN_EXTRA_COLLEAGUES=%s;
(()=>{
  let last='';
  async function refreshRoster(){
    try{
      const r=await fetch('/api/town/colleagues',{headers:{Accept:'application/json'}});
      if(!r.ok)return;
      const data=await r.json();
      const rows=Array.isArray(data&&data.characters)?data.characters:[];
      const ids=rows.map(v=>String(v&&v.id||'').toUpperCase()).filter(Boolean);
      window.__townTiDBColleagues=rows;
      const signature=ids.join('|');
      if(signature===last)return;
      last=signature;
      const app=document.getElementById('customs-sim');
      const box=app&&app.querySelector('#eventLog');
      if(box){
        const d=document.createElement('div');
        d.textContent='> 正式同事(TiDB)：'+(ids.length?ids.join('、'):'尚無資料');
        box.appendChild(d);box.scrollTop=box.scrollHeight;
      }
    }catch(_e){}
  }
  refreshRoster();setInterval(refreshRoster,30000);
})();
</script>
''' % ('true' if patched else 'false')

    return html.replace('</body>', roster_js + '</body>', 1) if '</body>' in html else html + roster_js

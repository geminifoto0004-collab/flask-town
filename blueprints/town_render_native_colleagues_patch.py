"""Extend the mature native browser agent engine with every TiDB colleague.

There must be one employee rendering/movement/chat method, not a separate
canvas for the 4th+ colleague.  This patch injects TiDB roster synchronization
inside the original town script closure where `agents` already exists. New
employees clone a same-gender native agent template, then participate in the
same draw/update/path/chat/local-life loops as the first three employees.
"""


def patch_render_native_colleagues(html: str) -> str:
    if "townRefreshTiDBNativeColleagues" in html:
        return html

    marker = "  function sync(){"
    if marker not in html:
        return html

    runtime = r'''  let townTiDBRosterRows=[];
  let townTiDBRosterBusy=false;
  const townTiDBDynamicIds=new Set();

  function townFemaleGender(value){
    const g=String(value||'').trim().toLowerCase();
    return g==='f'||g==='female'||g==='femenino'||g==='mujer'||g==='女'||g.includes('female')||g.includes('mujer');
  }

  function townAgentId(a){return String(a&&a.name||a&&a.slot||'').trim().toUpperCase();}

  function townCloneAgentTemplate(row,rowIndex,rows,world){
    const native=agents.slice(0,Math.min(3,agents.length));
    if(!native.length)return null;
    const wantFemale=townFemaleGender(row&&row.gender);
    let template=null;
    for(let i=0;i<native.length;i++){
      const nativeRow=rows[i]||{};
      if(townFemaleGender(nativeRow.gender)===wantFemale){template=native[i];break;}
    }
    if(!template)template=native[0];

    const extraIndex=Math.max(0,rowIndex-3);
    const homeX=135+(extraIndex%4)*115;
    const homeY=218+Math.floor(extraIndex/4)*32;
    const clone={...template};
    clone.name=String(row.id||'').toUpperCase();
    clone.slot=clone.name;
    clone.displayName=String(row.name||clone.name);
    clone.index=agents.length;
    clone.x=homeX;clone.y=homeY;clone.homeX=homeX;clone.homeY=homeY;
    clone.path=[];clone.pathTarget='';clone.task=null;clone.state='idle';
    clone.chatText='';clone.chatTimer=0;clone.intentLabel='';clone.intentUntil=0;
    clone.timer=.2;clone.decisionTimer=.3;clone.manualOffDuty=false;clone.dutyState='';
    clone.tidbDynamicColleague=true;
    clone.tidbGender=String(row.gender||'');
    clone.profile={...(template.profile||{}),...(row.profile||{}),gender:String(row.gender||'')};
    clone.careerState=String(row.careerState||row.profile&&row.profile.careerState||'active');
    clone.workStyle=String(row.workStyle||row.profile&&row.profile.workStyle||'');

    const presence=world&&world.characterPresence&&world.characterPresence[clone.name];
    if(presence&&typeof presence==='object'){
      if(typeof presence.manualOffDuty==='boolean')clone.manualOffDuty=presence.manualOffDuty;
      if(presence.dutyState==='on'||presence.dutyState==='off')clone.dutyState=presence.dutyState;
    }
    return clone;
  }

  async function townRefreshTiDBNativeColleagues(){
    if(townTiDBRosterBusy)return false;
    townTiDBRosterBusy=true;
    try{
      const [rr,rw]=await Promise.all([
        fetch('/api/town/colleagues',{headers:{Accept:'application/json'},cache:'no-store'}),
        fetch('/api/town/world',{headers:{Accept:'application/json'},cache:'no-store'})
      ]);
      if(!rr.ok||!rw.ok)return false;
      const roster=await rr.json();
      const worldData=await rw.json();
      const world=worldData&&worldData.world&&typeof worldData.world==='object'?worldData.world:{};
      const rows=Array.isArray(roster&&roster.characters)?roster.characters:[];
      if(!rows.length)return false;
      townTiDBRosterRows=rows;

      const validIds=new Set(rows.map(r=>String(r&&r.id||'').toUpperCase()).filter(Boolean));
      const presence=world&&world.characterPresence&&typeof world.characterPresence==='object'?world.characterPresence:{};

      rows.forEach((row,rowIndex)=>{
        const id=String(row&&row.id||'').trim().toUpperCase();if(!id)return;
        let agent=agents.find(a=>townAgentId(a)===id);
        if(!agent&&rowIndex>=3){
          agent=townCloneAgentTemplate(row,rowIndex,rows,world);
          if(agent){agents.push(agent);townTiDBDynamicIds.add(id);}
        }
        if(!agent)return;

        agent.name=id;agent.slot=id;agent.displayName=String(row.name||id);
        agent.tidbGender=String(row.gender||'');
        agent.profile={...(agent.profile||{}),...(row.profile||{}),gender:String(row.gender||'')};
        agent.careerState=String(row.careerState||row.profile&&row.profile.careerState||agent.careerState||'active');
        agent.workStyle=String(row.workStyle||row.profile&&row.profile.workStyle||agent.workStyle||'');
        const pr=presence[id];
        if(pr&&typeof pr==='object'){
          if(typeof pr.manualOffDuty==='boolean')agent.manualOffDuty=pr.manualOffDuty;
          if(pr.dutyState==='on'||pr.dutyState==='off')agent.dutyState=pr.dutyState;
        }
      });

      // Remove only agents created by this TiDB extension if they were later
      // deactivated/deleted from TiDB. Never remove the three mature native slots.
      for(let i=agents.length-1;i>=3;i--){
        const a=agents[i],id=townAgentId(a);
        if(a&&a.tidbDynamicColleague&&!validIds.has(id)){agents.splice(i,1);townTiDBDynamicIds.delete(id);}
      }
      agents.forEach((a,i)=>{if(a)a.index=i;});

      window.__townTiDBNativeAgentIds=()=>agents.map(townAgentId).filter(Boolean);
      window.__townTiDBDynamicAgentIds=()=>agents.filter(a=>a&&a.tidbDynamicColleague).map(townAgentId);
      return true;
    }catch(_e){return false;}finally{townTiDBRosterBusy=false;}
  }

  window.__townRefreshNativeColleagues=townRefreshTiDBNativeColleagues;
  setTimeout(townRefreshTiDBNativeColleagues,450);
  setInterval(townRefreshTiDBNativeColleagues,4000);

'''
    return html.replace(marker, runtime + marker, 1)

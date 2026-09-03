"""Extend the mature native browser agent engine with every TiDB colleague.

There must be one employee rendering/movement/chat/work method, not a separate
canvas for the 4th+ colleague. The authoritative TiDB roster is embedded into
the generated HTML so all permanent colleagues exist in native `agents` before
the first game frame. TiDB numeric traits are promoted onto each native agent,
matching the server character runtime, so work/idle behavior does not inherit a
cloned template's personality by accident.
"""

import json

from .town_character_tidb_runtime import character_context


def _bootstrap_rows():
    try:
        rows = character_context(force=True)
    except Exception:
        rows = []
    result = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        traits = dict(row.get("traits") or {}) if isinstance(row.get("traits"), dict) else {}
        result.append({
            "id": str(row.get("id") or "").upper(),
            "name": str(row.get("name") or row.get("id") or ""),
            "gender": str(row.get("gender") or ""),
            "birthYear": row.get("birthYear"),
            "careerState": str(row.get("careerState") or "active"),
            "workStyle": str(row.get("workStyle") or ""),
            "displayOrder": row.get("displayOrder", 0),
            "traits": traits,
            "profile": {
                "gender": str(row.get("gender") or ""),
                "birthYear": row.get("birthYear"),
                "maritalStatus": str(row.get("maritalStatus") or ""),
                "partnerLabel": str(row.get("partnerLabel") or ""),
                "childrenCount": row.get("childrenCount", 0),
                "careerState": str(row.get("careerState") or "active"),
                "workStyle": str(row.get("workStyle") or ""),
                "personalityNotes": str(row.get("personalityNotes") or ""),
                "familyNotes": str(row.get("familyNotes") or ""),
                "traits": traits,
            },
        })
    return result


def patch_render_native_colleagues(html: str) -> str:
    if "townRefreshTiDBNativeColleagues" in html:
        return html

    marker = "  function sync(){"
    if marker not in html:
        return html

    bootstrap_json = json.dumps(_bootstrap_rows(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    runtime = r'''  const townTiDBBootstrapRows=__TOWN_BOOTSTRAP_ROWS__;
  let townTiDBRosterRows=Array.isArray(townTiDBBootstrapRows)?townTiDBBootstrapRows:[];
  let townTiDBRosterBusy=false;
  let townTiDBRosterKey='';
  const townTiDBDynamicIds=new Set();
  const townShipAssignmentCounts={};
  const townShipTaskState=new Map();
  let townShipAssignmentSignature='';

  function townFemaleGender(value){
    const g=String(value||'').trim().toLowerCase();
    return g==='f'||g==='female'||g==='femenino'||g==='mujer'||g==='女'||g.includes('female')||g.includes('mujer');
  }
  function townAgentId(a){return String(a&&a.name||a&&a.slot||'').trim().toUpperCase();}

  function townApplyTiDBTraits(agent,row){
    if(!agent||!row)return;
    const source=(row.traits&&typeof row.traits==='object')?row.traits:((row.profile&&row.profile.traits&&typeof row.profile.traits==='object')?row.profile.traits:{});
    Object.entries(source).forEach(([key,value])=>{
      if(!key)return;
      const n=Number(value);
      if(Number.isFinite(n))agent[String(key)]=Math.max(0,Math.min(1,n));
    });
  }

  function townCloneAgentTemplate(row,rowIndex,rows,world){
    // The first three are visual templates only. Employee identity/behavior is
    // always overwritten from the corresponding TiDB row below.
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
    clone.name=String(row.id||'').toUpperCase();clone.slot=clone.name;clone.displayName=String(row.name||clone.name);
    clone.index=agents.length;clone.x=homeX;clone.y=homeY;clone.homeX=homeX;clone.homeY=homeY;
    clone.path=[];clone.pathTarget='';clone.task=null;clone.state='idle';clone.chatText='';clone.chatTimer=0;clone.intentLabel='';clone.intentUntil=0;
    clone.timer=.2;clone.decisionTimer=.3;clone.manualOffDuty=false;clone.dutyState='';clone.tidbDynamicColleague=true;clone.tidbGender=String(row.gender||'');
    clone.profile={...(template.profile||{}),...(row.profile||{}),gender:String(row.gender||'')};
    clone.careerState=String(row.careerState||row.profile&&row.profile.careerState||'active');
    clone.workStyle=String(row.workStyle||row.profile&&row.profile.workStyle||'');
    townApplyTiDBTraits(clone,row);
    const presence=world&&world.characterPresence&&world.characterPresence[clone.name];
    if(presence&&typeof presence==='object'){
      if(typeof presence.manualOffDuty==='boolean')clone.manualOffDuty=presence.manualOffDuty;
      if(presence.dutyState==='on'||presence.dutyState==='off')clone.dutyState=presence.dutyState;
    }
    return clone;
  }

  function townMergeTiDBRowsIntoNativeAgents(rows,world,logRoster=false){
    rows=Array.isArray(rows)?rows:[];
    if(!rows.length)return false;
    townTiDBRosterRows=rows;
    const validIds=new Set(rows.map(r=>String(r&&r.id||'').toUpperCase()).filter(Boolean));
    const presence=world&&world.characterPresence&&typeof world.characterPresence==='object'?world.characterPresence:{};

    rows.forEach((row,rowIndex)=>{
      const id=String(row&&row.id||'').trim().toUpperCase();if(!id)return;
      let agent=agents.find(a=>townAgentId(a)===id);
      if(!agent&&rowIndex>=3){agent=townCloneAgentTemplate(row,rowIndex,rows,world);if(agent){agents.push(agent);townTiDBDynamicIds.add(id);}}
      if(!agent)return;
      agent.name=id;agent.slot=id;agent.displayName=String(row.name||id);agent.tidbGender=String(row.gender||'');
      agent.profile={...(agent.profile||{}),...(row.profile||{}),gender:String(row.gender||'')};
      agent.careerState=String(row.careerState||row.profile&&row.profile.careerState||agent.careerState||'active');
      agent.workStyle=String(row.workStyle||row.profile&&row.profile.workStyle||agent.workStyle||'');
      // Match server-side _merge_world_characters: TiDB numeric traits are
      // first-class agent properties, not merely descriptive profile metadata.
      townApplyTiDBTraits(agent,row);
      const pr=presence[id];
      if(pr&&typeof pr==='object'){
        if(typeof pr.manualOffDuty==='boolean')agent.manualOffDuty=pr.manualOffDuty;
        if(pr.dutyState==='on'||pr.dutyState==='off')agent.dutyState=pr.dutyState;
      }
    });

    for(let i=agents.length-1;i>=3;i--){
      const a=agents[i],id=townAgentId(a);
      if(a&&a.tidbDynamicColleague&&!validIds.has(id)){agents.splice(i,1);townTiDBDynamicIds.delete(id);}
    }
    agents.forEach((a,i)=>{if(a)a.index=i;});

    const rosterIds=rows.map(r=>String(r&&r.id||'').toUpperCase()).filter(Boolean);
    const nativeIds=agents.map(townAgentId).filter(Boolean);
    const key=rosterIds.join(',')+'|'+nativeIds.join(',');
    if(logRoster&&key!==townTiDBRosterKey){
      townTiDBRosterKey=key;
      if(typeof addLog==='function'){
        addLog('正式同事(TiDB)：'+rosterIds.join(','));
        addLog('native agents：'+nativeIds.join(','));
      }
    }else if(!townTiDBRosterKey){
      townTiDBRosterKey=key;
    }
    window.__townTiDBNativeAgentIds=()=>agents.map(townAgentId).filter(Boolean);
    window.__townTiDBDynamicAgentIds=()=>agents.filter(a=>a&&a.tidbDynamicColleague).map(townAgentId);
    return true;
  }

  function townObserveShipAssignments(){
    try{
      const roster=Array.isArray(agents)?agents.filter(a=>a&&townAgentId(a)):[];
      const active=[];
      roster.forEach(agent=>{
        const id=townAgentId(agent),hasTask=!!agent.task||agent.state==='workingShip'||agent.state==='inspect';
        const previous=!!townShipTaskState.get(id);
        if(hasTask&&!previous)townShipAssignmentCounts[id]=(townShipAssignmentCounts[id]||0)+1;
        townShipTaskState.set(id,hasTask);
        if(hasTask)active.push(id);
      });
      const sig=active.slice().sort().join(',');
      if(sig&&sig!==townShipAssignmentSignature){
        townShipAssignmentSignature=sig;
        const onDuty=roster.filter(a=>!a.manualOffDuty&&(typeof isAgentOnDuty!=='function'||isAgentOnDuty(a))).map(townAgentId);
        const waiting=onDuty.filter(id=>!active.includes(id));
        if(typeof addLog==='function')addLog('船務分派：'+active.join(',')+(waiting.length?'｜待命：'+waiting.join(','):''));
      }else if(!sig){townShipAssignmentSignature='';}
      window.__townShipAssignmentStats=()=>({counts:{...townShipAssignmentCounts},working:active.slice(),roster:roster.map(townAgentId)});
    }catch(_e){}
  }

  // IMPORTANT: hydrate from the TiDB roster embedded by Flask synchronously,
  // before sync()/animation can paint the historical three native slots alone.
  townMergeTiDBRowsIntoNativeAgents(townTiDBBootstrapRows,{},false);

  async function townRefreshTiDBNativeColleagues(){
    if(townTiDBRosterBusy)return false;
    townTiDBRosterBusy=true;
    try{
      const [rr,rw]=await Promise.all([
        fetch('/api/town/colleagues',{headers:{Accept:'application/json'},cache:'no-store'}),
        fetch('/api/town/world',{headers:{Accept:'application/json'},cache:'no-store'})
      ]);
      if(!rr.ok||!rw.ok)return false;
      const roster=await rr.json();const worldData=await rw.json();
      const world=worldData&&worldData.world&&typeof worldData.world==='object'?worldData.world:{};
      const rows=Array.isArray(roster&&roster.characters)?roster.characters:[];
      return townMergeTiDBRowsIntoNativeAgents(rows,world,true);
    }catch(_e){return false;}finally{townTiDBRosterBusy=false;}
  }

  window.__townRefreshNativeColleagues=townRefreshTiDBNativeColleagues;
  setTimeout(townRefreshTiDBNativeColleagues,120);
  setInterval(townRefreshTiDBNativeColleagues,4000);
  setInterval(townObserveShipAssignments,350);

'''.replace('__TOWN_BOOTSTRAP_ROWS__', bootstrap_json)
    return html.replace(marker, runtime + marker, 1)

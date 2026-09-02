"""Local life plus occasional one-call AI conversations for CUSTOMS AGENT TOWN.

Ordinary movement/pathfinding stays local and free. When two active characters
naturally decide to converse, the browser makes one DeepSeek request for the
whole multi-turn conversation. That request uses TiDB character memory and the
persisted current-information feed. A tiny scripted conversation is kept only
as an API/network fallback.
"""

from .town_render_admin_entity_sync_patch import patch_render_admin_entity_sync
from .town_render_extra_colleagues_patch import patch_render_extra_colleagues
from .town_render_performance_patch import patch_render_performance


def patch_render_local_life(html: str) -> str:
    marker = "  function sync(){"
    if "function townLocalLifeTick()" not in html and marker in html:
        helper = r'''  let localLifeTimer=rand(12,28);
  let aiChatTimer=rand(25,50);
  let aiChatBusy=false;
  const localChatRecent=[];

  function pickLocalChatPair(live){
    if(!Array.isArray(live)||live.length<2)return null;
    const candidates=[];
    for(let i=0;i<live.length;i++)for(let j=i+1;j<live.length;j++){
      const a=live[i],b=live[j];
      const key=[String(a.name),String(b.name)].sort().join('|');
      const penalty=localChatRecent.includes(key)?4:0;
      candidates.push({a,b,key,score:Math.random()-penalty});
    }
    candidates.sort((x,y)=>y.score-x.score);
    return candidates[0]||null;
  }

  function fallbackChat(pair){
    if(!pair||typeof applyAiTownActions!=='function')return false;
    const lines=[
      [
        ['¿Cómo va todo?','最近怎麼樣？'],
        ['Bien, aquí seguimos con lo nuestro.','還好，就繼續忙自己的事情。'],
        ['Después conversamos con más calma.','等一下有空再慢慢聊。'],
        ['Ya, dale.','好啊。']
      ],
      [
        ['¿Vas por un café después?','等一下要去喝咖啡嗎？'],
        ['Puede ser, cuando termine esto.','可以啊，等我把這個弄完。'],
        ['Me avisas entonces.','那你等一下叫我。'],
        ['Sí.','好。']
      ]
    ];
    const p=lines[Math.floor(Math.random()*lines.length)];
    applyAiTownActions([{type:'agent_chat',from:String(pair.a.name),to:String(pair.b.name),turns:[
      {speaker:String(pair.a.name),text:p[0][0],text_zh:p[0][1]},
      {speaker:String(pair.b.name),text:p[1][0],text_zh:p[1][1]},
      {speaker:String(pair.a.name),text:p[2][0],text_zh:p[2][1]},
      {speaker:String(pair.b.name),text:p[3][0],text_zh:p[3][1]}
    ],localFallback:true}]);
    return true;
  }

  function currentLiveAgents(){
    if(!Array.isArray(agents))return [];
    return agents.filter(a=>a&&a.name&&a.state!=='workingShip'&&a.state!=='inspect'&&a.state!=='chat'&&!a.manualOffDuty);
  }

  async function townAiChatTick(){
    if(aiChatBusy||typeof applyAiTownActions!=='function')return;
    const live=currentLiveAgents();if(live.length<2)return;
    const pair=pickLocalChatPair(live);if(!pair)return;
    localChatRecent.push(pair.key);while(localChatRecent.length>3)localChatRecent.shift();
    aiChatBusy=true;
    try{
      const world=(typeof compactTownSnapshot==='function')?compactTownSnapshot():{agents:live.map(a=>({name:a.name,displayName:a.displayName,state:a.state,profile:a.profile||{}})),recentDialogue:(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-8)};
      const r=await fetch('/api/town/auto-chat',{
        method:'POST',
        headers:{'Content-Type':'application/json','Accept':'application/json'},
        body:JSON.stringify({from:String(pair.a.name),to:String(pair.b.name),world})
      });
      const data=await r.json().catch(()=>({}));
      if(!r.ok||!data.ok||!Array.isArray(data.actions)||!data.actions.length)throw new Error(data.error||'AI chat unavailable');
      applyAiTownActions(data.actions);
    }catch(_e){
      fallbackChat(pair);
    }finally{
      aiChatBusy=false;
    }
  }

  function townLocalLifeTick(){
    if(typeof applyAiTownActions!=='function')return;
    const live=currentLiveAgents();if(!live.length)return;
    const actor=live[Math.floor(Math.random()*live.length)];
    const roll=Math.random();
    let action='wander';
    if(roll<.20)action='desk';
    else if(roll<.36)action='files';
    else if(roll<.49)action='coffee';
    else if(roll<.60)action='lookSea';
    else if(roll<.69)action='plant';
    else if(roll<.77)action='stretch';
    else if(roll<.88&&live.length>1)action='checkCoworker';
    applyAiTownActions([{type:'agent_action',agent:String(actor.name),action}]);
  }

'''
        html = html.replace(marker, helper + marker, 1)

    html = html.replace(
        "    updateDogs(dt);",
        "    updateDogs(dt);\n"
        "    localLifeTimer-=dt;if(localLifeTimer<=0){localLifeTimer=rand(16,34);townLocalLifeTick();}\n"
        "    aiChatTimer-=dt;if(aiChatTimer<=0){aiChatTimer=rand(90,180);townAiChatTick();}",
        1,
    )

    html = html.replace("let aiAutoTimer=rand(35,75);", "let aiAutoTimer=rand(420,900);")
    html = html.replace("aiAutoTimer=rand(300,900);testDeepSeek();", "aiAutoTimer=rand(900,1800);testDeepSeek();")
    html = html.replace("aiAutoTimer=aiAuto?rand(15,35):999999;", "aiAutoTimer=aiAuto?rand(300,600):999999;")
    html = html.replace("if(aiAuto)aiAutoTimer=rand(8,22);", "if(aiAuto)aiAutoTimer=rand(300,600);")

    # Extend the existing generic overlay so TiDB characters after the three
    # mature native sprite slots are still visible as permanent colleagues.
    html = patch_render_extra_colleagues(html)

    # Admin command responses already contain the authoritative evolved world.
    html = patch_render_admin_entity_sync(html)
    return patch_render_performance(html)

"""Synchronize the dialogue sidebar with the native speech bubble clock.

DeepSeek may return a whole multi-turn conversation at once, while the mature
native town engine renders it one turn at a time through each agent's `chatText`.
The sidebar therefore follows `agents[*].chatText` directly instead of using the
status/event log as an indirect clock. While a conversation is playing, a full
TiDB copy of that same conversation is hidden until native playback finishes.
Manual scroll position is also preserved when the user is reading older turns.
"""


def patch_render_dialogue_sync(html: str) -> str:
    if "townPollNativeSpeech" in html:
        return html

    # Stage the expected conversation without rendering all turns immediately.
    # The active card is not inserted into history until the first native speech
    # bubble really appears.
    old_store = r'''    window.__townDialogueHistory=Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[];
    const storedTurns=turns.map(turn=>({speaker:String(turn.speaker||''),text:String(turn.text||''),text_zh:String(turn.text_zh||'')}));
    window.__townDialogueHistory.push({at:Date.now(),members:[from.name,to.name],turns:storedTurns,text:storedTurns.map(turn=>turn.speaker+': '+(turn.text||'')).join(' ').slice(0,520)});
    window.__townDialogueHistory=window.__townDialogueHistory.slice(-10);
    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();
    turns=turns.map(turn=>({...turn,text:dialogueText(turn)}));'''
    new_store = r'''    window.__townDialogueHistory=Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[];
    const storedTurns=turns.map(turn=>({speaker:String(turn.speaker||''),text:String(turn.text||''),text_zh:String(turn.text_zh||turn.textZh||'')}));
    const liveDialogue={
      id:'live-'+Date.now()+'-'+String(from.name||'')+'-'+String(to.name||''),
      at:Date.now(),members:[from.name,to.name],turns:[],text:'',
      __staged:true,__visibleInHistory:false,__expectedTurns:storedTurns,__spokenIndex:0
    };
    window.__townActiveDialogue=liveDialogue;
    turns=turns.map(turn=>({...turn,text:dialogueText(turn)}));'''
    html = html.replace(old_store, new_store, 1)

    marker = "  function installTownLanguageUi(){"
    helper = r'''  const townNativeSpeechState=new Map();

  function townDialogueMemberKey(item){
    return (Array.isArray(item&&item.members)?item.members:[])
      .map(v=>String(v||'').trim().toUpperCase()).filter(Boolean).sort().join('|');
  }

  function townDialogueMatchesActive(item,active){
    if(!item||!active)return false;
    if(townDialogueMemberKey(item)!==townDialogueMemberKey(active))return false;
    const expected=Array.isArray(active.__expectedTurns)?active.__expectedTurns:[];
    const actual=Array.isArray(item.turns)?item.turns:[];
    if(!expected.length||!actual.length)return true;
    const e=expected[0]||{},a=actual[0]||{};
    const es=String(e.speaker||'').trim().toUpperCase();
    const as=String(a.speaker||'').trim().toUpperCase();
    if(es&&as&&es!==as)return false;
    const et=String(e.text||e.text_zh||'').trim();
    const at=String(a.text||a.text_zh||'').trim();
    return !et||!at||et===at;
  }
  window.__townDialogueMatchesActive=townDialogueMatchesActive;

  function townPutActiveIntoHistory(active){
    if(!active||active.__visibleInHistory)return;
    const current=Array.isArray(window.__townDialogueHistory)?Array.from(window.__townDialogueHistory):[];
    current.push(active);
    window.__townDialogueHistory=current.slice(-24);
    active.__visibleInHistory=true;
  }

  function townConsumeNativeSpeech(speaker,visibleText){
    const active=window.__townActiveDialogue;
    if(!active||!active.__staged||!Array.isArray(active.__expectedTurns))return false;
    const who=String(speaker||'').trim().toUpperCase();
    if(!who||!String(visibleText||'').trim())return false;

    let index=Math.max(0,Number(active.__spokenIndex)||0);
    let selected=-1;
    for(let i=index;i<active.__expectedTurns.length;i++){
      if(String(active.__expectedTurns[i]&&active.__expectedTurns[i].speaker||'').trim().toUpperCase()===who){selected=i;break;}
    }
    if(selected<0)return false;

    const turn=active.__expectedTurns[selected]||{};
    active.turns.push({
      speaker:String(turn.speaker||speaker||''),
      text:String(turn.text||visibleText||''),
      text_zh:String(turn.text_zh||turn.textZh||'')
    });
    active.__spokenIndex=selected+1;
    active.text=active.turns.map(t=>String(t.speaker||'')+': '+String(t.text||'')).join(' ').slice(0,520);
    townPutActiveIntoHistory(active);
    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();

    if(active.__spokenIndex>=active.__expectedTurns.length){
      active.__staged=false;
      delete active.__expectedTurns;
      delete active.__spokenIndex;
      window.__townActiveDialogue=null;
      if(typeof window.__townPostDialogueNow==='function')window.__townPostDialogueNow(active);
    }
    return true;
  }
  window.townConsumeNativeSpeech=townConsumeNativeSpeech;

  function townPollNativeSpeech(){
    try{
      if(Array.isArray(agents)){
        const liveIds=new Set();
        agents.forEach(agent=>{
          if(!agent)return;
          const id=String(agent.name||agent.slot||'').trim().toUpperCase();
          if(!id)return;
          liveIds.add(id);
          const text=String(agent.chatText||'').trim();
          const previous=String(townNativeSpeechState.get(id)||'');
          if(text&&text!==previous)townConsumeNativeSpeech(id,text);
          townNativeSpeechState.set(id,text);
        });
        [...townNativeSpeechState.keys()].forEach(id=>{if(!liveIds.has(id))townNativeSpeechState.delete(id);});
      }
    }catch(_e){}
    requestAnimationFrame(townPollNativeSpeech);
  }
  requestAnimationFrame(townPollNativeSpeech);

'''
    if marker in html:
        html = html.replace(marker, helper + marker, 1)

    # Do not force-scroll while the user is reading older dialogue. Only follow
    # new speech when the panel was already near the bottom (or on first render).
    html = html.replace(
        "    const items=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-8);",
        "    const firstPaint=box.dataset.townScrollReady!=='1';\n"
        "    const oldTop=box.scrollTop;\n"
        "    const nearBottom=firstPaint||(box.scrollHeight-box.scrollTop-box.clientHeight<64);\n"
        "    const items=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-20);",
        1,
    )
    html = html.replace(
        "    requestAnimationFrame(()=>{box.scrollTop=box.scrollHeight;syncTownDialoguePanelHeight();});",
        "    requestAnimationFrame(()=>{\n"
        "      if(nearBottom)box.scrollTop=box.scrollHeight;else box.scrollTop=oldTop;\n"
        "      box.dataset.townScrollReady='1';\n"
        "      syncTownDialoguePanelHeight();\n"
        "    });",
        1,
    )

    # The main world synchronizer may already contain a complete server/TiDB
    # dialogue while the local actors are still speaking it. Hide that full copy
    # and preserve only the locally revealed staged card until playback ends.
    old_apply = "    if(Array.isArray(world?.recentDialogue)){window.__townDialogueHistory=world.recentDialogue.map(item=>({at:item.at,members:Array.isArray(item.members)?item.members:[],turns:Array.isArray(item.turns)?item.turns:[],text:item.text||''})).slice(-10);setTimeout(()=>{if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();},0);}" 
    new_apply = "    if(Array.isArray(world?.recentDialogue)){\n" \
        "      let incoming=world.recentDialogue.map(item=>({id:item.id,at:item.at,members:Array.isArray(item.members)?item.members:[],turns:Array.isArray(item.turns)?item.turns:[],text:item.text||''}));\n" \
        "      const active=window.__townActiveDialogue;\n" \
        "      if(active&&active.__staged&&typeof townDialogueMatchesActive==='function')incoming=incoming.filter(item=>!townDialogueMatchesActive(item,active));\n" \
        "      const current=Array.isArray(window.__townDialogueHistory)?Array.from(window.__townDialogueHistory):[];\n" \
        "      const staged=current.filter(item=>item&&item.__staged);\n" \
        "      window.__townDialogueHistory=incoming.concat(staged).sort((a,b)=>Number(a.at||0)-Number(b.at||0)).slice(-24);\n" \
        "      setTimeout(()=>{if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();},0);\n" \
        "    }"
    html = html.replace(old_apply, new_apply, 1)

    # Shared TiDB polling follows the same rule: a persisted full copy of the
    # conversation currently playing must not get ahead of the native bubbles.
    html = html.replace(
        "    fetch('/api/town/dialogues?limit=12'",
        "    fetch('/api/town/dialogues?limit=24'",
        1,
    )
    html = html.replace(
        "        const ids=new Set(shared.map(dialogueId));",
        "        const active=window.__townActiveDialogue;\n"
        "        if(active&&active.__staged&&typeof window.__townDialogueMatchesActive==='function'){\n"
        "          for(let i=shared.length-1;i>=0;i--){if(window.__townDialogueMatchesActive(shared[i],active))shared.splice(i,1);}\n"
        "        }\n"
        "        const ids=new Set(shared.map(dialogueId));",
        1,
    )
    html = html.replace(
        "        window.__townDialogueHistory=shared.slice(-12);",
        "        const staged=(Array.isArray(window.__townDialogueHistory)?Array.from(window.__townDialogueHistory):[]).filter(x=>x&&x.__staged);\n"
        "        staged.forEach(chat=>{const id=dialogueId(chat);if(!ids.has(id))shared.push(chat);});\n"
        "        shared.sort((a,b)=>Number(a.at||0)-Number(b.at||0));\n"
        "        window.__townDialogueHistory=shared.slice(-24);",
        1,
    )

    # Persist only after native playback reaches the final expected turn.
    html = html.replace(
        "  function wrapArray(value){",
        "  window.__townPostDialogueNow=postDialogue;\n\n  function wrapArray(value){",
        1,
    )
    return html

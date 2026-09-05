"""Make the right dialogue panel a faithful view of native visible speech.

A multi-turn AI response may be generated at once, but the town canvas reveals
one `agent.chatText` at a time. The sidebar therefore advances only when that
native speech value actually appears. Single-agent speech is captured too.
TiDB remains completed/shared history; it never drives local live timing.

Scrolling has one owner rule: if the user leaves the bottom, the viewport stays
where the user put it through all DOM/history refreshes. Auto-follow resumes only
when the user themselves returns to the bottom.
"""


def patch_render_dialogue_sync(html: str) -> str:
    if "townPollNativeSpeech" in html:
        return html

    # Do not insert a complete generated conversation into the sidebar before
    # native playback. Stage its original bilingual turns and reveal them only
    # as matching chatText bubbles become visible on the canvas.
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
    # The profile patch uses a different history insertion. Previously this
    # failed silently, so full chats AND translated single-speech copies appeared.
    profile_store = """    window.__townDialogueHistory=Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[];
    window.__townDialogueHistory.push({at:Date.now(),members:[from.name,to.name],turns:turns.map(turn=>({speaker:turn.speaker,text:turn.text,text_zh:turn.text_zh||''})),text:turns.map(turn=>turn.speaker+': '+turn.text).join(' ').slice(0,520)});
    window.__townDialogueHistory=window.__townDialogueHistory.slice(-8);
    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();"""
    html = html.replace(profile_store, new_store.replace(
        "    turns=turns.map(turn=>({...turn,text:dialogueText(turn)}));", ""), 1)

    marker = "  function installTownLanguageUi(){"
    helper = r'''  const townNativeSpeechState=new Map();
  const townStandaloneSpeechState=new Map();

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

  function townPutIntoHistory(item){
    if(!item)return;
    const current=Array.isArray(window.__townDialogueHistory)?Array.from(window.__townDialogueHistory):[];
    if(!current.includes(item))current.push(item);
    window.__townDialogueHistory=current.slice(-40);
    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();
  }

  function townPutActiveIntoHistory(active){
    if(!active||active.__visibleInHistory)return;
    active.__visibleInHistory=true;
    townPutIntoHistory(active);
  }

  function townAppendStandaloneSpeech(speaker,visibleText,original){
    const who=String(speaker||'').trim().toUpperCase();
    const text=String(visibleText||'').trim();
    if(!who||!text)return false;
    const signature=who+'|'+text;
    const now=Date.now();
    const previous=townStandaloneSpeechState.get(signature)||0;
    if(now-previous<2500)return false;
    townStandaloneSpeechState.set(signature,now);
    // Single speech is real visible UI state but the current TiDB dialogue table
    // requires a two-person conversation, so keep this card browser-local.
    townPutIntoHistory({
      id:'speech-'+now+'-'+who,
      at:now,members:[who],turns:[{speaker:who,text:original?.text||text,text_zh:original?.text_zh||''}],text:who+': '+text,
      __localOnly:true
    });
    return true;
  }

  function townConsumeNativeSpeech(speaker,visibleText,original){
    const who=String(speaker||'').trim().toUpperCase();
    const shown=String(visibleText||'').trim();
    if(!who||!shown)return false;

    const active=window.__townActiveDialogue;
    if(!active||!active.__staged||!Array.isArray(active.__expectedTurns)){
      return townAppendStandaloneSpeech(who,shown,original);
    }

    let index=Math.max(0,Number(active.__spokenIndex)||0);
    let selected=-1;
    for(let i=index;i<active.__expectedTurns.length;i++){
      if(String(active.__expectedTurns[i]&&active.__expectedTurns[i].speaker||'').trim().toUpperCase()===who){selected=i;break;}
    }
    if(selected<0)return townAppendStandaloneSpeech(who,shown,original);

    const turn=active.__expectedTurns[selected]||{};
    active.turns.push({
      speaker:String(turn.speaker||speaker||''),
      text:String(turn.text||shown||''),
      text_zh:String(turn.text_zh||turn.textZh||'')
    });
    active.__spokenIndex=selected+1;
    active.text=active.turns.map(t=>String(t.speaker||'')+': '+String(t.text||'')).join(' ').slice(0,1200);
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
          const original=agent.__townSpeechTurn;
          const text=String(agent.chatText?(original?.text||agent.chatText):'').trim();
          const previous=String(townNativeSpeechState.get(id)||'');
          if(text&&text!==previous)townConsumeNativeSpeech(id,text,original);
          townNativeSpeechState.set(id,text);
        });
        [...townNativeSpeechState.keys()].forEach(id=>{if(!liveIds.has(id))townNativeSpeechState.delete(id);});
      }
    }catch(_e){}
    requestAnimationFrame(townPollNativeSpeech);
  }
  requestAnimationFrame(townPollNativeSpeech);

  function townEnsureDialogueViewport(box){
    if(!box)return null;
    let state=window.__townDialogueViewport;
    if(!state){
      state={followLatest:true,top:0,mutating:false,dragging:false};
      window.__townDialogueViewport=state;
    }
    if(box.dataset.townViewportInstalled==='1')return state;
    box.dataset.townViewportInstalled='1';
    box.tabIndex=0;
    // Capture pointerdown at window level too: browser scrollbar thumbs do
    // not always bubble their pointer event through the scroll container.
    const markDragging=(event)=>{
      if(event&&event.target&& (event.target===box||box.contains(event.target)))state.dragging=true;
    };
    box.addEventListener('pointerdown',markDragging,{passive:true});
    window.addEventListener('pointerdown',markDragging,{capture:true,passive:true});
    const release=()=>{state.dragging=false;};
    window.addEventListener('pointerup',release,{passive:true});
    window.addEventListener('pointercancel',release,{passive:true});
    box.addEventListener('scroll',()=>{
      if(state.mutating)return;
      state.top=Math.max(0,box.scrollTop);
      const distance=Math.max(0,box.scrollHeight-box.scrollTop-box.clientHeight);
      // Only the user can change this flag because programmatic render writes
      // happen while mutating=true.
      state.followLatest=distance<=6;
    },{passive:true});
    window.__townDialogueFollowLatest=()=>!!state.followLatest;
    window.__townDialogueGoLatest=()=>{
      state.mutating=true;state.followLatest=true;
      box.scrollTop=box.scrollHeight;state.top=box.scrollTop;
      setTimeout(()=>{state.mutating=false;},0);
    };
    return state;
  }

'''
    if marker in html:
        html = html.replace(marker, helper + marker, 1)

    # Replace the old unconditional scroll-to-bottom renderer with one simple
    # viewport rule. DOM refreshes may update content, but they cannot move a
    # reader who left the bottom. The user's own scroll event updates the saved
    # top continuously, so upward and downward manual scrolling both stay fluid.
    html = html.replace(
        "    const items=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-8);",
        "    const viewport=townEnsureDialogueViewport(box);\n"
        "    if(viewport?.dragging)return;\n"
        "    const oldTop=box.scrollTop;\n"
        "    const followLatest=!viewport||viewport.followLatest;\n"
        "    if(viewport)viewport.mutating=true;\n"
        "    const items=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-40);",
        1,
    )
    html = html.replace(
        "    requestAnimationFrame(()=>{box.scrollTop=box.scrollHeight;syncTownDialoguePanelHeight();});",
        "    {\n"
        "      if(followLatest)box.scrollTop=box.scrollHeight;\n"
        "      else box.scrollTop=Math.min(oldTop,Math.max(0,box.scrollHeight-box.clientHeight));\n"
        "      if(viewport){viewport.top=box.scrollTop;viewport.mutating=false;}\n"
        "      syncTownDialoguePanelHeight();\n"
        "    }",
        1,
    )
    html = html.replace("syncTownDialoguePanelHeight();return;}\n    box.innerHTML=items.map", "syncTownDialoguePanelHeight();if(viewport)viewport.mutating=false;return;}\n    const nextMarkup=items.map", 1)
    html = html.replace("    }).join('');\n    {\n      if(followLatest)", "    }).join('');\n    if(box.innerHTML!==nextMarkup)box.innerHTML=nextMarkup;\n    {\n      if(followLatest)", 1)

    # Server-world refresh is historical data only. During local native playback
    # hide the complete persisted copy of that same conversation and retain the
    # progressively revealed local card plus single-speech cards.
    old_apply = "    if(Array.isArray(world?.recentDialogue)){window.__townDialogueHistory=world.recentDialogue.map(item=>({at:item.at,members:Array.isArray(item.members)?item.members:[],turns:Array.isArray(item.turns)?item.turns:[],text:item.text||''})).slice(-10);setTimeout(()=>{if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();},0);}" 
    new_apply = "    if(Array.isArray(world?.recentDialogue)){\n" \
        "      let incoming=world.recentDialogue.map(item=>({id:item.id,at:item.at,members:Array.isArray(item.members)?item.members:[],turns:Array.isArray(item.turns)?item.turns:[],text:item.text||''}));\n" \
        "      const active=window.__townActiveDialogue;\n" \
        "      if(active&&active.__staged&&typeof townDialogueMatchesActive==='function')incoming=incoming.filter(item=>!townDialogueMatchesActive(item,active));\n" \
        "      const current=Array.isArray(window.__townDialogueHistory)?Array.from(window.__townDialogueHistory):[];\n" \
        "      const local=current.filter(item=>item&&(item.__staged||item.__localOnly));\n" \
        "      const ids=new Set(incoming.map(item=>String(item.id||'')));\n" \
        "      local.forEach(item=>{if(!ids.has(String(item.id||'')))incoming.push(item);});\n" \
        "      incoming.sort((a,b)=>Number(a.at||0)-Number(b.at||0));\n" \
        "      window.__townDialogueHistory=incoming.slice(-40);\n" \
        "    }"
    html = html.replace(old_apply, new_apply, 1)

    # Shared runtime now owns persistence and exposes this function. Keep the
    # fallback assignment for compatibility with an older generated build.
    if "window.__townPostDialogueNow=postDialogue;" not in html:
        html = html.replace("  function wrapArray(value){", "  window.__townPostDialogueNow=postDialogue;\n\n  function wrapArray(value){", 1)

    return html

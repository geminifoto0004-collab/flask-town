"""Synchronize the dialogue sidebar with the native speech clock.

DeepSeek returns a whole multi-turn conversation at once, but the native town
engine speaks it turn-by-turn.  The sidebar must reveal the same turn only when
native `addLog` emits the corresponding speech line.  This patch also preserves
a user's manual scroll position instead of forcing the panel to the bottom on
every refresh.
"""


def patch_render_dialogue_sync(html: str) -> str:
    if "townConsumeSpokenDialogue" in html:
        return html

    # The dialogue-panel patch used to push the complete conversation before the
    # native actor animation began. Keep the expected turns off-screen and expose
    # only the turns that have actually been spoken.
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
      at:Date.now(),members:[from.name,to.name],turns:[],text:'',__staged:true,__expectedTurns:storedTurns,__spokenIndex:0
    };
    window.__townActiveDialogue=liveDialogue;
    window.__townDialogueHistory.push(liveDialogue);
    window.__townDialogueHistory=window.__townDialogueHistory.slice(-24);
    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();
    turns=turns.map(turn=>({...turn,text:dialogueText(turn)}));'''
    html = html.replace(old_store, new_store, 1)

    # Install a small turn consumer beside the existing sidebar renderer. The
    # native game already logs each speech line exactly when the speech bubble is
    # shown, so this event is the authoritative playback clock.
    marker = "  function installTownLanguageUi(){"
    helper = r'''  function townConsumeSpokenDialogue(message){
    const raw=String(message==null?'':message);
    const match=raw.match(/^💬\s*([^：:]+)[：:]\s*(.+)$/);
    if(!match)return false;
    const active=window.__townActiveDialogue;
    if(!active||!active.__staged||!Array.isArray(active.__expectedTurns))return false;
    const speaker=String(match[1]||'').trim().toUpperCase();
    let index=Math.max(0,Number(active.__spokenIndex)||0);
    let selected=-1;
    for(let i=index;i<active.__expectedTurns.length;i++){
      if(String(active.__expectedTurns[i]&&active.__expectedTurns[i].speaker||'').trim().toUpperCase()===speaker){selected=i;break;}
    }
    if(selected<0)return false;
    const turn=active.__expectedTurns[selected]||{};
    active.turns.push({speaker:String(turn.speaker||match[1]||''),text:String(turn.text||match[2]||''),text_zh:String(turn.text_zh||turn.textZh||'')});
    active.__spokenIndex=selected+1;
    active.text=active.turns.map(t=>String(t.speaker||'')+': '+String(t.text||'')).join(' ').slice(0,520);
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
  window.townConsumeSpokenDialogue=townConsumeSpokenDialogue;

'''
    if marker in html:
        html = html.replace(marker, helper + marker, 1)

    # Feed the actual native speech log into the staged dialogue card before the
    # ordinary status log translation is processed.
    html = html.replace(
        "      addLog=function(message){\n        const item={at:Date.now(),zh:String(message==null?'':message),es:translateTownLog(message,'es')};",
        "      addLog=function(message){\n        try{townConsumeSpokenDialogue(message);}catch(_e){}\n        const item={at:Date.now(),zh:String(message==null?'':message),es:translateTownLog(message,'es')};",
        1,
    )

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

    # The shared-history runtime normally replaces local history with TiDB on
    # every poll. Preserve the one currently playing staged card until all native
    # speech turns have fired, then persist it normally.
    html = html.replace(
        "    fetch('/api/town/dialogues?limit=12'",
        "    fetch('/api/town/dialogues?limit=24'",
        1,
    )
    html = html.replace(
        "        window.__townDialogueHistory=shared.slice(-12);",
        "        const staged=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).filter(x=>x&&x.__staged);\n"
        "        staged.forEach(chat=>{const id=dialogueId(chat);if(!ids.has(id))shared.push(chat);});\n"
        "        shared.sort((a,b)=>Number(a.at||0)-Number(b.at||0));\n"
        "        window.__townDialogueHistory=shared.slice(-24);",
        1,
    )

    # Expose the existing TiDB persistence function so the synchronizer can save
    # the dialogue only after its final spoken turn.
    html = html.replace(
        "  function wrapArray(value){",
        "  window.__townPostDialogueNow=postDialogue;\n\n  function wrapArray(value){",
        1,
    )
    return html

"""Render-page patch for a clearer dialogue sidebar and UI language toggles."""


def patch_render_dialogue_panel(html: str) -> str:
    if "town-side-panel" not in html:
        html = html.replace(
            "</style>",
            """
  #town-dock-layout{display:flex;align-items:flex-start;justify-content:center;gap:0;width:max-content;max-width:calc(100vw - 18px);margin:0 auto}
  #town-dock-layout>.town-main-root{flex:0 1 auto;min-width:0}
  #town-side-panel{position:relative;display:flex;flex-direction:column;gap:10px;flex:0 0 360px;width:360px;max-width:360px;height:640px;min-height:0;z-index:20;background:#1c2733;border:2px solid #1a2028;border-left:0;border-radius:0 10px 10px 0;box-shadow:none;padding:12px;color:#eef4ff;font:12px/1.45 "Segoe UI",Arial,sans-serif;overflow:hidden;box-sizing:border-box}
  #town-side-panel .panel-title{font-size:24px;font-weight:800;letter-spacing:.4px;color:#fff}
  #town-side-panel .panel-sub{font-size:12px;opacity:.8}
  #town-side-panel .panel-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  #town-side-panel label{display:flex;flex-direction:column;gap:4px;font-size:11px;color:#d6e4ff;flex:1 1 130px}
  #town-side-panel select{background:#243646;color:#fff;border:1px solid #4e6a84;border-radius:6px;padding:6px 8px;font-size:12px}
  #town-dialogue-list{overflow-y:scroll;overflow-x:hidden;display:flex;flex-direction:column;gap:10px;padding-right:6px;min-height:0;flex:1 1 auto;scrollbar-gutter:stable;overscroll-behavior:contain;overflow-anchor:none;touch-action:pan-y;scrollbar-width:auto;scrollbar-color:#8faac3 #111922}
  #town-dialogue-list::-webkit-scrollbar{width:16px}
  #town-dialogue-list::-webkit-scrollbar-track{background:#111922}
  #town-dialogue-list::-webkit-scrollbar-thumb{background:#8faac3;border:3px solid #111922;border-radius:8px;min-height:40px}
  #town-dialogue-list>.town-dialogue-card{flex-shrink:0}
  .town-dialogue-card{background:#111922;border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:10px}
  .town-dialogue-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;font-size:11px;color:#b8cae6}
  .town-dialogue-members{font-weight:700;color:#fff;letter-spacing:.3px}
  .town-dialogue-turns{display:flex;flex-direction:column;gap:7px}
  .town-dialogue-bubble{display:flex;flex-direction:column;max-width:88%}
  .town-dialogue-bubble.right{margin-left:auto;align-items:flex-end}
  .town-dialogue-bubble.left{margin-right:auto;align-items:flex-start}
  .town-dialogue-speaker-chip{font-size:10px;font-weight:700;letter-spacing:.3px;color:#d0def5;margin-bottom:3px}
  .town-dialogue-line{font-size:14px;line-height:1.5;word-break:break-word;padding:8px 10px;border-radius:12px}
  .town-dialogue-bubble.left .town-dialogue-line{background:#f4f7fb;color:#111}
  .town-dialogue-bubble.right .town-dialogue-line{background:#3d5a77;color:#fff}
  .town-dialogue-empty{background:#111922;border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:12px;font-size:14px}
  @media (max-width: 1180px){
    #town-dock-layout{flex-direction:column;max-width:100vw;width:100%}
    #town-side-panel{width:auto;max-width:none;height:320px;min-height:260px;border-left:2px solid #1a2028;border-top:0;border-radius:0 0 10px 10px}
  }
</style>""",
            1,
        )

    marker = "  function applyAiTownActions(actions=[]){"
    if "function ensureTownSidePanel()" not in html and marker in html:
        helper = r'''  const TOWN_UI_PREF_KEY='town-ui-prefs-v2';
  function loadTownUiPrefs(){
    try{
      const raw=localStorage.getItem(TOWN_UI_PREF_KEY);
      const prefs=raw?JSON.parse(raw):{};
      return {
        dialogueLang:prefs&&prefs.dialogueLang==='zh'?'zh':'es',
        statusLang:prefs&&prefs.statusLang==='es'?'es':'zh'
      };
    }catch(_){return {dialogueLang:'zh',statusLang:'zh'};}
  }
  function saveTownUiPrefs(){
    try{localStorage.setItem(TOWN_UI_PREF_KEY,JSON.stringify(window.__townUiPrefs||{dialogueLang:'es',statusLang:'zh'}));}catch(_){ }
  }
  window.__townUiPrefs=window.__townUiPrefs||loadTownUiPrefs();
  window.__townDialogueHistory=Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[];
  window.__townStatusHistory=Array.isArray(window.__townStatusHistory)?window.__townStatusHistory:[];
  function escapeHtml(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function dialogueText(turn){
    if(window.TownLanguage)return window.TownLanguage.text(turn);
    if((window.__townUiPrefs||{}).dialogueLang==='zh'&&turn&&turn.text_zh)return String(turn.text_zh);
    return String((turn&&turn.text)||'');
  }
  function translateTownLog(message, lang){
    const raw=String(message==null?'':message);
    if(lang!=='es')return raw;
    if(!window.TownLanguage)return raw;
    const translated=window.TownLanguage.text({text:raw},'es');
    // Keep a readable source until the asynchronous semantic translation is
    // ready; the language-change event will update the existing log node.
    return translated.startsWith('[Traducción pendiente]')?raw:translated;
  }
  function refreshTownLogLanguage(){
    const lang=(window.__townUiPrefs||{}).statusLang==='es'?'es':'zh';
    document.querySelectorAll('#eventLog [data-town-status-zh]').forEach(node=>{
      const zh=String(node.dataset.townStatusZh||'');
      if(lang!=='es'){node.textContent='> '+zh;return;}
      const es=translateTownLog(zh,'es');
      node.dataset.townStatusEs=es;
      node.textContent='> '+es;
    });
  }
  function findTownRootNode(){
    const labels=['AI 立即想一下','船抵港','快速完成','CUSTOMS AGENT TOWN'];
    let seed=Array.from(document.querySelectorAll('button,div,section,main')).find(el=>{
      const t=String(el.textContent||'');
      return labels.filter(v=>t.includes(v)).length>=3;
    });
    if(!seed)seed=Array.from(document.querySelectorAll('button,div,section,main')).find(el=>String(el.textContent||'').includes('AI 立即想一下'));
    let node=seed;
    while(node&&node.parentElement&&node.parentElement!==document.body){
      const text=String(node.textContent||'');
      if(text.includes('CUSTOMS AGENT TOWN')&&text.includes('AI 立即想一下')&&text.includes('船抵港'))return node;
      node=node.parentElement;
    }
    return seed||document.body.firstElementChild||document.body;
  }
  function syncTownDialoguePanelHeight(){
    const panel=document.getElementById('town-side-panel');
    const game=document.querySelector('#customs-sim .game-wrap');
    if(!panel||!game)return;
    if(window.matchMedia('(max-width:1180px)').matches){panel.style.height='320px';return;}
    panel.style.height=Math.max(320,Math.round(game.getBoundingClientRect().height))+'px';
  }
  function ensureTownSidePanel(){
    let panel=document.getElementById('town-side-panel');
    if(panel)return panel;
    panel=document.createElement('div');
    panel.id='town-side-panel';
    panel.innerHTML=''
      +'<div class="panel-title">IQUIQUE · AI DIALOGUE</div>'
      +'<div class="panel-sub">對話顯示在右側；像聊天視窗一樣清楚。下方狀態可切換中文 / Español。</div>'
      +'<div class="panel-row">'
      +'<label>對話 / Diálogo<select id="town-dialogue-lang"><option value="es">Español</option><option value="zh">中文</option></select></label>'
      +'<label>狀態 / Estado<select id="town-status-lang"><option value="zh">中文</option><option value="es">Español</option></select></label>'
      +'</div>'
      +'<div id="town-dialogue-list"></div>';
    const root=findTownRootNode();
    let dock=document.getElementById('town-dock-layout');
    if(!dock){
      dock=document.createElement('div');
      dock.id='town-dock-layout';
      root.classList.add('town-main-root');
      root.parentNode.insertBefore(dock,root);
      dock.appendChild(root);
    }
    dock.appendChild(panel);
    const dialogueSel=panel.querySelector('#town-dialogue-lang');
    const statusSel=panel.querySelector('#town-status-lang');
    dialogueSel.value=(window.__townUiPrefs||{}).dialogueLang||'es';
    statusSel.value=(window.__townUiPrefs||{}).statusLang||'zh';
    dialogueSel.addEventListener('change',()=>{window.__townUiPrefs.dialogueLang=dialogueSel.value;saveTownUiPrefs();window.dispatchEvent(new Event('town-language-change'));});
    window.addEventListener('town-language-change',()=>{
      agents.forEach(a=>{if(a.chatText&&a.__townSpeechTurn)a.chatText=dialogueText(a.__townSpeechTurn);});
      refreshTownLogLanguage();
      renderDialogueSidebar();
    });
    statusSel.addEventListener('change',()=>{window.__townUiPrefs.statusLang=statusSel.value;saveTownUiPrefs();if(typeof addLog==='function')addLog(statusSel.value==='es'?'Idioma del registro cambiado a Español':'狀態列語言已切換為中文');refreshTownLogLanguage();});
    setTimeout(syncTownDialoguePanelHeight,0);
    if('ResizeObserver' in window){
      const game=document.querySelector('#customs-sim .game-wrap');
      if(game)new ResizeObserver(syncTownDialoguePanelHeight).observe(game);
    }
    window.addEventListener('resize',syncTownDialoguePanelHeight);
    return panel;
  }
  function renderDialogueSidebar(){
    const panel=ensureTownSidePanel();
    const box=panel.querySelector('#town-dialogue-list');
    const items=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-8);
    if(!items.length){box.innerHTML='<div class="town-dialogue-empty">尚無對話 / Aún no hay diálogo.</div>';syncTownDialoguePanelHeight();return;}
    box.innerHTML=items.map(item=>{
      const members=(Array.isArray(item.members)?item.members:[]).slice(0,2);
      const first=members[0]||'MIA';
      const turns=(Array.isArray(item.turns)?item.turns:[]).map(turn=>{
        const side=String(turn.speaker||'')===first?'left':'right';
        return '<div class="town-dialogue-bubble '+side+'"><div class="town-dialogue-speaker-chip">'+escapeHtml(turn.speaker||'?')+'</div><div class="town-dialogue-line">'+escapeHtml(dialogueText(turn))+'</div></div>';
      }).join('');
      const stamp=item.at?new Date(item.at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'';
      return '<div class="town-dialogue-card"><div class="town-dialogue-head"><span class="town-dialogue-members">'+escapeHtml(members.join(' ↔ ')||'MIA ↔ ANA')+'</span><span>'+escapeHtml(stamp)+'</span></div><div class="town-dialogue-turns">'+(turns||('<div class="town-dialogue-bubble left"><div class="town-dialogue-line">'+escapeHtml(item.text||'')+'</div></div>'))+'</div></div>';
    }).join('');
    requestAnimationFrame(()=>{box.scrollTop=box.scrollHeight;syncTownDialoguePanelHeight();});
  }
  function installTownLanguageUi(){
    if(window.__townLangUiInstalled)return;
    window.__townLangUiInstalled=true;
    ensureTownSidePanel();
    if(typeof addLog==='function'&&!window.__townAddLogWrapped){
      window.__townRawAddLog=addLog;
      addLog=function(message){
        const zh=String(message==null?'':message);
        const statusLang=(window.__townUiPrefs||{}).statusLang==='es'?'es':'zh';
        const item={at:Date.now(),zh,es:statusLang==='es'?translateTownLog(zh,'es'):zh};
        window.__townStatusHistory=Array.isArray(window.__townStatusHistory)?window.__townStatusHistory:[];
        window.__townStatusHistory.push(item);
        window.__townStatusHistory=window.__townStatusHistory.slice(-120);
        const result=window.__townRawAddLog((window.__townUiPrefs||{}).statusLang==='es'?item.es:item.zh);
        const node=document.querySelector('#eventLog')?.firstElementChild;
        if(node){node.dataset.townStatusZh=item.zh;node.dataset.townStatusEs=item.es;}
        return result;
      };
      window.__townAddLogWrapped=true;
    }
    renderDialogueSidebar();
  }
  setTimeout(installTownLanguageUi,0);

'''
        html = html.replace(marker, helper + marker, 1)

    html = html.replace(
        "    if(!turns.length)return;\n    const midX=",
        "    if(!turns.length)return;\n"
        "    window.__townDialogueHistory=Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[];\n"
        "    const storedTurns=turns.map(turn=>({speaker:String(turn.speaker||''),text:String(turn.text||''),text_zh:String(turn.text_zh||'')}));\n"
        "    window.__townDialogueHistory.push({at:Date.now(),members:[from.name,to.name],turns:storedTurns,text:storedTurns.map(turn=>turn.speaker+': '+(turn.text||'')).join(' ').slice(0,520)});\n"
        "    window.__townDialogueHistory=window.__townDialogueHistory.slice(-10);\n"
        "    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();\n"
        "    turns=turns.map(turn=>({...turn,text:dialogueText(turn)}));\n"
        "    const midX=",
        1,
    )

    html = html.replace(
        "  function applyServerWorld(world){",
        "  function applyServerWorld(world){\n"
        "    if(Array.isArray(world?.recentDialogue)){window.__townDialogueHistory=world.recentDialogue.map(item=>({at:item.at,members:Array.isArray(item.members)?item.members:[],turns:Array.isArray(item.turns)?item.turns:[],text:item.text||''})).slice(-10);setTimeout(()=>{if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();},0);}",
        1,
    )

    return html

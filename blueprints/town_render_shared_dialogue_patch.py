"""Shared TiDB dialogue history without fighting the native live speech UI.

The browser keeps local speech responsive and persists completed conversations
asynchronously. Shared TiDB history is reconciled only when its actual content
changes; unchanged polling must not rebuild the sidebar or steal scroll input.
"""


def patch_render_shared_dialogue(html: str) -> str:
    css = r'''
<style id="town-shared-dialogue-style">
#town-side-panel>.panel-title,#town-side-panel>.panel-sub{display:none!important}
#town-side-panel{padding-top:10px!important}
#town-side-panel>#town-dialogue-list{flex:1 1 auto!important;min-height:0!important}
#town-inline-language-row{display:flex!important;align-items:center!important;gap:8px!important;margin:0!important;padding:0!important;border:0!important;flex:0 0 auto!important}
#town-inline-language-row label{display:flex!important;flex-direction:row!important;align-items:center!important;gap:5px!important;font-size:12px!important;color:inherit!important}
#town-inline-language-row select{min-height:44px!important;padding:7px 9px!important;background:light-dark(#f4efe3,#202936)!important;color:inherit!important;border:2px solid light-dark(#655d50,#3c4657)!important;font:inherit!important;font-weight:700!important}
@media(max-width:700px){#town-inline-language-row{width:100%;flex-wrap:wrap}}
</style>
'''
    js = r'''
<script id="town-shared-dialogue-runtime">
(()=>{
  const app=document.getElementById('customs-sim');
  if(!app)return;

  function moveLanguageControls(){
    const panel=document.getElementById('town-side-panel');
    const controls=app.querySelector('.controls');
    if(!panel||!controls)return;
    panel.querySelectorAll('.panel-title,.panel-sub').forEach(el=>el.remove());
    let row=panel.querySelector('.panel-row');
    if(!row)return;
    row.id='town-inline-language-row';
    const auto=app.querySelector('#aiAutoBtn');
    if(auto&&auto.parentNode===controls)auto.insertAdjacentElement('afterend',row);
    else controls.appendChild(row);
  }

  let backing=Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[];
  let proxy=null;
  const alreadyPosted=new Set();
  const pendingById=new Map();
  let lastSharedSignature='';

  function dialogueId(chat){
    if(chat&&chat.id)return String(chat.id);
    const members=Array.isArray(chat&&chat.members)?chat.members.join('-'):'chat';
    return members+'@'+String(chat&&chat.at||'');
  }

  function dialogueSignature(items){
    return (Array.isArray(items)?items:[]).map(chat=>{
      const turns=Array.isArray(chat&&chat.turns)?chat.turns:[];
      const tail=turns.length?turns[turns.length-1]||{}:{};
      return dialogueId(chat)+':'+turns.length+':'+String(tail.speaker||'')+':'+String(tail.text||tail.text_zh||'').slice(0,80);
    }).join('|');
  }

  function renderNow(){
    if(typeof renderDialogueSidebar==='function'){
      try{renderDialogueSidebar();}catch(_e){}
    }
  }

  function postDialogue(chat){
    if(!chat||chat.__localOnly||chat.__staged||!Array.isArray(chat.turns)||!chat.turns.length)return;
    const id=dialogueId(chat);
    if(alreadyPosted.has(id))return;
    alreadyPosted.add(id);
    const payload={
      ...chat,
      id,
      source:'browser',
      turns:chat.turns.map(turn=>({
        speaker:String(turn&&turn.speaker||''),
        text:String(turn&&turn.text||''),
        text_zh:String(turn&&turn.text_zh||turn&&turn.textZh||'')
      }))
    };
    pendingById.set(id,payload);
    fetch('/api/town/dialogues',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({dialogue:payload})})
      .then(r=>r.ok?r.json():Promise.reject(new Error('dialogue save failed')))
      .then(()=>{pendingById.delete(id);setTimeout(refreshSharedHistory,80);})
      .catch(()=>{alreadyPosted.delete(id);pendingById.delete(id);});
  }

  function wrapArray(value){
    const arr=Array.isArray(value)?value:[];
    return new Proxy(arr,{
      get(target,prop,receiver){
        if(prop==='push')return (...items)=>{
          const result=Array.prototype.push.apply(target,items);
          renderNow();
          items.forEach(postDialogue);
          return result;
        };
        return Reflect.get(target,prop,receiver);
      }
    });
  }

  try{
    proxy=wrapArray(backing);
    Object.defineProperty(window,'__townDialogueHistory',{
      configurable:true,
      enumerable:true,
      get(){return proxy;},
      set(value){
        if(value===proxy)return;
        backing=Array.isArray(value)?value:[];
        proxy=wrapArray(backing);
        renderNow();
      }
    });
  }catch(_e){}

  let refreshing=false;
  function refreshSharedHistory(){
    if(refreshing)return;
    refreshing=true;
    fetch('/api/town/dialogues?limit=24',{headers:{'Accept':'application/json'},cache:'no-store'})
      .then(r=>r.ok?r.json():null)
      .then(data=>{
        if(!data||!Array.isArray(data.dialogues))return;
        const shared=data.dialogues.map(chat=>({
          id:chat.id,
          at:chat.at,
          members:Array.isArray(chat.members)?chat.members:[],
          turns:Array.isArray(chat.turns)?chat.turns.map(turn=>({speaker:turn.speaker,text:turn.text,text_zh:turn.text_zh,textZh:turn.text_zh})):[],
          text:chat.text||''
        }));

        // Dialogue currently being revealed by native speech bubbles owns its
        // live progress. Do not let a complete TiDB copy jump ahead of it.
        const active=window.__townActiveDialogue;
        if(active&&active.__staged&&typeof window.__townDialogueMatchesActive==='function'){
          for(let i=shared.length-1;i>=0;i--){
            if(window.__townDialogueMatchesActive(shared[i],active))shared.splice(i,1);
          }
        }

        const ids=new Set(shared.map(dialogueId));
        pendingById.forEach((chat,id)=>{if(!ids.has(id))shared.push(chat);});

        // Keep local-only single speech and the staged live conversation. They
        // are presentation state, not database history.
        const local=(Array.isArray(window.__townDialogueHistory)?Array.from(window.__townDialogueHistory):[])
          .filter(chat=>chat&&(chat.__staged||chat.__localOnly));
        local.forEach(chat=>{const id=dialogueId(chat);if(!ids.has(id)){shared.push(chat);ids.add(id);}});
        shared.sort((a,b)=>Number(a.at||0)-Number(b.at||0));
        const next=shared.slice(-40);
        const signature=dialogueSignature(next);
        if(signature===lastSharedSignature)return;
        lastSharedSignature=signature;
        window.__townDialogueHistory=next;
      })
      .catch(()=>{})
      .finally(()=>{refreshing=false;});
  }

  window.__townPostDialogueNow=postDialogue;
  window.__townRefreshSharedDialogue=refreshSharedHistory;
  moveLanguageControls();
  refreshSharedHistory();
  // Shared persistence does not need frame-like polling. Local bubbles update
  // instantly; remote/history reconciliation every 2.5 s is sufficient and
  // avoids constantly rebuilding a panel the user may be scrolling.
  setInterval(refreshSharedHistory,2500);
  setTimeout(moveLanguageControls,150);
})();
</script>
'''
    if 'town-shared-dialogue-style' not in html:
        html = html.replace('</head>', css + '</head>', 1) if '</head>' in html else css + html
    if 'town-shared-dialogue-runtime' not in html:
        html = html.replace('</body>', js + '</body>', 1) if '</body>' in html else html + js
    return html

"""Keep the dialogue sidebar fixed while the user reads older messages.

The shared TiDB dialogue feed refreshes frequently and the native speech clock can
also re-render the sidebar several times per conversation.  A user who manually
scrolls away from the bottom owns the viewport until they themselves return to
the bottom.  Programmatic renders may update DOM content but may not steal the
reading position.
"""


def patch_render_dialogue_scroll_lock(html: str) -> str:
    if "town-dialogue-scroll-lock-runtime" in html:
        return html

    js = r'''
<script id="town-dialogue-scroll-lock-runtime">
(()=>{
  const STATE={reading:false,top:0,userInput:false,restoreQueued:false};

  function getBox(){return document.getElementById('town-dialogue-list');}
  function distanceFromBottom(box){return Math.max(0,box.scrollHeight-box.scrollTop-box.clientHeight);}
  function atBottom(box){return distanceFromBottom(box)<=28;}

  function remember(box){
    if(!box)return;
    STATE.top=Math.max(0,box.scrollTop);
  }

  function userBegins(box){
    STATE.userInput=true;
    if(box)remember(box);
  }
  function userEnds(){
    setTimeout(()=>{STATE.userInput=false;},120);
  }

  function onUserScroll(box){
    if(!box||!STATE.userInput)return;
    if(atBottom(box)){
      STATE.reading=false;
      STATE.top=box.scrollTop;
    }else{
      STATE.reading=true;
      remember(box);
    }
  }

  function restore(box){
    if(!box||!STATE.reading||STATE.restoreQueued)return;
    STATE.restoreQueued=true;
    requestAnimationFrame(()=>{
      // Run one frame after the town renderer's own "follow latest" RAF.  This
      // deliberately wins the last write to scrollTop while history is locked.
      requestAnimationFrame(()=>{
        STATE.restoreQueued=false;
        if(!STATE.reading)return;
        const maxTop=Math.max(0,box.scrollHeight-box.clientHeight);
        box.scrollTop=Math.min(STATE.top,maxTop);
      });
    });
  }

  function install(){
    const box=getBox();
    if(!box||box.dataset.townHistoryScrollLock==='1')return false;
    box.dataset.townHistoryScrollLock='1';
    if(!box.hasAttribute('tabindex'))box.setAttribute('tabindex','0');

    box.addEventListener('wheel',()=>userBegins(box),{passive:true});
    box.addEventListener('touchstart',()=>userBegins(box),{passive:true});
    box.addEventListener('touchmove',()=>userBegins(box),{passive:true});
    box.addEventListener('pointerdown',()=>userBegins(box),{passive:true});
    box.addEventListener('pointerup',userEnds,{passive:true});
    box.addEventListener('pointercancel',userEnds,{passive:true});
    box.addEventListener('touchend',userEnds,{passive:true});
    box.addEventListener('wheel',userEnds,{passive:true});
    box.addEventListener('keydown',event=>{
      const keys=['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '];
      if(!keys.includes(event.key))return;
      userBegins(box);
      setTimeout(()=>{onUserScroll(box);userEnds();},0);
    });
    box.addEventListener('scroll',()=>{
      if(STATE.userInput)onUserScroll(box);
      else if(STATE.reading)restore(box);
    },{passive:true});

    const observer=new MutationObserver(()=>{
      if(STATE.reading)restore(box);
    });
    observer.observe(box,{childList:true,subtree:true,characterData:true});

    // Expose tiny diagnostics so a future UI/debug check can tell whether the
    // browser is intentionally holding history rather than following latest.
    window.__townDialogueReadingHistory=()=>STATE.reading;
    window.__townDialogueUnlockScroll=()=>{
      STATE.reading=false;
      box.scrollTop=box.scrollHeight;
      STATE.top=box.scrollTop;
    };
    return true;
  }

  if(!install()){
    const observer=new MutationObserver(()=>{if(install())observer.disconnect();});
    observer.observe(document.documentElement,{childList:true,subtree:true});
    setTimeout(install,250);
  }
})();
</script>
'''
    return html.replace('</body>', js + '</body>', 1) if '</body>' in html else html + js

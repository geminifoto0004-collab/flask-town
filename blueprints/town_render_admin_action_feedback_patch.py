"""Make admin story commands visibly execute transient actions on Render."""


def patch_render_admin_action_feedback(html: str) -> str:
    # The main town script keeps applyAiTownActions inside its own IIFE. Expose a
    # tiny safe bridge before that IIFE closes so the later Render admin overlay
    # can dispatch transient actions without duplicating the whole engine.
    html = html.replace(
        "  bootWorld();\n})();",
        "  window.__townApplyAiTownActions=applyAiTownActions;\n  bootWorld();\n})();",
        1,
    )

    html = html.replace(
        "promptWrap.innerHTML='<span>AI 指令</span><input id=\"town-world-prompt-input\" type=\"text\" maxlength=\"180\" placeholder=\"例如：道路來一台車、Oscar 帶晚餐來探 MIA\"><button id=\"town-world-prompt-run\" type=\"button\">✨ 執行</button>';",
        "promptWrap.innerHTML='<span>AI 劇情</span><input id=\"town-world-prompt-input\" type=\"text\" maxlength=\"300\" placeholder=\"告訴 AI 核心劇情；沒指定的細節讓它自己導演\"><button id=\"town-world-prompt-run\" type=\"button\">✨ 執行</button>';",
        1,
    )
    html = html.replace(
        "log('AI 已收到指令：'+prompt+'（已送出，不必重按）');",
        "log('AI 已收到劇情種子：'+prompt+'（明確指定的核心會保留，其餘由 AI 導演；超過 15 秒仍會繼續等待，不必重按）');",
        1,
    )

    # The old Render overlay aborted the browser request at 15 seconds. That can
    # create a false failure while Flask/DeepSeek is still finishing the same
    # command. Keep the request alive; after 15 seconds only change the visible
    # status so the user knows the same command is still being processed.
    html = html.replace(
        "    const controller=new AbortController();\n    let timer=null;",
        "    let timer=null;\n    let softNoticeShown=false;",
        1,
    )
    html = html.replace(
        "    timer=setInterval(()=>{\n      const sec=Math.floor((Date.now()-started)/1000);\n      if(btn)btn.textContent='⏳ '+sec+'s · 已送出';\n      setStatus(sec<3?'AI 已收到指令 · 正在理解':'AI 正在轉成世界動作 · '+sec+' 秒');\n    },1000);\n    const hardTimer=setTimeout(()=>controller.abort(),15000);",
        "    timer=setInterval(()=>{\n      const sec=Math.floor((Date.now()-started)/1000);\n      if(btn)btn.textContent='⏳ '+sec+'s · 已送出';\n      setStatus(sec<3?'AI 已收到指令 · 正在理解':sec<15?'AI 正在轉成世界動作 · '+sec+' 秒':'AI 還在導演中 · '+sec+' 秒，請勿重按');\n      if(sec>=15&&!softNoticeShown){softNoticeShown=true;log('AI 已思考超過 15 秒，但同一個指令仍在處理；不會取消。');}\n    },1000);",
        1,
    )
    html = html.replace(
        "      const r=await fetch('/api/town/admin/command',{method:'POST',credentials:'include',signal:controller.signal,headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({prompt,command_id:commandId})});",
        "      const r=await fetch('/api/town/admin/command',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({prompt,command_id:commandId})});",
        1,
    )
    html = html.replace(
        "    }catch(err){\n      const timedOut=err&&err.name==='AbortError';\n      log(timedOut?'AI 指令超過 15 秒，已停止等待；按鈕已恢復':'AI 指令失敗：'+String(err&&err.message||err));\n      setStatus(timedOut?'AI 等待超時，可再試一次':'AI 指令失敗');\n    }finally{\n      clearTimeout(hardTimer);if(timer)clearInterval(timer);commandBusy=false;",
        "    }catch(err){\n      log('AI 指令失敗：'+String(err&&err.message||err));\n      setStatus('AI 指令失敗');\n    }finally{\n      if(timer)clearInterval(timer);commandBusy=false;",
        1,
    )

    old = """      if(actions.length)log('AI 真正下令：'+actions.map(a=>String(a.type||'動作')+(a.name?' '+a.name:'')+(a.target?' → '+a.target:'')).join('；'));
      if(data.duplicate)log('這個 command_id 已執行過，本次沒有重複建立物件');"""
    new = """      if(data.thought)log('AI 導演改編：'+String(data.thought).slice(0,300));
      if(actions.length){
        log('AI 真正執行：'+actions.map(a=>String(a.type||'動作')+(a.agent?' '+a.agent:'')+(a.name?' '+a.name:'')+(a.action?' · '+a.action:'')+(a.target?' → '+a.target:'')+(a.group?' · '+a.group:'')).join('；'));
        try{
          if(typeof window.__townApplyAiTownActions==='function')window.__townApplyAiTownActions(actions);
          else log('AI 即時動作橋接尚未就緒，等待共同世界同步');
        }catch(err){log('AI 即時動作顯示失敗：'+String(err&&err.message||err));}
      }
      const hasGenericSpawn=actions.some(a=>a&&(a.type==='spawn_entity'||a.type==='spawn_from_template'));
      const serverEntities=Array.isArray(data&&data.world&&data.world.genericEntities)?data.world.genericEntities:[];
      try{
        if(data&&data.world&&typeof window.__townMergeGenericWorld==='function'){
          window.__townMergeGenericWorld(data.world);
          if(typeof window.__townInvalidateWorldFetch==='function')window.__townInvalidateWorldFetch();
        }
      }catch(err){log('共同世界即時同步失敗：'+String(err&&err.message||err));}
      if(hasGenericSpawn){
        const rendererCount=typeof window.__townGenericEntityCount==='function'?window.__townGenericEntityCount():'未連接';
        log('共同世界實體：後端 '+serverEntities.length+' / renderer '+rendererCount);
        if(data.spawn_persistence_repaired)log('生成實體原本未落地，伺服器已自動補寫 TiDB');
        if(Array.isArray(data.missing_spawn_ids_after_repair)&&data.missing_spawn_ids_after_repair.length){
          log('生成實體仍未落地：'+data.missing_spawn_ids_after_repair.join(', '));
        }
        if(typeof window.__townMergeGenericWorld!=='function')log('generic renderer bridge 未連接');
      }
      if(data.director_note)log('AI 優化：'+String(data.director_note).slice(0,180));
      if(data.duplicate)log('這個 command_id 已執行過，本次沒有重複建立物件');"""
    html = html.replace(old, new, 1)
    return html

"""Final Render HTML fixes for bilingual dialogue playback and sidebar history."""


def patch_render_dialogue_fix(html: str) -> str:
    # Default to Chinese unless the user explicitly selected Spanish before.
    html = html.replace(
        "dialogueLang:prefs&&prefs.dialogueLang==='zh'?'zh':'es',",
        "dialogueLang:prefs&&prefs.dialogueLang==='es'?'es':'zh',",
    )

    # Preserve the Traditional-Chinese translation coming from DeepSeek instead
    # of dropping it when the browser normalizes an agent_chat action.
    html = html.replace(
        "      text:String(turn?.text||turn?.message||'').slice(0,140)\n    })).filter(turn=>turn.text&&(turn.speaker===from.name||turn.speaker===to.name));",
        "      text:String(turn?.text||turn?.message||'').slice(0,140),\n"
        "      text_zh:String(turn?.text_zh||turn?.textZh||'').slice(0,140)\n"
        "    })).filter(turn=>turn.text&&(turn.speaker===from.name||turn.speaker===to.name));",
        1,
    )

    # The profile patch already creates recent dialogue memory. Upgrade that
    # entry so the right-hand chat window receives every individual turn.
    html = html.replace(
        "    window.__townDialogueHistory.push({at:Date.now(),members:[from.name,to.name],text:turns.map(turn=>turn.speaker+': '+turn.text).join(' ').slice(0,520)});\n"
        "    window.__townDialogueHistory=window.__townDialogueHistory.slice(-8);",
        "    window.__townDialogueHistory.push({at:Date.now(),members:[from.name,to.name],turns:turns.map(turn=>({speaker:turn.speaker,text:turn.text,text_zh:turn.text_zh||''})),text:turns.map(turn=>turn.speaker+': '+turn.text).join(' ').slice(0,520)});\n"
        "    window.__townDialogueHistory=window.__townDialogueHistory.slice(-8);\n"
        "    if(typeof renderDialogueSidebar==='function')renderDialogueSidebar();",
        1,
    )

    # The speech bubble on the canvas follows the same language switch as the
    # docked dialogue panel. Each chat turn remains a separate turn/line.
    html = html.replace(
        "      speaker.chatText=turn.text;speaker.chatTimer=Math.max(5.5,Math.min(10,3.5+turn.text.length*.055));\n"
        "      listener.chatText='';listener.chatTimer=0;\n"
        "      addLog('💬 '+agentLabel(speaker)+'：'+turn.text);",
        "      speaker.__townSpeechTurn={...turn};\n"
        "      const shownTurnText=dialogueText(turn);\n"
        "      speaker.chatText=shownTurnText;speaker.chatTimer=Math.max(5.5,Math.min(10,3.5+shownTurnText.length*.055));\n"
        "      listener.chatText='';listener.chatTimer=0;\n"
        "      addLog('💬 '+agentLabel(speaker)+'：'+shownTurnText);",
        1,
    )

    # Single-character speech also follows the dialogue language selector.
    html = html.replace(
        "    const text=String(action.text||action.message||'').trim().slice(0,160);if(!text){addLog('AI 說話未執行：沒有台詞');return;}\n"
        "    a.chatText=text;a.chatTimer=Math.max(7,Math.min(18,4+text.length*.13));",
        "    const textEs=String(action.text||action.message||'').trim().slice(0,160),textZh=String(action.text_zh||action.textZh||'').trim().slice(0,160);\n"
        "    const text=(window.__townUiPrefs?.dialogueLang==='zh'&&textZh)?textZh:textEs;if(!text){addLog('AI 說話未執行：沒有台詞');return;}\n"
        "    a.chatText=text;a.chatTimer=Math.max(7,Math.min(18,4+text.length*.13));",
        1,
    )

    # The single-speech tool has its own normalizer in this snapshot.
    html = html.replace("    a.chatText=text;", "    a.__townSpeechTurn={text:String(action.text||action.message||''),text_zh:String(action.text_zh||action.textZh||'')};\n    a.chatText=dialogueText(a.__townSpeechTurn);", 1)

    # The older browser snapshot never registered the validated agent_say tool,
    # so valid solo lines were silently ignored by runDirectorTool. Keep one
    # renderer for solo and multi-turn speech and preserve both source fields.
    if "registerDirectorTool('agent_say'" not in html:
        marker = "  registerDirectorTool('night_preview',action=>{"
        helper = r'''  registerDirectorTool('agent_say',action=>{
    const a=agents.find(x=>x.name===String(action.agent||'').toUpperCase());
    if(!a){addLog('AI 說話未執行：找不到 '+String(action.agent||''));return;}
    if(a.task){addLog('AI 說話未執行：'+agentLabel(a)+' 正在處理船務');return;}
    if(!isAgentOnDuty(a)){addLog('AI 說話未執行：'+agentLabel(a)+' 現在不在班');return;}
    const turn={text:String(action.text||action.message||'').trim().slice(0,160),text_zh:String(action.text_zh||action.textZh||'').trim().slice(0,160)};
    if(!turn.text){addLog('AI 說話未執行：沒有台詞');return;}
    a.__townSpeechTurn=turn;
    a.chatText=dialogueText(turn);
    a.chatTimer=Math.max(7,Math.min(18,4+a.chatText.length*.13));
    a.intentLabel='正在說話';a.intentUntil=Date.now()+a.chatTimer*1000;
    addLog('💬 '+agentLabel(a)+'：'+a.chatText);
  });
'''
        if marker in html:
            html = html.replace(marker, helper + marker, 1)

    return html

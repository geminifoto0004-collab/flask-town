"""API-free local life loop for CUSTOMS AGENT TOWN.

Ordinary movement and short everyday conversations are generated in the browser
without calling DeepSeek.  They still use the normal agent_chat action path, so
speech bubbles, animation, shared dialogue history and TiDB persistence all stay
on the same pipeline.  DeepSeek remains responsible for richer narrative and
long-term evolution.
"""

from .town_render_performance_patch import patch_render_performance


def patch_render_local_life(html: str) -> str:
    marker = "  function sync(){"
    if "function townLocalLifeTick()" not in html and marker in html:
        helper = r'''  let localLifeTimer=rand(12,28);
  let localChatSeq=0;
  const localChatRecent=[];

  function localDisplayName(a){return String(a?.displayName||a?.name||'同事');}
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

  function localChatTurns(a,b){
    const an=localDisplayName(a),bn=localDisplayName(b);
    const topics=[
      [
        ['¿Cómo va la mañana?','今天上午過得怎麼樣？'],
        ['Con calma, pero todavía me quedan cosas por terminar.','還行，不過還有一些事情沒做完。'],
        ['Después hacemos una pausa corta.','等一下我們休息一下。'],
        ['Sí, y luego seguimos.','好，休息一下再繼續。']
      ],
      [
        ['¿Ya tomaste café?','你喝咖啡了嗎？'],
        ['Todavía no. Estaba pensando ir por uno.','還沒有，我正想去弄一杯。'],
        ['Si vas, avísame.','你要去的話叫我一下。'],
        ['Ya, vamos en un rato.','好，等一下我們一起去。']
      ],
      [
        ['¿Está tranquilo hoy por aquí?','今天這邊好像比較安靜？'],
        ['Por ahora sí, pero puede cambiar rápido.','目前是，不過很快也可能忙起來。'],
        ['Mejor adelantamos un poco entonces.','那我們先把事情做一些。'],
        ['Buena idea.','好主意。']
      ],
      [
        ['Tengo ganas de estirar las piernas un poco.','我有點想起來走一走。'],
        ['Yo también, llevo rato sentado.','我也是，坐很久了。'],
        ['Damos una vuelta corta y volvemos.','我們走一下再回來。'],
        ['Ya, pero cortito.','好，不過不要太久。']
      ],
      [
        ['¿Qué vas a hacer a la hora de almuerzo?','你午餐時間要做什麼？'],
        ['Todavía no sé. Quiero algo simple.','還不知道，我想吃簡單一點。'],
        ['Después vemos qué hay cerca.','等一下看看附近有什麼。'],
        ['Dale.','好啊。']
      ],
      [
        ['Hoy se siente largo el día.','今天感覺時間過得有點慢。'],
        ['Sí, hay días así.','對，有些日子就是這樣。'],
        ['Por lo menos estamos acompañados.','至少大家一起上班。'],
        ['Eso ayuda bastante.','這倒是有差。']
      ]
    ];
    const recentTopics=(Array.isArray(window.__townDialogueHistory)?window.__townDialogueHistory:[]).slice(-4).map(x=>String(x?.localTopic||''));
    let choices=topics.map((v,i)=>({v,i})).filter(x=>!recentTopics.includes(String(x.i)));
    if(!choices.length)choices=topics.map((v,i)=>({v,i}));
    const chosen=choices[Math.floor(Math.random()*choices.length)];
    const p=chosen.v;
    const turns=[
      {speaker:String(a.name),text:p[0][0],text_zh:p[0][1]},
      {speaker:String(b.name),text:p[1][0],text_zh:p[1][1]},
      {speaker:String(a.name),text:p[2][0],text_zh:p[2][1]},
      {speaker:String(b.name),text:p[3][0],text_zh:p[3][1]}
    ];
    turns.localTopic=String(chosen.i);
    return {turns,topic:String(chosen.i),an,bn};
  }

  function townLocalChat(live){
    const pair=pickLocalChatPair(live);if(!pair)return false;
    localChatRecent.push(pair.key);while(localChatRecent.length>3)localChatRecent.shift();
    const built=localChatTurns(pair.a,pair.b);
    localChatSeq++;
    applyAiTownActions([{type:'agent_chat',from:String(pair.a.name),to:String(pair.b.name),turns:built.turns,local:true,localTopic:built.topic,localChatId:'local-'+Date.now()+'-'+localChatSeq}]);
    return true;
  }

  function townLocalLifeTick(){
    if(!Array.isArray(agents)||!agents.length||typeof applyAiTownActions!=='function')return;
    const live=agents.filter(a=>a&&a.name&&a.state!=='workingShip'&&a.state!=='inspect'&&a.state!=='chat'&&!a.manualOffDuty);
    if(!live.length)return;
    const roll=Math.random();
    if(roll<.24&&live.length>1){townLocalChat(live);return;}
    const actor=live[Math.floor(Math.random()*live.length)];
    let action='wander';
    if(roll<.38)action='desk';
    else if(roll<.51)action='files';
    else if(roll<.62)action='coffee';
    else if(roll<.71)action='lookSea';
    else if(roll<.79)action='plant';
    else if(roll<.86)action='stretch';
    else if(roll<.93&&live.length>1)action='checkCoworker';
    applyAiTownActions([{type:'agent_action',agent:String(actor.name),action}]);
  }

'''
        html = html.replace(marker, helper + marker, 1)

    # Ordinary life runs locally and does not consume DeepSeek tokens.
    html = html.replace(
        "    updateDogs(dt);",
        "    updateDogs(dt);\n    localLifeTimer-=dt;if(localLifeTimer<=0){localLifeTimer=rand(16,34);townLocalLifeTick();}",
        1,
    )

    # DeepSeek is deliberately lower-frequency: it is for richer scenes and
    # persistent evolution, not for every coffee break or hallway conversation.
    html = html.replace("let aiAutoTimer=rand(35,75);", "let aiAutoTimer=rand(420,900);")
    html = html.replace("aiAutoTimer=rand(300,900);testDeepSeek();", "aiAutoTimer=rand(900,1800);testDeepSeek();")
    html = html.replace("aiAutoTimer=aiAuto?rand(15,35):999999;", "aiAutoTimer=aiAuto?rand(300,600):999999;")
    html = html.replace("if(aiAuto)aiAutoTimer=rand(8,22);", "if(aiAuto)aiAutoTimer=rand(300,600);")

    # Performance patch is intentionally last here: all earlier browser overlays
    # already exist, so it can dedupe their world fetches and defer their startup.
    return patch_render_performance(html)

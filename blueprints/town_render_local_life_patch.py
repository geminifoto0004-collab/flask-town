"""API-free local life loop for CUSTOMS AGENT TOWN.

The browser already owns movement/pathfinding/idle animation. This patch adds a
small local director that periodically asks those existing mechanics to perform
ordinary life actions without calling DeepSeek. DeepSeek remains responsible
for larger narrative/evolution events.
"""


def patch_render_local_life(html: str) -> str:
    marker = "  function sync(){"
    if "function townLocalLifeTick()" not in html and marker in html:
        helper = r'''  let localLifeTimer=rand(12,28);
  function townLocalLifeTick(){
    if(!Array.isArray(agents)||!agents.length||typeof applyAiTownActions!=='function')return;
    const live=agents.filter(a=>a&&a.name&&a.state!=='workingShip'&&a.state!=='inspect'&&a.state!=='chat');
    if(!live.length)return;
    const actor=live[Math.floor(Math.random()*live.length)];
    const roll=Math.random();
    let action='wander';
    if(roll<.18)action='desk';
    else if(roll<.34)action='files';
    else if(roll<.47)action='coffee';
    else if(roll<.58)action='lookSea';
    else if(roll<.67)action='plant';
    else if(roll<.74)action='stretch';
    else if(roll<.84&&live.length>1)action='chat';
    else if(roll<.92)action='checkCoworker';
    applyAiTownActions([{type:'agent_action',agent:String(actor.name),action}]);
  }

'''
        html = html.replace(marker, helper + marker, 1)

    # Run ordinary local life independently from DeepSeek/cron. Keep the cadence
    # deliberately human-scale so actors do not twitch between activities.
    html = html.replace(
        "    updateDogs(dt);",
        "    updateDogs(dt);\n    localLifeTimer-=dt;if(localLifeTimer<=0){localLifeTimer=rand(18,42);townLocalLifeTick();}",
        1,
    )

    # The existing auto-AI loop is still useful for richer decisions, but lower
    # its frequency because ordinary life is now local and free.
    html = html.replace("let aiAutoTimer=rand(35,75);", "let aiAutoTimer=rand(420,900);")
    html = html.replace("aiAutoTimer=rand(300,900);testDeepSeek();", "aiAutoTimer=rand(900,1800);testDeepSeek();")
    html = html.replace("aiAutoTimer=aiAuto?rand(15,35):999999;", "aiAutoTimer=aiAuto?rand(300,600):999999;")
    html = html.replace("if(aiAuto)aiAutoTimer=rand(8,22);", "if(aiAuto)aiAutoTimer=rand(300,600);")
    return html

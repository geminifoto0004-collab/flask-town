"""Depth-sort movable town actors and AI furniture on the Render page."""

def patch_render_depth(html: str) -> str:
    html = html.replace('    drawDesk(agents[0]);drawDesk(agents[1]);drawDesk(agents[2]);', '')
    html = html.replace('    drawBreakTable(layout.breakX,216);', '')
    # Wall-mounted items stay in the background. Floor furniture is drawn later
    # together with characters according to Y, so walking in front/behind an
    # object looks natural instead of every AI object covering every person.
    html = html.replace(
        "    aiFurniture.filter(f=>f.type==='wall_frame'||f.type==='notice_board').forEach(drawAiFurniture);\n"
        "    aiFurniture.filter(f=>f.type!=='wall_frame'&&f.type!=='notice_board'&&f.type!=='custom_object').forEach(drawAiFurniture);\n"
        "    aiFurniture.filter(f=>f.type==='custom_object').forEach(drawAiCustomObject);\n\n"
        "    plantStates.forEach(drawLifePlant);",
        "    aiFurniture.filter(f=>f.type==='wall_frame'||f.type==='notice_board').forEach(drawAiFurniture);\n\n"
        "    plantStates.forEach(drawLifePlant);",
    )

    old_frame = (
        "    if(!running)return;let dt=Math.min(.05,(now-last)/1000)*speed;last=now;update(dt);drawRoom();drawAtmosphere();"
        "agents.filter(a=>isAgentOnDuty(a)||a.task).slice().sort((a,b)=>a.y-b.y).forEach(drawAgent);"
        "agents.filter(a=>(isAgentOnDuty(a)||a.task)&&a.chatTimer>0&&a.chatText).forEach(a=>bubble(a,a.chatText));"
        "humanVisitors.slice().sort((a,b)=>a.y-b.y).forEach(drawHumanVisitor);"
        "aiFurniture.filter(f=>f.type==='wall_frame'||f.type==='notice_board').forEach(drawAiFurniture);"
        "aiFurniture.filter(f=>f.type!=='wall_frame'&&f.type!=='notice_board'&&f.type!=='custom_object').forEach(drawAiFurniture);"
        "aiFurniture.filter(f=>f.type==='custom_object').forEach(drawAiCustomObject);requestAnimationFrame(frame);"
    )
    new_frame = (
        "    if(!running)return;let dt=Math.min(.05,(now-last)/1000)*speed;last=now;update(dt);drawRoom();drawAtmosphere();\n"
        "    const depthItems=[];\n"
        "    window.__townSpeechDraws=[];\n"
        "    agents.forEach(a=>depthItems.push({y:228,draw:()=>drawDesk(a)}));\n"
        "    depthItems.push({y:240,draw:()=>drawBreakTable(officeLayout().breakX,216)});\n"
        "    agents.filter(a=>isAgentOnDuty(a)||a.task).forEach(a=>depthItems.push({y:a.y,draw:()=>drawAgent(a)}));\n"
        "    humanVisitors.forEach(v=>depthItems.push({y:v.y,draw:()=>drawHumanVisitor(v)}));\n"
        "    aiFurniture.filter(f=>f.type!=='wall_frame'&&f.type!=='notice_board').forEach(f=>depthItems.push({y:Number(f.y)||0,draw:()=>f.type==='custom_object'?drawAiCustomObject(f):drawAiFurniture(f)}));\n"
        "    (window.__townSceneLayers||[]).forEach(layer=>depthItems.push(...layer(dt)));\n"
        "    depthItems.sort((a,b)=>a.y-b.y).forEach(item=>{ctx.save();try{item.draw();}finally{ctx.restore();}});\n"
        "    (window.__townSpeechDraws||[]).forEach(draw=>{ctx.save();try{draw();}finally{ctx.restore();}});\n"
        "    agents.filter(a=>(isAgentOnDuty(a)||a.task)&&a.chatTimer>0&&a.chatText).forEach(a=>bubble(a,a.chatText));requestAnimationFrame(frame);"
    )
    if old_frame not in html:
        raise ValueError('Town depth frame anchor changed; refusing a partial build')
    html = html.replace(old_frame, new_frame, 1)
    # Failed pathfinding must not fall back to walking through the obstacle.
    html = html.replace('    return [{x:tx,y:ty}];\n  }\n  function dogMoveToward', '    return [];\n  }\n  function dogMoveToward', 1)
    # Reject blocked endpoints and blocked final segments, not just grid cells.
    html = html.replace('    const step=8,minX=40,maxX=592,minY=88,maxY=300;', '    if(pointBlocked(tx,ty))return [];\n    const step=8,minX=40,maxX=592,minY=88,maxY=300;', 1)
    html = html.replace('if(Math.hypot(cur.x-goal.x,cur.y-goal.y)<=step){', 'if(Math.hypot(cur.x-goal.x,cur.y-goal.y)<=step&&townSegmentClear(cur.x,cur.y,tx,ty)){', 1)
    start=html.index('  function moveToward(a,tx,ty,d){')
    end=html.index('  function rect(',start)
    html=html[:start]+r'''  function townSegmentClear(sx,sy,tx,ty){
    const n=Math.max(1,Math.ceil(Math.hypot(tx-sx,ty-sy)/2));
    for(let i=1;i<=n;i++)if(pointBlocked(sx+(tx-sx)*i/n,sy+(ty-sy)*i/n))return false;
    return true;
  }
  function townSafeGoal(tx,ty){
    tx=Math.max(40,Math.min(592,tx));ty=Math.max(88,Math.min(300,ty));
    if(!pointBlocked(tx,ty))return {x:tx,y:ty};
    for(let r=8;r<=160;r+=8)for(let i=0;i<32;i++){
      const x=tx+Math.cos(i*Math.PI/16)*r,y=ty+Math.sin(i*Math.PI/16)*r;
      if(x>=40&&x<=592&&y>=88&&y<=300&&!pointBlocked(x,y))return {x,y};
    }
    return null;
  }
  window.__townFindPath=(sx,sy,tx,ty)=>{
    const goal=townSafeGoal(tx,ty);
    return goal?makePath(sx,sy,goal.x,goal.y):[];
  };
  function moveToward(a,tx,ty,d){
    if(pointBlocked(a.x,a.y)){
      const recovered=townSafeGoal(a.x,a.y);if(!recovered)return false;
      a.x=recovered.x;a.y=recovered.y;a.path=[];a.pathTarget='';
    }
    const goal=townSafeGoal(tx,ty);if(!goal)return false;
    tx=goal.x;ty=goal.y;
    const targetKey=Math.round(tx)+','+Math.round(ty);
    if(a.pathTarget!==targetKey||!a.path.length){a.path=makePath(a.x,a.y,tx,ty);a.pathTarget=targetKey;}
    if(!a.path.length)return Math.hypot(tx-a.x,ty-a.y)<2;
    const p=a.path[0],dx=p.x-a.x,dy=p.y-a.y,dist=Math.hypot(dx,dy);
    const step=Math.min(dist,d),nx=dist?a.x+dx/dist*step:a.x,ny=dist?a.y+dy/dist*step:a.y;
    if(!townSegmentClear(a.x,a.y,nx,ny)){a.path=[];a.pathTarget='';return false;}
    a.walkPhase+=d*.25;a.x=nx;a.y=ny;
    if(dist<=d){a.path.shift();if(!a.path.length){a.pathTarget='';return true;}}
    return false;
  }
''' + html[end:]
    return html

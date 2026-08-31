"""Teach the existing generic-entity overlay to render TiDB visual templates.

This is a presentation patch only.  It extends the generic renderer with a
small original pixel primitive language (rect/ellipse) and semantic interaction
animation.  Story/content remains data-driven.
"""


def patch_render_template_composer(html: str) -> str:
    if 'town-template-composer-runtime' in html:
        return html

    marker = "  function draw(e){if(hidden.has(e.id))return;if(e.entityType==='vehicle')drawVehicle(e);else if(e.entityType==='animal')drawAnimal(e);else if(e.entityType==='item'||e.entityType==='decoration')drawItem(e);else drawHuman(e);}\n"
    replacement = r'''  function drawTemplate(e){
    const visual=e.visual&&typeof e.visual==='object'?e.visual:null;
    const parts=visual&&Array.isArray(visual.parts)?visual.parts:[];
    if(!parts.length)return false;
    const scale=Math.max(.35,Math.min(3,Number(visual.scale)||1));
    const moving=!!(e.current&&(e.current.type==='move_entity'||e.current.type==='leave'));
    const bob=moving?Math.round(Math.sin(performance.now()/95)*1):0;
    const facing=String(e.facing||visual.facing||'down');
    c.save();c.translate(Math.round(e.x),Math.round(e.y+bob));
    if(facing==='left')c.scale(-1,1);
    const ordered=parts.slice(0,48).sort((a,b)=>(Number(a.layer)||0)-(Number(b.layer)||0));
    ordered.forEach(p=>{
      const x=(Number(p.x)||0)*scale,y=(Number(p.y)||0)*scale,w=Math.max(2,(Number(p.w)||2)*scale),h=Math.max(2,(Number(p.h)||2)*scale);
      c.fillStyle=String(p.color||'#808080');
      if(String(p.shape)==='ellipse'){
        c.beginPath();c.ellipse(Math.round(x),Math.round(y),Math.max(1,w/2),Math.max(1,h/2),0,0,Math.PI*2);c.fill();
      }else{
        c.fillRect(Math.round(x-w/2),Math.round(y-h/2),Math.round(w),Math.round(h));
      }
    });
    c.restore();label(e.name,e.x,e.y);bubble(e);return true;
  }
  function draw(e){if(hidden.has(e.id))return;if(drawTemplate(e))return;if(e.entityType==='vehicle')drawVehicle(e);else if(e.entityType==='animal')drawAnimal(e);else if(e.entityType==='item'||e.entityType==='decoration')drawItem(e);else drawHuman(e);}
'''
    if marker in html:
        html = html.replace(marker, replacement, 1)

    create_marker = "if(!e){e={id,name:String(raw.name||id),entityType:String(raw.entityType||'human'),zone:String(raw.zone||''),x:Number(raw.x)||320,y:Number(raw.y)||292,bodyColor:raw.bodyColor,accentColor:raw.accentColor,carrying:Array.isArray(raw.carrying)?raw.carrying.slice():[],queue:[],current:null,done:new Set(),speech:''};entities.set(id,e);}"
    create_replacement = "if(!e){e={id,name:String(raw.name||id),entityType:String(raw.entityType||'human'),zone:String(raw.zone||''),x:Number(raw.x)||320,y:Number(raw.y)||292,bodyColor:raw.bodyColor,accentColor:raw.accentColor,carrying:Array.isArray(raw.carrying)?raw.carrying.slice():[],templateId:String(raw.templateId||''),visual:raw.visual||null,capabilities:Array.isArray(raw.capabilities)?raw.capabilities.slice():[],mobility:String(raw.mobility||''),facing:'down',queue:[],current:null,done:new Set(),speech:''};entities.set(id,e);}"
    if create_marker in html:
        html = html.replace(create_marker, create_replacement, 1)

    merge_marker = "e.name=String(raw.name||e.name);e.entityType=String(raw.entityType||e.entityType);e.bodyColor=raw.bodyColor||e.bodyColor;e.accentColor=raw.accentColor||e.accentColor;"
    merge_replacement = "e.name=String(raw.name||e.name);e.entityType=String(raw.entityType||e.entityType);e.bodyColor=raw.bodyColor||e.bodyColor;e.accentColor=raw.accentColor||e.accentColor;e.templateId=String(raw.templateId||e.templateId||'');e.visual=raw.visual||e.visual||null;e.capabilities=Array.isArray(raw.capabilities)?raw.capabilities.slice():e.capabilities;e.mobility=String(raw.mobility||e.mobility||'');"
    if merge_marker in html:
        html = html.replace(merge_marker, merge_replacement, 1)

    move_marker = "const dx=p.x-e.x,dy=p.y-e.y,d=Math.hypot(dx,dy);if(d<2){e.x=p.x;e.y=p.y;return true;}\n    const step=Math.min(d,Math.max(10,speed)*dt);e.x+=dx/d*step;e.y+=dy/d*step;return false;"
    move_replacement = "const dx=p.x-e.x,dy=p.y-e.y,d=Math.hypot(dx,dy);if(d<2){e.x=p.x;e.y=p.y;return true;}\n    if(Math.abs(dx)>Math.abs(dy))e.facing=dx<0?'left':'right';else e.facing=dy<0?'up':'down';\n    const step=Math.min(d,Math.max(10,speed)*dt);e.x+=dx/d*step;e.y+=dy/d*step;return false;"
    if move_marker in html:
        html = html.replace(move_marker, move_replacement, 1)

    start_marker = "    }else if(kind==='wait')e.current.duration=Math.max(.5,Math.min(120,Number(step.seconds)||1));\n    else if(kind==='give')e.current.duration=.9;"
    start_replacement = "    }else if(kind==='wait')e.current.duration=Math.max(.5,Math.min(120,Number(step.seconds)||1));\n    else if(kind==='give')e.current.duration=.9;\n    else if(kind==='interact_entity'){\n      e.current.duration=Math.max(.2,Math.min(30,Number(step.duration)||1.2));e.interaction=String(step.verb||'interact');\n      if(step.text||step.text_zh){const zh=document.getElementById('dialogueLangSelect')?.value!=='es';e.speech=String(zh&&step.text_zh?step.text_zh:(step.text||''));}\n      eventLog('⚙ '+e.name+' '+e.interaction+(step.target?' → '+step.target:''));"
    if start_marker in html:
        html = html.replace(start_marker, start_replacement, 1)

    tick_marker = "    }else if(s.type==='say'||s.type==='wait'||s.type==='give'){\n      if(s.elapsed>=Number(s.duration||1))finishStep(e);"
    tick_replacement = "    }else if(s.type==='say'||s.type==='wait'||s.type==='give'||s.type==='interact_entity'){\n      if(s.elapsed>=Number(s.duration||1))finishStep(e);"
    if tick_marker in html:
        html = html.replace(tick_marker, tick_replacement, 1)

    finish_marker = "    if(step.type==='say')e.speech='';"
    finish_replacement = "    if(step.type==='say')e.speech='';\n    if(step.type==='interact_entity'){e.interaction='';e.speech='';}"
    if finish_marker in html:
        html = html.replace(finish_marker, finish_replacement, 1)

    tag = "\n<script id=\"town-template-composer-runtime\">window.TOWN_TEMPLATE_COMPOSER=true;</script>\n"
    return html.replace('</body>', tag + '</body>', 1) if '</body>' in html else html + tag

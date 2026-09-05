"""Offline regressions: no TiDB writes, live AI calls, or production requests."""
import ast
import importlib
import json
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]


def build_html():
    tree = ast.parse((ROOT / 'town_app.py').read_text())
    namespace = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and any(
            a.name.startswith('patch_render_') or a.name == 'latest_town_html' for a in node.names
        ):
            module = importlib.import_module(node.module)
            for alias in node.names:
                namespace[alias.name] = getattr(module, alias.name)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_build_cached_town_html')
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'offline-compose', 'exec'), namespace)
    with patch('blueprints.town_render_native_colleagues_patch._bootstrap_rows', return_value=[]):
        return namespace['_build_cached_town_html']()


def node(script, data):
    result = subprocess.run(['node', '-e', script], input=json.dumps(data), text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout


def function(html, name):
    match = re.search(r'  function '+name+r'\([^\n]*\)\{.*?\n  \}', html, re.S)
    if not match:
        raise AssertionError('function missing: '+name)
    return match.group()


class BrowserBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = build_html()

    def test_all_scripts_parse(self):
        scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', self.html, re.S)
        scripts.append((ROOT/'static/town_language.js').read_text())
        node("const vm=require('vm');const fs=require('fs');JSON.parse(fs.readFileSync(0,'utf8')).forEach((s,i)=>new vm.Script(s,{filename:'script-'+i}));", scripts)

    def test_one_scroll_owner(self):
        self.assertIn('/static/town_language.js?v=20260905', self.html)
        self.assertNotIn('town-dialogue-scroll-lock-runtime', self.html)
        self.assertIn('if(viewport?.dragging)return', self.html)
        self.assertIn('if(box.innerHTML!==nextMarkup)', self.html)
        self.assertIn('scrollbar{width:16px}', self.html)
        self.assertIn('overflow-y:scroll!important', self.html)
        self.assertNotIn('list.scrollTop=list.scrollHeight', self.html)
        self.assertNotIn('requestAnimationFrame(()=>{\n      if(followLatest)', self.html)

    def test_bilingual_history_and_scene_wiring(self):
        self.assertNotIn("document.getElementById('dialogueLangSelect')", self.html)
        self.assertIn('speaker.__townSpeechTurn={...turn}', self.html)
        self.assertIn('const liveDialogue=', self.html)
        self.assertNotIn('window.__townDialogueHistory.push({at:Date.now(),members:[from.name,to.name]', self.html)
        self.assertNotIn('c.clearRect(0,0,640,400);entities', self.html)
        self.assertEqual(self.html.count('window.__townSceneLayers.push('), 2)
        self.assertIn('Math.sin(performance.now()/1000', self.html)
        self.assertIn("registerDirectorTool('agent_say'", self.html)
        self.assertIn("a.__townSpeechTurn=turn", self.html)

    def test_language_switch_never_mutates_source(self):
        node(r"""
          const vm=require('vm'),assert=require('assert'),fs=require('fs');
          const context={window:{__townUiPrefs:{dialogueLang:'zh'}},setTimeout:()=>1,Date};
          vm.createContext(context);vm.runInContext(JSON.parse(fs.readFileSync(0,'utf8')),context);
          const api=context.window.TownLanguage;
          const turn={text:'¡Qué mala suerte!',text_zh:'造孽啊！'};
          assert.equal(api.text(turn),'造孽啊！');
          context.window.__townUiPrefs.dialogueLang='es';
          assert.equal(api.text(turn),'¡Qué mala suerte!');
          assert.equal(turn.text,'¡Qué mala suerte!');
          assert.equal(api.text({text:'造孽啊！'},'zh'),'造孽啊！');
          assert.equal(api.text({text:'造孽啊！'}),'[Traducción pendiente]');
          assert.equal(api.text({text:'Hola'},'zh'),'［翻譯待補］');
        """, (ROOT/'static/town_language.js').read_text())

    def test_path_never_falls_back_through_desk(self):
        script='\n'.join(function(self.html,n) for n in ['pointBlocked','makePath','townSegmentClear','townSafeGoal','moveToward'])
        node(r"""
          const vm=require('vm'),assert=require('assert'),fs=require('fs');
          const context={deskBlocks:[{x1:220,y1:148,x2:320,y2:218}],aiFurniture:[],Math};
          vm.createContext(context);vm.runInContext(JSON.parse(fs.readFileSync(0,'utf8')),context);
          assert.equal(context.makePath(200,240,270,180).length,0);
          const actor={x:180,y:240,path:[],walkPhase:0};
          for(let i=0;i<200;i++){
            context.moveToward(actor,360,140,3);
            assert(!context.pointBlocked(actor.x,actor.y),'walked into blocked floor');
          }
          assert(Math.hypot(actor.x-360,actor.y-140)<2,'did not reach reachable destination');
          context.deskBlocks=[{x1:35,y1:180,x2:600,y2:190}];
          assert.equal(context.makePath(100,240,100,120).length,0,'unreachable path must stay empty');
        """, script)

    def test_no_scroll_write_during_drag(self):
        node(r"""
          const vm=require('vm'),assert=require('assert'),fs=require('fs');
          const source=JSON.parse(fs.readFileSync(0,'utf8'));
          let writes=0,top=50,markup='';
          const box={get scrollTop(){return top},set scrollTop(v){writes++;top=v},scrollHeight:500,clientHeight:100,
            get innerHTML(){return markup},set innerHTML(v){markup=v}};
          const state={dragging:true,followLatest:false,mutating:false};
          const context={window:{__townDialogueHistory:[{members:['A'],turns:[{speaker:'A',text:'Hola'}]}]},
            ensureTownSidePanel:()=>({querySelector:()=>box}),townEnsureDialogueViewport:()=>state,
            syncTownDialoguePanelHeight:()=>{},escapeHtml:String,dialogueText:t=>t.text,Date,Math};
          vm.createContext(context);vm.runInContext(source,context);
          context.renderDialogueSidebar();assert.equal(writes,0);
          state.dragging=false;context.renderDialogueSidebar();assert.equal(top,50);assert.equal(state.mutating,false);
          context.window.__townDialogueHistory=[];context.renderDialogueSidebar();assert.equal(state.mutating,false);
        """, function(self.html,'renderDialogueSidebar'))


class BackendTests(unittest.TestCase):
    def test_translation_endpoint_limits_and_cache(self):
        from flask import Flask
        from blueprints import town_dialogue_translation as module
        app=Flask(__name__);module.install_dialogue_translation(app)
        client=app.test_client()
        self.assertEqual(client.post('/api/town/translate-dialogue',json={'turns':[]}).status_code,400)
        self.assertEqual(client.post('/api/town/translate-dialogue',json={'turns':[{'text':'x'*401}]}).status_code,400)
        module._CACHE.clear();module._NEXT_CALL=0
        response=Mock();response.json.return_value={'choices':[{'message':{'content':json.dumps({'turns':[{'text':'¡Qué mala suerte!','text_zh':'造孽啊！'}]})}}]}
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'offline-test'}),patch.object(module.requests,'post',return_value=response) as call:
            body={'turns':[{'text':'造孽啊！'}]}
            a=client.post('/api/town/translate-dialogue',json=body)
            b=client.post('/api/town/translate-dialogue',json=body)
            self.assertEqual(a.status_code,200);self.assertEqual(b.status_code,200)
            self.assertEqual(call.call_count,1)

    def test_motion_is_validated_not_executable(self):
        from blueprints.town_entity_template_runtime import _clean_motion, _clean_parts
        motion=_clean_motion({'on':'eval(code)','dx':999,'dy':float('nan'),'period':0})
        self.assertEqual(motion,{'on':'move','dx':20,'dy':0,'period':0.2,'phase':0})
        parts=_clean_parts([{'shape':'rect','color':'javascript:alert(1)','motion':{'on':'interact','dy':4}}])
        self.assertEqual(parts[0]['color'],'#808080')
        self.assertEqual(parts[0]['motion']['dy'],4)


if __name__ == '__main__':
    unittest.main()

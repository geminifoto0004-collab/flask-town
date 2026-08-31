"""Improve generic animal rendering for dinosaur-like entities.

This is a presentation-only patch layered after the generic entity runtime. It
keeps the server/world model generic while giving Dino/dinosaur/T-Rex entities a
recognizable larger pixel-art silhouette instead of the tiny default animal.
"""


def patch_render_dinosaurs(html: str) -> str:
    old = "function drawAnimal(e){const x=e.x,y=e.y,body=e.bodyColor||'#788890';px(x-11,y-5,22,10,body);px(x+7,y-10,9,9,body);px(x+12,y-7,2,2,'#182126');px(x-13,y-2,5,4,e.accentColor||'#58666d');label(e.name,x,y);}"
    new = r"""function drawDinosaur(e){
    const x=e.x,y=e.y,body=e.bodyColor||'#4fa83f',accent=e.accentColor||'#2f7d32';
    // shadow + powerful hind legs
    px(x-23,y+15,48,4,'rgba(0,0,0,.22)');
    px(x-9,y+3,9,15,body);px(x+7,y+3,9,15,body);px(x-12,y+15,13,4,accent);px(x+5,y+15,14,4,accent);
    // big torso and neck
    px(x-20,y-13,34,19,body);px(x+8,y-22,10,20,body);
    // large head / snout
    px(x+12,y-30,23,15,body);px(x+26,y-24,14,8,body);px(x+35,y-22,5,3,'#e8e0b6');
    px(x+27,y-26,3,3,'#142018');
    // jaw / teeth
    px(x+22,y-15,16,4,accent);px(x+27,y-14,3,4,'#f5f1dc');px(x+33,y-14,3,4,'#f5f1dc');
    // tiny arms
    px(x+11,y-6,10,4,body);px(x+18,y-4,4,7,body);px(x+18,y+1,7,3,accent);
    // long stepped tail
    px(x-34,y-10,16,11,body);px(x-46,y-7,14,8,body);px(x-56,y-4,12,5,accent);px(x-63,y-2,9,3,accent);
    // back spikes
    px(x-17,y-17,5,5,accent);px(x-8,y-20,5,7,accent);px(x+1,y-22,5,8,accent);px(x+9,y-25,5,7,accent);
    label(e.name,x,y-4);bubble(e);
  }
  function drawAnimal(e){
    const name=String(e.name||'');
    if(/dino|dinosaur|t[\s-]?rex|恐龍|恐龙/i.test(name)){drawDinosaur(e);return;}
    const x=e.x,y=e.y,body=e.bodyColor||'#788890';
    px(x-13,y+7,27,3,'rgba(0,0,0,.18)');px(x-12,y-5,24,11,body);px(x+7,y-11,10,10,body);
    px(x+12,y-8,2,2,'#182126');px(x-15,y-2,6,4,e.accentColor||'#58666d');
    px(x-8,y+4,4,8,body);px(x+6,y+4,4,8,body);label(e.name,x,y);bubble(e);
  }"""
    if old in html:
        return html.replace(old, new, 1)
    return html

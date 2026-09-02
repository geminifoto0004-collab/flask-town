"""Render TiDB colleagues beyond the three legacy native sprite slots.

The mature browser game owns three historical officer sprites. TiDB may contain
more permanent colleagues, so feed agents after the first three into the already
existing generic entity overlay as synthetic persistent humans. This keeps the
legacy renderer untouched while making additional employees visible and valid
movement targets.
"""


def patch_render_extra_colleagues(html: str) -> str:
    if 'town-extra-colleagues-runtime' in html:
        return html

    marker = "    const incoming=Array.isArray(world&&world.genericEntities)?world.genericEntities:[];\n"
    replacement = r'''    const incomingBase=Array.isArray(world&&world.genericEntities)?world.genericEntities:[];
    const extraColleagues=agents.slice(3).map((a,index)=>{
      const id=String(a&&a.name||a&&a.slot||'').toUpperCase();
      const col=index%4,row=Math.floor(index/4);
      const x=Number.isFinite(Number(a&&a.x))?Number(a.x):(125+col*120);
      const y=Number.isFinite(Number(a&&a.y))?Number(a.y):(210+row*44);
      return {
        id,
        name:String(a&&a.displayName||id),
        entityType:'human',
        zone:'office',
        x,y,
        bodyColor:String(a&&a.bodyColor||'#536f86'),
        accentColor:String(a&&a.accentColor||'#d4a74a'),
        carrying:[],
        script:[]
      };
    }).filter(v=>v.id);
    const genericIds=new Set(incomingBase.map(v=>String(v&&v.id||'').toUpperCase()));
    const incoming=incomingBase.concat(extraColleagues.filter(v=>!genericIds.has(String(v.id).toUpperCase())));
'''
    if marker in html:
        html = html.replace(marker, replacement, 1)

    tag = '\n<script id="town-extra-colleagues-runtime">window.TOWN_EXTRA_COLLEAGUES=true;</script>\n'
    return html.replace('</body>', tag + '</body>', 1) if '</body>' in html else html + tag

"""Browser startup/performance patch for CUSTOMS AGENT TOWN.

The page has several independent overlays that consume the same shared world.
Keep first paint independent from TiDB, deduplicate simultaneous world GETs in
the browser, and lower background polling frequency without changing immediate
local animation or interaction behavior.
"""


def patch_render_performance(html: str) -> str:
    if 'town-world-fetch-cache-runtime' not in html:
        js = r'''
<script id="town-world-fetch-cache-runtime">
(()=>{
  const nativeFetch=window.fetch.bind(window);
  let cached=null,cachedAt=0,inflight=null;
  const ttl=1500;
  function isWorldGet(input,init){
    const method=String((init&&init.method)||'GET').toUpperCase();
    if(method!=='GET')return false;
    let url='';
    try{url=typeof input==='string'?input:(input&&input.url)||'';}catch(_e){}
    try{const u=new URL(url,location.href);return u.origin===location.origin&&u.pathname==='/api/town/world';}catch(_e){return false;}
  }
  function responseFrom(rec){
    return new Response(rec.body,{status:rec.status,statusText:rec.statusText,headers:rec.headers});
  }
  window.fetch=(input,init)=>{
    if(!isWorldGet(input,init))return nativeFetch(input,init);
    const now=Date.now();
    if(cached&&now-cachedAt<ttl)return Promise.resolve(responseFrom(cached));
    if(!inflight){
      inflight=nativeFetch(input,init).then(async r=>{
        const rec={body:await r.clone().text(),status:r.status,statusText:r.statusText,headers:Array.from(r.headers.entries())};
        if(r.ok){cached=rec;cachedAt=Date.now();}
        return rec;
      }).finally(()=>{setTimeout(()=>{inflight=null;},0);});
    }
    return inflight.then(responseFrom);
  };
  window.__townInvalidateWorldFetch=()=>{cached=null;cachedAt=0;};
})();
</script>
'''
        html = html.replace('</head>', js + '</head>', 1) if '</head>' in html else js + html

    # Let the base canvas paint first. Non-critical shared-world overlays hydrate
    # just after first paint instead of all competing during page construction.
    html = html.replace(
        "refresh();setInterval(refresh,900);requestAnimationFrame(frame);",
        "setTimeout(refresh,900);setInterval(refresh,2500);requestAnimationFrame(frame);",
    )
    html = html.replace(
        "refresh();setInterval(refresh,900);",
        "setTimeout(refresh,1100);setInterval(refresh,2500);",
    )
    html = html.replace(
        "adminStatus();refreshWorld();setInterval(refreshWorld,3000);",
        "setTimeout(adminStatus,900);setTimeout(refreshWorld,1200);setInterval(refreshWorld,5000);",
    )
    html = html.replace(
        "  moveLanguageControls();\n  refreshSharedHistory();\n  // Other viewers follow the shared conversation within about one second.\n  setInterval(refreshSharedHistory,1000);",
        "  moveLanguageControls();\n  setTimeout(refreshSharedHistory,1200);\n  // Current-viewer chat is immediate; shared TiDB history can follow more slowly.\n  setInterval(refreshSharedHistory,4000);",
    )

    # On explicit world-changing operations, clear the tiny GET cache so the
    # next refresh sees the new authoritative state immediately.
    html = html.replace(
        "      await refreshWorld();",
        "      if(typeof window.__townInvalidateWorldFetch==='function')window.__townInvalidateWorldFetch();\n      await refreshWorld();",
    )
    return html

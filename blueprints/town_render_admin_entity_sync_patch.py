"""Immediately sync admin-returned shared world into the generic entity overlay.

The generic overlay normally hydrates from /api/town/world polling. Admin
commands already return the authoritative evolved world in their JSON payload,
so expose the overlay's existing mergeWorld function and feed that response into
it immediately. This avoids a visible race with polling/cache and does not add a
second renderer.
"""


def patch_render_admin_entity_sync(html: str) -> str:
    if 'town-admin-entity-sync-runtime' in html:
        return html

    # Expose the existing mature generic overlay merger from inside its IIFE.
    refresh_marker = "  async function refresh(){\n    if(refreshing)return;refreshing=true;"
    if refresh_marker in html and "window.__townMergeGenericWorld=mergeWorld" not in html:
        html = html.replace(
            refresh_marker,
            "  window.__townMergeGenericWorld=mergeWorld;\n  window.__townGenericEntityCount=()=>entities.size;\n" + refresh_marker,
            1,
        )

    # The admin response already contains evolved_world. Merge it before waiting
    # for any background /world poll, then invalidate the tiny GET cache.
    action_marker = "      const actions=Array.isArray(data.actions)?data.actions:[];\n"
    if action_marker in html:
        html = html.replace(
            action_marker,
            action_marker
            + "      try{\n"
            + "        if(data&&data.world&&typeof window.__townMergeGenericWorld==='function'){\n"
            + "          window.__townMergeGenericWorld(data.world);\n"
            + "          if(typeof window.__townInvalidateWorldFetch==='function')window.__townInvalidateWorldFetch();\n"
            + "        }\n"
            + "      }catch(err){log('共同世界即時同步失敗：'+String(err&&err.message||err));}\n",
            1,
        )

    tag = '\n<script id="town-admin-entity-sync-runtime">window.TOWN_ADMIN_ENTITY_SYNC=true;</script>\n'
    return html.replace('</body>', tag + '</body>', 1) if '</body>' in html else html + tag

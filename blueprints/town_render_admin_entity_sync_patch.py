"""Immediately sync admin world and finalize browser dialogue synchronization.

The generic overlay normally hydrates from /api/town/world polling. Admin
commands already return the authoritative evolved world in their JSON payload,
so expose the overlay's existing mergeWorld function and feed that response into
it immediately. The final dialogue patch is applied here because this function
runs after the dialogue panel/shared-history patches in the browser build.
"""

from .town_render_dialogue_sync_patch import patch_render_dialogue_sync


def patch_render_admin_entity_sync(html: str) -> str:
    if 'town-admin-entity-sync-runtime' not in html:
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
        html = html.replace('</body>', tag + '</body>', 1) if '</body>' in html else html + tag

    # This must run after town_render_dialogue_panel_patch and
    # town_render_shared_dialogue_patch have injected their known markup/runtime.
    return patch_render_dialogue_sync(html)

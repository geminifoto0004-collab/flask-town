"""Standalone Render entry point for CUSTOMS AGENT TOWN.

Start command for the dedicated Render service:
    gunicorn town_app:app

This process intentionally loads only the AI-town stack. It does not mount the
main authorization app, ORDER, crawler jobs, B2 helpers, container services or
other production blueprints.
"""

import os

# blueprints/__init__.py checks this before importing any unrelated main-service
# modules. It must be set before the first blueprints.* import below.
os.environ["TOWN_STANDALONE_SERVICE"] = "1"

from flask import Flask, jsonify, redirect

from blueprints import town_ai_bp as _town_ai_module
from blueprints.town_ai_action_runtime import install_latest_action_runtime
from blueprints.town_ai_visibility_runtime import install_visibility_runtime
from blueprints.town_ai_history_runtime import install_history_runtime
from blueprints.town_ai_profile_runtime import install_profile_runtime
from blueprints.town_ai_bilingual_runtime import install_bilingual_runtime
from blueprints.town_world_map_runtime import install_world_map_runtime
from blueprints.town_ai_sea_runtime import install_sea_runtime
from blueprints.town_ai_shift_runtime import install_shift_runtime
from blueprints.town_world_object_runtime import install_world_object_runtime
from blueprints.town_generic_entity_runtime import install_generic_entity_runtime
from blueprints.town_entity_template_runtime import install_entity_template_runtime, template_catalog
from blueprints.town_entity_interaction_runtime import install_entity_interaction_runtime
from blueprints.town_action_capacity_patch import install_action_capacity_patch
from blueprints.town_relationship_runtime import install_relationship_runtime
from blueprints.town_officer_scene_runtime import install_officer_scene_runtime
from blueprints.town_generic_scene_runtime import install_generic_scene_runtime
from blueprints.town_entity_type_compat_patch import install_entity_type_compat_patch
from blueprints.town_world_scene_runtime import install_world_scene_runtime
from blueprints.town_world_tidb_runtime import install_tidb_world_runtime
from blueprints.town_dialogue_tidb_runtime import install_tidb_dialogue_runtime
from blueprints.town_ai_auto_chat_runtime import install_auto_chat_runtime
from blueprints.town_cron_tick_runtime import install_cron_tick_runtime
from blueprints.town_state_merge_runtime import install_state_merge_guard
from blueprints.town_character_tidb_runtime import (
    character_ids,
    install_character_runtime,
    run_sql_migration_file,
)
from blueprints.town_character_validation_patch import install_character_validation_patch

# Import side effect: allow longer composed tool-call sequences before admin and
# language runtimes bind the action parser.
from blueprints import town_ai_toolcall_limit_patch as _town_ai_toolcall_limit_patch  # noqa: F401

from blueprints.town_admin_runtime import install_town_admin_runtime
from blueprints.town_admin_freedom_patch import install_admin_freedom_patch
from blueprints.town_admin_scene_runtime import install_admin_scene_runtime
from blueprints.town_officer_scene_admin_patch import install_officer_scene_admin_patch
from blueprints.town_ai_grounded_director import grounded_model_decision
from blueprints.town_character_director_patch import install_character_director_patch
from blueprints.town_admin_reliability_patch import install_admin_reliability_patch
from blueprints.town_entity_template_director_patch import install_entity_template_director_patch
from blueprints.town_character_admin_runtime import install_character_admin_runtime

from blueprints import town_page_bp as _town_page_module
from blueprints.town_latest_page_runtime import latest_town_html
from blueprints.town_render_visibility_patch import patch_render_visibility
from blueprints.town_render_action_patch import patch_render_actions
from blueprints.town_render_depth_patch import patch_render_depth
from blueprints.town_render_fishing_patch import patch_render_fishing
from blueprints.town_render_chat_timing_patch import patch_render_chat_timing
from blueprints.town_render_profile_patch import patch_render_profiles
from blueprints.town_render_dialogue_panel_patch import patch_render_dialogue_panel
from blueprints.town_render_dialogue_fix_patch import patch_render_dialogue_fix
from blueprints.town_render_panel_alignment_patch import patch_render_panel_alignment
from blueprints.town_render_shared_dialogue_patch import patch_render_shared_dialogue
from blueprints.town_render_admin_world_patch import patch_render_admin_world
from blueprints.town_render_world_object_patch import patch_render_world_objects
from blueprints.town_render_generic_entity_patch import patch_render_generic_entities
from blueprints.town_render_template_composer_patch import patch_render_template_composer
from blueprints.town_render_dinosaur_patch import patch_render_dinosaurs
from blueprints.town_render_admin_action_feedback_patch import patch_render_admin_action_feedback
from blueprints.town_render_local_life_patch import patch_render_local_life
from blueprints.town_render_character_binding_patch import patch_render_character_bindings


app = Flask(__name__)
app.secret_key = (
    os.environ.get("TOWN_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
    or "customs-town-local-development-only"
)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_NAME")),
)


# Keep the currently stable town runtime chain isolated from the main service.
install_latest_action_runtime()
install_visibility_runtime()
install_history_runtime()
install_profile_runtime()
install_bilingual_runtime()
install_world_map_runtime()
install_sea_runtime()
install_shift_runtime()
install_world_object_runtime()
install_generic_entity_runtime()

# Generic creation layer: AI can define reusable visual/behavior data in TiDB,
# spawn instances from it, then use semantic interactions on those instances.
install_entity_template_runtime()
install_entity_interaction_runtime()

install_relationship_runtime()
install_officer_scene_runtime()
# Put the capacity adapter after the older validators so their small per-call
# caps cannot silently erase later actors in a larger admin scene.
install_action_capacity_patch()
install_generic_scene_runtime()
# Semantic kinds are normalized before they reach the mature five-class
# renderer. The world-scene compiler is installed after this layer so its
# expanded spawn actions are normalized by the compatibility validator.
install_entity_type_compat_patch()
install_world_scene_runtime()
install_tidb_world_runtime()
install_tidb_dialogue_runtime()

# Character identity/personality is owned by TiDB. The SQL file seeds a brand-
# new installation; subsequent character data is edited in TiDB/admin API.
if not character_ids(force=True):
    run_sql_migration_file(
        os.path.join(os.path.dirname(__file__), "migrations", "20260831_town_characters.sql")
    )
install_character_runtime()

install_admin_scene_runtime()
install_officer_scene_admin_patch()
install_admin_freedom_patch()
# Final dialogue validation reads the current TiDB officer IDs instead of any
# legacy source-code name list.
install_character_validation_patch()
install_character_director_patch()
install_admin_reliability_patch()
install_auto_chat_runtime()
install_cron_tick_runtime()
install_entity_template_director_patch()
install_town_admin_runtime()
install_character_admin_runtime()

# /api/town/think uses the grounded director after all validation/persistence
# wrappers are installed.
_town_ai_module._model_decision = grounded_model_decision
town_ai_bp = _town_ai_module.town_ai_bp


def _build_cached_town_html():
    """Compose the browser build once per Render worker, not once per request.

    Keep the original mature pixel-character renderer/movement loop. Character
    identity is rebound to the current TiDB core characters once during worker
    startup, so there is no second overlay renderer and no delayed visual swap.
    """
    html = latest_town_html()
    html = patch_render_visibility(html)
    html = patch_render_actions(html)
    html = patch_render_depth(html)
    html = patch_render_fishing(html)
    html = patch_render_chat_timing(html)
    html = patch_render_profiles(html)
    html = patch_render_dialogue_panel(html)
    html = patch_render_dialogue_fix(html)
    html = patch_render_panel_alignment(html)
    html = patch_render_shared_dialogue(html)
    html = patch_render_admin_world(html)
    html = patch_render_world_objects(html)
    html = patch_render_generic_entities(html)
    html = patch_render_template_composer(html)
    html = patch_render_dinosaurs(html)
    html = patch_render_admin_action_feedback(html)
    html = patch_render_local_life(html)
    html = patch_render_character_bindings(html)
    return html


# Heavy gzip reconstruction and string patching happen once when this gunicorn
# worker starts. Every /customs-town request afterwards returns the same cached
# string immediately.
_TOWN_HTML_CACHE = _build_cached_town_html()
town_page_bp = _town_page_module.town_page_bp
_town_page_module._patched_town_html = lambda: _TOWN_HTML_CACHE

app.register_blueprint(town_ai_bp)
app.register_blueprint(town_page_bp)
# The native page periodically POSTs a partial/legacy world snapshot. Protect
# TiDB-owned AI entities/objects/dialogue from being erased by that stale state.
_STATE_MERGE_GUARD = install_state_merge_guard(app)


@app.get("/")
def town_root():
    return redirect("/customs-town")


@app.get("/ping")
def town_ping():
    return "OK", 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}


@app.get("/health")
def town_health():
    return jsonify(
        {
            "ok": True,
            "service": "customs-agent-town",
            "town_page": "/customs-town",
            "deepseek_configured": bool((os.environ.get("DEEPSEEK_API_KEY") or "").strip()),
            "admin_configured": bool((os.environ.get("TOWN_ADMIN_PASSWORD") or "").strip()),
            "core_characters": character_ids(),
            "entity_template_count": len(template_catalog()),
            "town_html_cached": True,
            "local_life_tick": True,
            "auto_chat_runtime": True,
            "cron_tick_runtime": True,
            "admin_reliability_guard": True,
            "semantic_entity_compat": True,
            "world_scene_runtime": True,
            "state_merge_guard": bool(_STATE_MERGE_GUARD),
            "native_character_renderer": True,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)

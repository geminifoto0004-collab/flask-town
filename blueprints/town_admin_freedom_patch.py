"""Remove small story-tool selection limits from admin directing.

Admin instructions should be represented visibly whenever the generic world
engine can represent them.  This patch keeps every registered tool available
instead of narrowing the model to a keyword-selected subset.
"""

from . import town_admin_runtime as _admin
from .town_ai_director_runtime import DIRECTOR_TOOLS


def install_admin_freedom_patch():
    def select_admin_tools(_prompt):
        # The registered tool schemas remain the safety boundary.  Do not hide
        # entity_scene or other generic verbs based on keyword guessing.
        return list(DIRECTOR_TOOLS)

    _admin._select_admin_tools = select_admin_tools

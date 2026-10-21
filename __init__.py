"""recursive-mode Hermes plugin.

Registers every ``skills/<name>/SKILL.md`` as a namespaced, read-only
plugin skill: ``skill_view("recursive-mode:<name>")``.
"""

from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent


def register(ctx):
    """Wire the skills/ tree into the Hermes skill registry."""
    for child in sorted((_PLUGIN_DIR / "skills").iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(child.name, skill_md)

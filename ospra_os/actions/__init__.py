"""
Actions module for converting AI insights into actionable items.

T122: action_factory.py and auto_pilot.py are dead. Nothing outside this package
ever imported ActionFactory, and this package's auto_pilot.py was imported only by
action_factory.py (the LIVE autopilot is intelligence/auto_pilot.py — a different
module that happens to define a class of the same name). The one live file here is
undo_manager.py, which callers import by direct module path
(api/actions_routes.py), so dropping this re-export does not affect it.
"""

__all__ = []

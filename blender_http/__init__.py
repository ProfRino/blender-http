"""Blender HTTP — live HTTP bridge for Blender script execution."""

from . import ui


def register():
    ui.register()


def unregister():
    ui.unregister()

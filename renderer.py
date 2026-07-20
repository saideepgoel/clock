"""Backward-compatible import shim for existing scripts."""

from devotional_image_studio.renderer import CardRenderer, RenderRequest, RenderResult

__all__ = ["CardRenderer", "RenderRequest", "RenderResult"]

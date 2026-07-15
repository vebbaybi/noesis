"""Process composition, background workers, and server lifecycle."""

from .container import ServiceContainer, get_container

__all__ = ["ServiceContainer", "get_container"]
"""The sole composition root for dependency wiring, lifecycle, and process startup."""

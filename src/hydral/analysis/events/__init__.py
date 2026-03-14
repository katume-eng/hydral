"""Event detection modules for hydral."""

from hydral.analysis.events.splash import (
    SplashEvent,
    detect_splash_events,
    events_to_dicts,
    to_dict,
)

__all__ = [
    "SplashEvent",
    "detect_splash_events",
    "events_to_dicts",
    "to_dict",
]

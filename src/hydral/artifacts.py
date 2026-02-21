"""Structured output artifacts for hydral pipeline steps.

Steps fill fields on an :class:`Artifacts` instance (stored at
``ctx.artifacts``) instead of relying on fragile string-keyed ``ctx.extra``
lookups for core outputs.  ``ctx.extra`` is still available for ad-hoc
debugging payloads.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Artifacts:
    """Holds typed output paths produced by built-in pipeline steps.

    Fields are ``None`` until the corresponding step runs successfully.
    """

    features_json: Optional[Path] = None
    normalized_wav: Optional[Path] = None
    grain_wav: Optional[Path] = None
    band_manifest_json: Optional[Path] = None
    band_dir: Optional[Path] = None

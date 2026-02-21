"""Metadata unification for hydral WAV files.

Defines a single canonical metadata schema (v1) and provides utilities to
migrate legacy/mixed-format sidecar JSONs into that schema.

Schema v1
---------
::

    {
        "schema_version": "v1",
        "filename": "example.wav",
        "duration_sec": 12.0,
        "sample_rate": 44100,
        "channels": 1,
        "tags": [],
        "normalized": false,
        "mean_rms": null
    }

CLI usage::

    python -m hydral.processing.unify_metadata --root data/raw

"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import soundfile as sf

SCHEMA_VERSION = "v1"

# Keys that identify a fully-formed v1 document.
_V1_REQUIRED = {"schema_version", "filename", "duration_sec", "sample_rate", "channels", "tags"}

# Mapping from known legacy field names → v1 field names.
_LEGACY_FIELD_MAP: Dict[str, str] = {
    # duration aliases
    "duration": "duration_sec",
    "length_sec": "duration_sec",
    # rms aliases
    "rms": "mean_rms",
    "rms_db": "mean_rms",
    "rms_mean": "mean_rms",
}


# ── Schema helpers ─────────────────────────────────────────────────────────


def is_v1(data: Dict[str, Any]) -> bool:
    """Return *True* if *data* already conforms to schema v1."""
    return (
        isinstance(data, dict)
        and data.get("schema_version") == SCHEMA_VERSION
        and _V1_REQUIRED.issubset(data)
    )


def _read_wav_info(wav_path: Path) -> Dict[str, Any]:
    """Return basic audio info from *wav_path* using soundfile."""
    info = sf.info(str(wav_path))
    return {
        "duration_sec": info.duration,
        "sample_rate": info.samplerate,
        "channels": info.channels,
    }


def to_v1(wav_path: Path, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a v1 metadata dict for *wav_path*.

    If *existing* is provided, its fields are migrated into the v1 document
    (legacy field names are translated via ``_LEGACY_FIELD_MAP``).  Fields
    already present in *existing* take precedence over defaults derived from
    the WAV file, except for ``schema_version`` and ``filename`` which are
    always set from the canonical values.

    Parameters
    ----------
    wav_path:
        Path to the WAV file.
    existing:
        Optional existing metadata dict (may be empty or in a legacy format).

    Returns
    -------
    dict
        A fully-formed v1 metadata document.
    """
    wav_info = _read_wav_info(wav_path)

    # Start from the v1 skeleton
    doc: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "filename": wav_path.name,
        "duration_sec": wav_info["duration_sec"],
        "sample_rate": wav_info["sample_rate"],
        "channels": wav_info["channels"],
        "tags": [],
        "normalized": False,
        "mean_rms": None,
    }

    if existing:
        # Translate legacy field names first
        translated: Dict[str, Any] = {}
        for k, v in existing.items():
            canonical = _LEGACY_FIELD_MAP.get(k, k)
            translated[canonical] = v

        # Merge: existing values override defaults (except identity fields)
        for k, v in translated.items():
            if k in ("schema_version", "filename"):
                continue  # always use canonical values
            doc[k] = v

    return doc


# ── File-level helpers ─────────────────────────────────────────────────────


def _sidecar_path(wav_path: Path) -> Path:
    """Return the expected sidecar JSON path for *wav_path*."""
    return wav_path.with_suffix(".json")


def ensure_metadata(wav_path: Path) -> Tuple[Path, bool]:
    """Ensure a v1 sidecar JSON exists alongside *wav_path*.

    If the sidecar is absent or not v1, it is created/updated in-place.

    Parameters
    ----------
    wav_path:
        Path to the WAV file.

    Returns
    -------
    (json_path, changed)
        ``json_path`` is the sidecar path.
        ``changed`` is *True* if the file was created or overwritten.
    """
    json_path = _sidecar_path(wav_path)

    existing: Optional[Dict[str, Any]] = None
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            existing = None  # treat corrupt JSON as absent

    if existing is not None and is_v1(existing):
        return json_path, False

    doc = to_v1(wav_path, existing)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)

    return json_path, True


# ── Batch migration ────────────────────────────────────────────────────────


def migrate_root(root: Path) -> Dict[str, int]:
    """Walk *root* recursively and ensure every WAV has a v1 sidecar JSON.

    Parameters
    ----------
    root:
        Directory to scan.

    Returns
    -------
    dict
        ``{"created": N, "updated": N, "skipped": N}`` counts.
    """
    counts = {"created": 0, "updated": 0, "skipped": 0}
    for wav_path in sorted(root.rglob("*.wav")):
        sidecar = _sidecar_path(wav_path)
        existed_before = sidecar.exists()
        _, changed = ensure_metadata(wav_path)
        if changed:
            if existed_before:
                counts["updated"] += 1
                print(f"  updated  {wav_path}")
            else:
                counts["created"] += 1
                print(f"  created  {wav_path}")
        else:
            counts["skipped"] += 1
    return counts


# ── CLI ────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hydral.processing.unify_metadata",
        description="Migrate mixed metadata JSONs to schema v1 for all WAVs under --root.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        metavar="DIR",
        help="Root directory to scan for WAV files.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if not args.root.is_dir():
        import sys
        sys.exit(f"Root directory not found: {args.root}")

    print(f"🔍 Scanning {args.root} …")
    counts = migrate_root(args.root)
    print(
        f"\n✅ Done — created: {counts['created']}, "
        f"updated: {counts['updated']}, "
        f"skipped (already v1): {counts['skipped']}"
    )


if __name__ == "__main__":
    main()

"""YAML-driven pipeline runner for hydral.

Loads a ``pipeline.yaml`` config file and executes the declared steps over
each audio file found under the configured input root.

Usage::

    python -m hydral run
    python -m hydral run --config pipeline.yaml
"""
from __future__ import annotations

import json
import time
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Ensure built-in steps are registered in StepRegistry before any build_step call.
import hydral.steps.builtin  # noqa: F401 – side-effect: registers built-ins
from hydral.steps.registry import StepRegistry


# ── Config dataclasses ─────────────────────────────────────────────────────

@dataclass
class StepConfig:
    name: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    name: str = "hydral_default"
    input: str = "data/raw"
    output: str = "data/processed/hydral"
    glob: List[str] = field(
        default_factory=lambda: ["**/*.wav", "**/*.mp3", "**/*.flac", "**/*.m4a"]
    )
    steps: List[StepConfig] = field(default_factory=list)


# ── Trace dataclasses ──────────────────────────────────────────────────────

@dataclass
class StepTrace:
    name: str
    status: str  # "ran" | "skipped_disabled" | "skipped_exists" | "failed"
    elapsed_sec: float = 0.0
    outputs: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class FileTrace:
    input: str
    status: str  # "success" | "failed"
    steps: List[StepTrace] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RunReport:
    run_id: str
    pipeline_name: str
    config_path: str
    started_at: str
    finished_at: str = ""
    total_elapsed_sec: float = 0.0
    files: List[FileTrace] = field(default_factory=list)


# ── Config loading ─────────────────────────────────────────────────────────

def load_config(config_path: Path) -> PipelineConfig:
    """Load and parse a pipeline YAML config file.

    Raises
    ------
    FileNotFoundError
        If *config_path* does not exist.
    ValueError
        If the YAML is structurally invalid or contains unknown step names.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict) or "pipeline" not in raw:
        raise ValueError(
            f"Config {config_path} must have a top-level 'pipeline' key."
        )

    pipeline_raw = raw.get("pipeline", {})
    if not isinstance(pipeline_raw, dict):
        raise ValueError(
            f"'pipeline' in {config_path} must be a mapping, got {type(pipeline_raw).__name__}."
        )

    steps_raw = pipeline_raw.get("steps", [])
    if not isinstance(steps_raw, list):
        raise ValueError(
            f"'pipeline.steps' in {config_path} must be a list."
        )

    steps: List[StepConfig] = []
    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            raise ValueError(
                f"Step #{i} in {config_path} must be a mapping, got {type(s).__name__}."
            )
        if "name" not in s:
            raise ValueError(f"Step #{i} in {config_path} is missing required key 'name'.")
        step_name = s["name"]
        # Validate name against registered steps (only enabled steps need to be known).
        enabled = s.get("enabled", True)
        if enabled and step_name not in StepRegistry.names():
            known = ", ".join(StepRegistry.names()) or "(none registered)"
            raise ValueError(
                f"Unknown step {step_name!r} in {config_path}. "
                f"Known steps: {known}"
            )
        steps.append(
            StepConfig(
                name=step_name,
                enabled=enabled,
                params=s.get("params", {}),
            )
        )

    return PipelineConfig(
        name=pipeline_raw.get("name", "hydral_default"),
        input=pipeline_raw.get("input", "data/raw"),
        output=pipeline_raw.get("output", "data/processed/hydral"),
        glob=pipeline_raw.get(
            "glob", ["**/*.wav", "**/*.mp3", "**/*.flac", "**/*.m4a"]
        ),
        steps=steps,
    )


# ── Input collection ───────────────────────────────────────────────────────

def collect_inputs(input_path: Path, globs: List[str]) -> List[Path]:
    """Return sorted list of audio files from *input_path* (file or folder)."""
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        files: set[Path] = set()
        for pattern in globs:
            files.update(input_path.glob(pattern))
        return sorted(files)
    return []


# ── Step building ──────────────────────────────────────────────────────────

def build_step(step_cfg: StepConfig):
    """Instantiate a step object from a :class:`StepConfig` via the registry.

    Raises
    ------
    ValueError
        If the step name is not registered.
    """
    return StepRegistry.build(step_cfg.name, step_cfg.params)


# ── Report helpers ─────────────────────────────────────────────────────────

def _capture_outputs(step_name: str, ctx, step_trace: StepTrace) -> None:
    """Populate step_trace.outputs from ctx.artifacts (and ctx.extra fallback)."""
    from hydral.artifacts import Artifacts

    artifact_map = {
        "analyze": "features_json",
        "normalize": "normalized_wav",
        "grain": "grain_wav",
        "band_split": "band_dir",
    }
    attr = artifact_map.get(step_name)
    if attr:
        val = getattr(ctx.artifacts, attr, None)
        if val is not None:
            step_trace.outputs = [str(val)]
            return

    # Fallback: legacy ctx.extra string keys
    key_map = {
        "analyze": "features_path",
        "normalize": "normalized_path",
        "grain": "grain_path",
        "band_split": "band_split_manifest",
    }
    key = key_map.get(step_name)
    if key and key in ctx.extra:
        val = ctx.extra[key]
        if isinstance(val, dict) and "outputs" in val:
            step_trace.outputs = [str(o.get("path", "")) for o in val["outputs"]]
        else:
            step_trace.outputs = [str(val)]


def _write_cache_manifest(
    run_id: str,
    audio_file: Path,
    output_root: Path,
    step_fingerprints: Dict[str, Any],
) -> None:
    """Write a per-file fingerprint manifest under the run-isolated cache dir.

    Layout::

        <output_root>/runs/<run_id>/<stem>/.cache/manifest.json
    """
    cache_dir = output_root / "runs" / run_id / audio_file.stem / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(step_fingerprints, fh, indent=2)


def _report_to_dict(report: RunReport) -> dict:
    return {
        "run_id": report.run_id,
        "pipeline_name": report.pipeline_name,
        "config_path": report.config_path,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "total_elapsed_sec": report.total_elapsed_sec,
        "files": [
            {
                "input": f.input,
                "status": f.status,
                "error": f.error,
                "steps": [
                    {
                        "name": s.name,
                        "status": s.status,
                        "elapsed_sec": s.elapsed_sec,
                        "outputs": s.outputs,
                        "error": s.error,
                    }
                    for s in f.steps
                ],
            }
            for f in report.files
        ],
    }


def _write_report(report: RunReport, output_root: Path) -> Path:
    runs_dir = output_root / "_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    report_path = runs_dir / f"run_{report.run_id}.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(_report_to_dict(report), fh, indent=2)
    return report_path


# ── Main entry point ───────────────────────────────────────────────────────

def run_pipeline(config_path: Path) -> None:
    """Load *config_path* and execute the configured pipeline."""
    from hydral.pipeline import PipelineContext

    config = load_config(config_path)
    input_root = Path(config.input)
    output_root = Path(config.output)

    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    started_at = datetime.datetime.now().isoformat()

    print(f"\n🎵 Hydral Pipeline: {config.name!r}")
    print(f"   Config : {config_path}")
    print(f"   Input  : {input_root}")
    print(f"   Output : {output_root}")
    print(f"   Run ID : {run_id}")

    input_files = collect_inputs(input_root, config.glob)
    if not input_files:
        print(f"\n⚠  No audio files found under {input_root}")
        return

    print(f"\n📂 Found {len(input_files)} file(s):")
    for f in input_files:
        print(f"   {f}")

    report = RunReport(
        run_id=run_id,
        pipeline_name=config.name,
        config_path=str(config_path),
        started_at=started_at,
    )

    run_start = time.monotonic()

    for audio_file in input_files:
        print(f"\n▶  {audio_file.name}")

        output_dir = output_root / audio_file.stem
        ctx = PipelineContext(input_path=audio_file, output_dir=output_dir)

        file_trace = FileTrace(input=str(audio_file), status="success")
        file_failed = False
        step_fingerprints: Dict[str, Any] = {}

        for step_cfg in config.steps:
            if not step_cfg.enabled:
                print(f"   ⏭  {step_cfg.name} (disabled)")
                file_trace.steps.append(
                    StepTrace(name=step_cfg.name, status="skipped_disabled")
                )
                continue

            try:
                step = build_step(step_cfg)
            except ValueError as exc:
                print(f"   ✗  {step_cfg.name}: {exc}")
                file_trace.steps.append(
                    StepTrace(name=step_cfg.name, status="failed", error=str(exc))
                )
                file_failed = True
                continue

            # Collect fingerprint before potentially mutating ctx.audio_path
            if hasattr(step, "fingerprint"):
                step_fingerprints[step_cfg.name] = step.fingerprint(ctx)

            # Skip if the step's output already exists
            if hasattr(step, "output_exists") and step.output_exists(ctx):
                print(f"   ⏭  {step_cfg.name} (output exists)")
                file_trace.steps.append(
                    StepTrace(name=step_cfg.name, status="skipped_exists")
                )
                continue

            t0 = time.monotonic()
            try:
                ctx = step.run(ctx)
                elapsed = time.monotonic() - t0
                step_trace = StepTrace(
                    name=step_cfg.name,
                    status="ran",
                    elapsed_sec=round(elapsed, 3),
                )
                _capture_outputs(step_cfg.name, ctx, step_trace)
                print(f"      ({elapsed:.2f}s)")
                file_trace.steps.append(step_trace)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.monotonic() - t0
                print(f"   ✗  {step_cfg.name} failed: {exc}")
                file_trace.steps.append(
                    StepTrace(
                        name=step_cfg.name,
                        status="failed",
                        elapsed_sec=round(elapsed, 3),
                        error=str(exc),
                    )
                )
                file_failed = True

        # Write run-isolated fingerprint cache for this file
        if step_fingerprints:
            _write_cache_manifest(run_id, audio_file, output_root, step_fingerprints)

        if file_failed:
            file_trace.status = "failed"
            print(f"   ✗ {audio_file.name}: FAILED")
        else:
            print(f"   ✓ {audio_file.name}: OK")

        report.files.append(file_trace)

    total_elapsed = time.monotonic() - run_start
    report.total_elapsed_sec = round(total_elapsed, 3)
    report.finished_at = datetime.datetime.now().isoformat()

    report_path = _write_report(report, output_root)
    print(f"\n📄 Report: {report_path}")

    success_count = sum(1 for f in report.files if f.status == "success")
    print(
        f"✅ Done: {success_count}/{len(report.files)} files succeeded"
        f" in {total_elapsed:.2f}s"
    )

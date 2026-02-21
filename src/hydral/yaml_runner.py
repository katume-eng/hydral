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
    """Load and parse a pipeline YAML config file."""
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    pipeline_raw = raw.get("pipeline", {})
    steps_raw = pipeline_raw.get("steps", [])

    steps = [
        StepConfig(
            name=s["name"],
            enabled=s.get("enabled", True),
            params=s.get("params", {}),
        )
        for s in steps_raw
    ]

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
    """Instantiate a step object from a :class:`StepConfig`."""
    from hydral.steps import AnalyzeStep, BandSplitStep, GrainStep, NormalizeStep

    name = step_cfg.name
    params = step_cfg.params

    if name == "analyze":
        return AnalyzeStep(
            hop_length=params.get("hop_length", 512),
            smoothing_window=params.get("smoothing_window", 5),
            sr=params.get("sr"),
        )
    if name == "normalize":
        return NormalizeStep(
            target_db=params.get("target_db", -1.0),
        )
    if name == "band_split":
        return BandSplitStep(
            filter_order=params.get("filter_order", 5),
        )
    if name == "grain":
        return GrainStep(
            grain_sec=params.get("grain_sec", 0.5),
            seed=params.get("seed", 42),
        )
    raise ValueError(f"Unknown step: {name!r}")


# ── Report helpers ─────────────────────────────────────────────────────────

def _capture_outputs(step_name: str, ctx, step_trace: StepTrace) -> None:
    """Populate step_trace.outputs from ctx.extra after a step runs."""
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

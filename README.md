# Hydral

Hydral is a modular audio–analysis and audio–processing framework designed to convert sound into structured numerical data and controllable signals for visual expression, generative art, and interactive systems.

The project is intentionally split into clearly separated layers (core / analysis / pipelines / frontend) so that sound can be treated differently depending on purpose: as an object to manipulate, as a signal to analyze, or as data to drive visuals.

This repository currently focuses on the analysis pipeline that transforms WAV audio into time–series features usable in environments such as p5.js.

## Philosophy

Hydral is built around a simple principle:

> **The same sound should be handled differently depending on what you want to do with it.**

- **Editing and composing sound** requires audio objects
- **Measuring and understanding sound** requires signals and numbers
- **Expressing sound visually** requires stable control parameters

Hydral formalizes this separation instead of mixing concerns into a single, fragile pipeline.

## Core Concepts

### 1. Layer Separation

| Layer | Purpose | Representation |
|-------|---------|-----------------|
| **core** | Editing, playback, synthesis | AudioSegment (pydub) |
| **analysis** | Measurement, decomposition | NumPy arrays (librosa) |
| **pipelines** | Execution logic | Structured feature dictionaries |
| **frontend** | Expression & visualization | p5.js / Web / Graphics |

This is not duplication — it is intentional decoupling.

### 2. Analysis Features

Hydral currently extracts the following time–series features:

#### RMS Energy

- Represents overall loudness per frame
- Suitable for continuous controls (scale, brightness, zoom)

#### Frequency Band Energies

- **Low:** 20–200 Hz
- **Mid:** 200–2000 Hz
- **High:** 2000–8000 Hz

These allow separation of musical structure and timbre.

#### Onset Strength

- Detects sudden changes in sound
- Best used as event triggers rather than continuous values

#### Smoothing

- Moving average filtering
- Converts noisy raw features into stable control signals

## Analysis Pipeline

The standard analysis pipeline follows this flow:

1. Load WAV → waveform + sample rate
2. Extract numerical features (RMS, bands, onset)
3. Smooth signals for visual stability
4. Return structured feature data

### Example Usage

```python
from pipelines.analysis_pipelines import run_audio_analysis_pipeline

features = run_audio_analysis_pipeline(
    "input.wav",
    hop_length=512,
    smoothing_window=5
)
```

The resulting features dictionary can be:

- Serialized to JSON
- Synchronized with audio playback
- Consumed directly by visualization systems

## External Dependencies

- **ffmpeg** (required, available in PATH)

### Python Libraries

- numpy
- librosa
- scipy
- pydub

## Design Principles

- Single responsibility per module
- No hidden side effects
- Stable time alignment across all features
- Analysis results must be explainable and debuggable

> Hydral prioritizes clarity over cleverness.

## Intended Use Cases

- Audio–driven generative visuals (p5.js, WebGL)
- Music video prototyping
- Interactive installations
- Research experiments in audio–visual mapping
- Preprocessing for machine learning pipelines

## Non‑Goals (For Now)

- Real‑time streaming analysis
- End‑user audio editing UI
- High‑level musical understanding (chords, harmony)

Hydral is deliberately low‑level and composable.

## Status

This project is under active development. Interfaces may evolve, but layer separation and analysis semantics are considered stable.

### Future Extensions

- Feature normalization utilities
- JSON exporters
- Beat and tempo extraction
- Real‑time analysis bridges

## License

To be determined.

---

**Hydral treats sound not as something to merely hear, but as something to measure, structure, and transform into expression.**

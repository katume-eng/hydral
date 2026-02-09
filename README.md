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
| ------- | --------- | ----------------- |
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

Hydral is deliberately low‑level and composable.

## Song Generation (songMaking)

The `/songMaking` subsystem generates MIDI melodies using various algorithmic approaches. This is **separate from and independent of** water audio editing - it exists in the same repository purely for unified tooling and workflow management.

### Generation Methods

Three distinct algorithms are available:

- **random**: Constrained random selection within harmonic boundaries
- **scored**: Generates multiple candidates and selects highest-quality via evaluation metrics
- **markov**: N-gram transition model trained on synthetic melodic patterns

### Usage

```bash
# Generate using random method
python -m songMaking.cli --method random --seed 42

# Generate with scored method (evaluates multiple candidates)
python -m songMaking.cli --method scored --seed 123 --candidates 20

# Generate with Markov chains
python -m songMaking.cli --method markov --seed 999 --ngram-order 2

# Customize tempo range
python -m songMaking.cli --method random --seed 42 --min-bpm 100 --max-bpm 160
```

### Concatenated Fragment Export

Generate multiple short melody fragments and concatenate them into a single MIDI file with constraint-based filtering:

```bash
# Generate 20 fragments (2 bars each) with 1-beat gaps
python -m songMaking.export.concat_fragments --method random --seed 123 --out outputs/audition_001

# Customize fragment count, length, and gaps
python -m songMaking.export.concat_fragments --method markov --seed 456 \
  --n-fragments 30 --bars 4 --gap-beats 2.0 --out outputs/long_session

# Apply pitch constraints (MIDI note numbers)
python -m songMaking.export.concat_fragments --method scored --seed 789 \
  --min-pitch 60 --max-pitch 84 --target-mean-pitch 72 --mean-tolerance 6 \
  --out outputs/constrained_range
```

Each fragment is generated independently with its own harmony spec. Constraints are checked per fragment, with automatic retry (up to `--max-attempts`, default 25) until requirements are met.

### Interactive Audition

The audition tool generates concatenated fragments and optionally plays them back (if `pygame.midi` is available):

```bash
# Generate and audition fragments
python -m songMaking.player.audition --method random --seed 999 --n-fragments 15

# With constraints and custom output
python -m songMaking.player.audition --method markov --seed 123 \
  --min-pitch 55 --max-pitch 79 --out outputs/audition_session_01
```

If `pygame.midi` is not installed, fragments are still generated and exported for playback in external MIDI players.

### MIDI Playback

Play any generated MIDI file with precise control over tempo, instrument, and playback parameters:

```bash
# Basic playback
python -m songMaking.player.play_midi songMaking/output/melody_001.mid

# Play with different instrument (e.g., electric guitar = program 26)
python -m songMaking.player.play_midi song.mid --program 26

# Slow down to 50% speed for detailed listening
python -m songMaking.player.play_midi song.mid --bpm-scale 0.5

# Speed up to 1.5x for quick audition
python -m songMaking.player.play_midi song.mid --bpm-scale 1.5

# List available MIDI devices
python -m songMaking.player.play_midi --list-devices
```

**Requirements:** `pip install mido pygame`

**Features:**
- Accurate timing with tempo change support
- Tempo scaling via `--bpm-scale` (0.5 = half speed, 2.0 = double speed)
- Instrument override via `--program` (0-127, General MIDI)
- Clean Ctrl+C handling

### Output

Each generation produces two files in `songMaking/output/`:

- **MIDI file** (`.mid`): Playable melody
- **JSON metadata** (`.json`): Complete generation parameters including:
  - Method used
  - Random seed (for reproducibility)
  - Harmonic specification (key, scale, tempo, time signature, chord progression)
  - Generation config (candidates, n-gram order, etc.)
  - Quality metrics

### Reproducibility

Given the same seed and parameters, generation is **fully deterministic**:

```bash
# These produce identical MIDI output
python -m songMaking.cli --method random --seed 42
python -m songMaking.cli --method random --seed 42
```

### Key Design Principles

- **Harmonic spec separation**: `HarmonySpec` defines musical context, generators implement methods
- **Pluggable methods**: All generators consume same `HarmonySpec` interface
- **Evaluation-driven**: Scoring functions (`eval.py`) assess melody quality
- **No cross-contamination**: `/songMaking` does not depend on `/hydral` water audio tools

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

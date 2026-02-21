# Band Split Processing Module

This module splits audio files into 5 frequency bands and further separates each band into tonal (harmonic) and noise (percussive) components, resulting in 10 output files per input.

## Features

- **5-Band Frequency Splitting**: Configurable frequency bands using Butterworth bandpass filters
- **Tonal/Noise Separation**: HPSS (Harmonic-Percussive Source Separation) for each band
- **Metadata Tracking**: JSON manifest with complete processing metadata
- **Flexible Configuration**: Customizable band definitions, sample rates, and processing parameters

## Default Band Definitions

| Band    | Frequency Range (Hz) | Description          |
|---------|---------------------|----------------------|
| band01  | 20 – 120            | Sub-bass             |
| band02  | 120 – 300           | Bass                 |
| band03  | 300 – 900           | Low-mid              |
| band04  | 900 – 3000          | Mid-high             |
| band05  | 3000 – 12000        | High / Presence      |

## Output Structure

```
data/processed/band_split/v1/<input_stem>/
├── band01_tonal.wav
├── band01_noise.wav
├── band02_tonal.wav
├── band02_noise.wav
├── band03_tonal.wav
├── band03_noise.wav
├── band04_tonal.wav
├── band04_noise.wav
├── band05_tonal.wav
├── band05_noise.wav
└── split_manifest.json
```

## Usage

### Basic Usage

```bash
python -m processing.band_split.cli --input path/to/audio.wav
```

This will:
1. Load the input audio file
2. Split it into 5 frequency bands
3. Separate each band into tonal and noise components
4. Save 10 WAV files to `data/processed/band_split/v1/<input_stem>/`
5. Generate a `split_manifest.json` with processing metadata

### Advanced Options

```bash
python -m processing.band_split.cli \
    --input path/to/audio.wav \
    --out-root custom/output/path \
    --sr 44100 \
    --mono \
    --filter-order 6 \
    --hpss-kernel 41
```

### Command-Line Arguments

- `--input` (required): Path to input WAV file
- `--out-root` (optional): Output root directory (default: `data/processed/band_split/v1`)
- `--bands` (optional): Custom band definitions as JSON string or file path
- `--sr` (optional): Target sample rate for processing (default: use original)
- `--mono` (optional): Convert to mono before processing
- `--filter-order` (optional): Butterworth filter order (default: 5)
- `--hpss-kernel` (optional): HPSS kernel size (default: 31)
- `--hpss-margin` (optional): HPSS margin for soft masking (default: 2.0)

### Custom Band Definitions

You can provide custom band definitions via JSON:

**As a file:**
```bash
python -m processing.band_split.cli \
    --input audio.wav \
    --bands custom_bands.json
```

**custom_bands.json:**
```json
{
  "band01": {"low_hz": 20, "high_hz": 150},
  "band02": {"low_hz": 150, "high_hz": 500},
  "band03": {"low_hz": 500, "high_hz": 2000},
  "band04": {"low_hz": 2000, "high_hz": 8000},
  "band05": {"low_hz": 8000, "high_hz": 16000}
}
```

**As a JSON string:**
```bash
python -m processing.band_split.cli \
    --input audio.wav \
    --bands '{"band01": {"low_hz": 20, "high_hz": 200}}'
```

## Output Format

All output files are saved as **float32 WAV** files with peak normalization to -1 dBFS to prevent clipping.

## Manifest JSON

The `split_manifest.json` file contains:

```json
{
  "version": "v1",
  "created_at": "2026-02-10T01:59:18.984Z",
  "input": {
    "path": "path/to/input.wav",
    "sample_rate": 44100,
    "channels": 2,
    "duration_sec": 5.5,
    "sha256": "abc123..."
  },
  "processing": {
    "band_method": "butter_bandpass_sosfiltfilt",
    "band_params": {
      "order": 5
    },
    "hpss_method": "librosa_hpss",
    "hpss_params": {
      "kernel_size": 31,
      "margin": 2.0
    }
  },
  "bands": {
    "band01": {"low_hz": 20, "high_hz": 120},
    ...
  },
  "outputs": [
    {
      "path": "band01_tonal.wav",
      "band_id": "band01",
      "component": "tonal",
      "sample_rate": 44100,
      "channels": 2,
      "duration_sec": 5.5,
      "format": "float32"
    },
    ...
  ]
}
```

## Processing Details

### Bandpass Filtering

- **Method**: Butterworth bandpass filter (IIR)
- **Implementation**: `scipy.signal.butter` + `sosfiltfilt` (zero-phase)
- **Order**: Configurable (default: 5)
- **Frequency Clipping**: Automatically clips to Nyquist frequency

### Tonal/Noise Separation

- **Method**: HPSS (Harmonic-Percussive Source Separation)
- **Implementation**: `librosa.effects.hpss`
- **Kernel Size**: Configurable (default: 31)
- **Margin**: Configurable soft masking margin (default: 2.0)

### Normalization

- Peak normalization to -1 dBFS to prevent clipping
- Applied independently to each output file

## Dependencies

All required dependencies are already in `requirements.txt`:
- `librosa` (HPSS and audio loading)
- `scipy` (Butterworth filtering)
- `soundfile` (WAV I/O)
- `numpy` (array operations)

## Example Workflow

```bash
# 1. Process a water sound recording
python -m processing.band_split.cli --input data/raw/water_sound.wav

# 2. Check the output
ls data/processed/band_split/v1/water_sound/

# 3. View the manifest
cat data/processed/band_split/v1/water_sound/split_manifest.json

# 4. Use custom settings for high-quality processing
python -m processing.band_split.cli \
    --input data/raw/water_sound.wav \
    --sr 48000 \
    --filter-order 6 \
    --hpss-kernel 41
```

## Integration with Hydral

This module fits into the Hydral processing layer:

- **Input**: Raw WAV files (typically from `data/raw/`)
- **Output**: Processed audio components in `data/processed/band_split/v1/`
- **Use Case**: Preparing water sounds for further analysis or creative processing

The split components can be used for:
- Individual band manipulation
- Tonal/noise analysis
- Creative sound design
- Multi-band compression or effects

## Notes

- Frequencies exceeding the Nyquist frequency are automatically clipped
- Multi-channel audio is supported (each channel is processed independently)
- The `--mono` flag can be used to mix down to mono before processing
- All processing is done in-memory; ensure sufficient RAM for long files

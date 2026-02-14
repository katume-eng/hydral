# Data Structure

This project expects the following structure:

```bash
data/
　packs/
  raw/
  processed/
  selected/
    low_freq/
    high_freq/
```

Each audio file (.wav) must have a corresponding metadata .json file.

Metadata schema:
{
  "file": "kawa_01.wav",
  "tags": ["low_freq_rich", "river"],
  "min_pitch": 120.5,
  "max_pitch": 4300.2,
  "low_band_ratio": 0.63
}

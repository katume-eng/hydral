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

low_freq_rich は解析で自動付与できます。例:

```bash
python processing/tag_low_freq_rich.py --data-root data --threshold 0.25 --dry-run
python processing/tag_low_freq_rich.py --data-root data --threshold 0.25 --backup
python processing/tag_low_freq_rich.py --data-root data --threshold 0.25 --remove-if-not-rich
```

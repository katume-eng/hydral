# Melody Structure Constraints - Quick Reference

## Overview
Melody generation now supports structural constraints for creating cohesive, repeating musical patterns.

## Key Features

### 1. Repeating Motifs
Generate melodies with repeating musical units:
```bash
--repeat-unit-beats 4.0  # 1 bar in 4/4 time
```

### 2. Motif Variations
Allow subtle variations in repeated sections:
```bash
--allow-motif-variation
--variation-probability 0.3  # 30% chance per repeat
```

**Variation Types:**
- **Transpose**: ±1 or ±2 semitones
- **Neighbor tone**: Single note ±1 semitone  
- **Inversion**: Reverse interval directions

### 3. Rhythm Profiles
Target specific duration distributions:
```bash
--rhythm-profile '{"0.5": 0.6, "1.0": 0.4}'
```
This targets 60% eighth notes (0.5 beats), 40% quarter notes (1.0 beats).

## CLI Examples

### Simple Repetition
```bash
python -m songMaking.cli \
  --method random \
  --bars 4 \
  --repeat-unit-beats 4.0
```

### Repetition with Variation
```bash
python -m songMaking.cli \
  --method scored \
  --bars 4 \
  --repeat-unit-beats 2.0 \
  --allow-motif-variation \
  --variation-probability 0.5
```

### Rhythm Profile Only
```bash
python -m songMaking.cli \
  --method markov \
  --bars 2 \
  --rhythm-profile '{"0.5": 0.5, "1.0": 0.3, "2.0": 0.2}'
```

### All Constraints Combined
```bash
python -m songMaking.cli \
  --method scored \
  --bars 4 \
  --repeat-unit-beats 4.0 \
  --allow-motif-variation \
  --variation-probability 0.3 \
  --rhythm-profile '{"0.5": 0.6, "1.0": 0.4}' \
  --candidates 20
```

## Metadata Output

Generated JSON includes:

```json
{
  "structure": {
    "enabled": true,
    "repeat_unit_beats": 4.0,
    "rhythm_profile": {"0.5": 0.6, "1.0": 0.4},
    "allow_motif_variation": true,
    "variation_probability": 0.3
  },
  "debug_stats": {
    "repeat_count": 4,
    "actual_duration_distribution": {
      "0.5": 0.625,
      "1.0": 0.375
    }
  }
}
```

## Scoring Metrics

When using `--method scored`, structural constraints add new metrics:

- **self_similarity** (0-1): Measures repetition consistency
- **rhythm_alignment** (0-1): Measures rhythm profile match

These are weighted and combined with existing metrics (complexity, contour, smoothness, variety, etc.).

## Common Patterns

### Pop/Rock Verse
```bash
--bars 8 --repeat-unit-beats 4.0 --allow-motif-variation --variation-probability 0.2
```

### Minimalist/Techno
```bash
--bars 8 --repeat-unit-beats 2.0 --rhythm-profile '{"0.25": 0.7, "0.5": 0.3}'
```

### Classical Theme
```bash
--bars 8 --repeat-unit-beats 4.0 --rhythm-profile '{"0.5": 0.4, "1.0": 0.4, "2.0": 0.2}'
```

### Jazz Motif
```bash
--bars 4 --repeat-unit-beats 2.0 --allow-motif-variation --variation-probability 0.6
```

## Notes

- All structural constraints are **optional**
- Without constraints, generation behaves as before (backward compatible)
- `--repeat-unit-beats` should divide evenly into total duration
- Rhythm profile values should sum to ~1.0 (proportions)
- Variation is probabilistic - may not occur every time
- Works with all three methods: random, scored, markov

## Duration Values

Standard durations in beats (quarter note = 1.0):
- `4.0` - Whole note
- `2.0` - Half note
- `1.0` - Quarter note
- `0.5` - Eighth note
- `0.25` - Sixteenth note
- `0.125` - Thirty-second note

## Troubleshooting

**Q: Repetition not happening?**
- Check that `--bars` × beats_per_bar ÷ `--repeat-unit-beats` ≥ 2
- Example: 2 bars × 4 beats ÷ 4.0 = 2 repeats ✓

**Q: Rhythm profile not matching?**
- Profile is a target, not strict enforcement
- Check `actual_duration_distribution` in metadata
- Scored method will select candidates closer to target

**Q: No variations appearing?**
- Increase `--variation-probability` (try 0.5-1.0)
- Variations are random - try different seeds
- Only applies to repeats after the first occurrence

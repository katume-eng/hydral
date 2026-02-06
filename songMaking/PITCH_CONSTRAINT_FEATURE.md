# Mean Pitch Target/Tolerance Feature

## Overview
The songMaking system now supports constraining melody generation by mean pitch. This allows you to specify a target average pitch and tolerance, with the generator automatically retrying until the constraint is satisfied.

## Usage

### CLI Options

```bash
python -m songMaking.cli \
  --mean-pitch-target 60 \
  --mean-pitch-tolerance 2.0 \
  --max-attempts 100
```

**Options:**
- `--mean-pitch-target FLOAT`: Target mean pitch in MIDI notation (e.g., 60 for middle C). Optional.
- `--mean-pitch-tolerance FLOAT`: Tolerance in semitones (default: 2.0). Only used if target is specified.
- `--max-attempts INT`: Maximum generation attempts before giving up (default: 100).

### MIDI Pitch Reference
- C3 = 48 (low male voice)
- C4 = 60 (middle C, typical center pitch)
- C5 = 72 (soprano range)
- C6 = 84 (high soprano)

### Examples

**Generate melody with mean pitch around middle C (60 ± 2 semitones):**
```bash
python -m songMaking.cli --method random --seed 42 \
  --mean-pitch-target 60 --mean-pitch-tolerance 2
```

**Generate melody in soprano range (72 ± 3 semitones):**
```bash
python -m songMaking.cli --method scored --seed 123 \
  --mean-pitch-target 72 --mean-pitch-tolerance 3 --max-attempts 200
```

**Generate without constraint (original behavior):**
```bash
python -m songMaking.cli --method random --seed 42
```

## How It Works

1. **Generation Loop**: When a pitch target is specified, the generator runs in a loop with incrementing seeds
2. **Constraint Check**: After each generation, calculates mean pitch of sounding notes (rests excluded)
3. **Acceptance**: If mean pitch falls within `target ± tolerance`, generation stops
4. **Retry**: Otherwise, increments seed and tries again
5. **Fallback**: After `max-attempts`, returns the last generated melody with a warning

## Implementation Details

### New Module: `pitch_stats.py`
Provides utilities for pitch analysis:
- `calculate_mean_pitch(midi_notes)`: Calculate average pitch, excluding rests
- `check_pitch_constraint(midi_notes, target, tolerance)`: Verify constraint satisfaction
- `get_pitch_stats(midi_notes)`: Comprehensive pitch statistics

### Modified Files
- **cli.py**: 
  - Added CLI options for pitch constraints
  - Implemented generation loop with retry logic
  - Enhanced metadata to include pitch statistics and constraint info
  
- **Metadata JSON**: Now includes:
  ```json
  {
    "pitch_constraint": {
      "enabled": true,
      "target_mean": 60.0,
      "tolerance": 2.0,
      "max_attempts": 100,
      "attempts_used": 5
    },
    "result": {
      "pitch_stats": {
        "mean": 60.5,
        "min": 55,
        "max": 67,
        "range": 12,
        "sounding_count": 10
      }
    }
  }
  ```

## Testing

Run the pitch constraint tests:
```bash
python -m songMaking.test_pitch_constraint
```

Tests cover:
- Mean pitch calculation with and without rests
- Constraint checking (within/outside tolerance, boundaries)
- Comprehensive pitch statistics
- Generation loop behavior
- Metadata integration

## Performance Considerations

- **Tight Constraints**: Very narrow tolerances may require many attempts
- **Seed Strategy**: Each attempt uses `seed + attempt_number` for deterministic variation
- **Recommendation**: Use tolerance ≥ 2.0 semitones for reasonable performance
- **Fallback**: System always produces output even if constraint can't be met

## Design Rationale

Following repo conventions:
- ✅ Small, focused changes
- ✅ Backward compatible (constraint is optional)
- ✅ Reproducible (seed-based retry)
- ✅ Well-tested (comprehensive test suite)
- ✅ Documented metadata (full logging of attempts and results)
- ✅ No cross-system dependencies (/songMaking only)

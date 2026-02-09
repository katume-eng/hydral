# Melody Structure Specification Implementation Summary

## Overview
Implemented comprehensive structural constraints for MIDI melody generation in the Hydral /songMaking system. This adds repeating motif patterns, rhythm profile targeting, subtle variations, and enhanced scoring/metadata.

## New Files Created

### 1. `songMaking/structure.py` (2,231 bytes)
Defines `MelodyStructureSpec` dataclass with:
- `repeat_unit_beats`: Length of repeating unit in beats (e.g., 4.0 for 1 bar)
- `rhythm_profile`: Target duration distribution as `{duration: proportion}`
- `allow_motif_variation`: Enable subtle pitch variations in repeated motifs
- `variation_probability`: Probability of applying variation (0.0-1.0)

Helper functions:
- `create_default_structure_spec()`: No constraints
- `create_structured_spec()`: Configured spec with all options

### 2. `songMaking/structure_utils.py` (6,866 bytes)
Utility functions for applying structural constraints:
- `apply_motif_repetition()`: Repeats first unit with optional variations
- `_apply_subtle_variation()`: Applies transpose, neighbor, or inversion variation
- `enforce_rhythm_profile()`: Adjusts durations to match target distribution
- `calculate_repeat_count()`: Counts complete repeating units
- `compute_duration_distribution()`: Calculates actual rhythm distribution

### 3. `songMaking/test_structure.py` (8,584 bytes)
Comprehensive test suite covering:
- Structure spec creation and configuration
- Self-similarity and rhythm profile metrics
- Motif repetition and variation application
- All three generators (random, scored, markov) with structure
- Duration distribution and repeat count calculation

## Modified Files

### 1. `songMaking/eval.py`
**Added metrics:**
- `measure_self_similarity()`: Scores repetition quality (0-1)
  - Segments melody into units based on `repeat_unit_beats`
  - Compares consecutive units for exact or partial matches
  - Returns average similarity across all unit pairs

- `measure_rhythm_profile_alignment()`: Scores rhythm distribution match (0-1)
  - Calculates actual duration distribution from sequence
  - Compares to target profile using sum of absolute differences
  - Normalizes to 0-1 score

**Updated:**
- `aggregate_melody_score()`: Now accepts optional `structure_spec`
  - Adds `self_similarity` metric when `repeat_unit_beats` specified
  - Adds `rhythm_alignment` metric when `rhythm_profile` specified
  - Auto-adjusts weights to maintain normalization

### 2. `songMaking/generators/random.py`
**Updated `generate_random_melody()`:**
- Added `structure_spec: Optional[MelodyStructureSpec]` parameter
- Applies rhythm profile to duration selection (weighted choice)
- Calls `apply_motif_repetition()` post-generation if enabled
- Tracks `repeat_count` and `actual_duration_distribution` in debug stats

### 3. `songMaking/generators/scored.py`
**Updated `generate_scored_melody()`:**
- Added `structure_spec` parameter, passes to `generate_random_melody()`
- Includes structure-specific durations in validation
- Passes `structure_spec` to `aggregate_melody_score()` for structural scoring
- Propagates new debug stats (`repeat_count`, `actual_duration_distribution`)

### 4. `songMaking/generators/markov.py`
**Updated `generate_markov_melody()`:**
- Added `structure_spec` parameter
- Applies rhythm profile to duration selection (weighted choice)
- Calls `apply_motif_repetition()` post-generation if enabled
- Tracks structural debug stats

### 5. `songMaking/cli.py`
**New CLI arguments:**
- `--repeat-unit-beats FLOAT`: Repeating unit length in beats
- `--allow-motif-variation`: Enable subtle variations (flag)
- `--variation-probability FLOAT`: Variation probability (0.0-1.0)
- `--rhythm-profile JSON`: Target rhythm as `{"0.5": 0.6, "1.0": 0.4}`

**Updated logic:**
- Parses structure spec from CLI args (with JSON rhythm profile)
- Displays structural constraints when enabled
- Passes `structure_spec` to `generate_melody_midi()`
- Includes structure metadata in JSON output

**Updated metadata export:**
- Added `structure` section:
  - `enabled`, `repeat_unit_beats`, `rhythm_profile`
  - `allow_motif_variation`, `variation_probability`
- Enhanced `debug_stats`:
  - `repeat_count`: Number of complete repeating units
  - `actual_duration_distribution`: Actual rhythm proportions

## Usage Examples

### Basic Repetition
```bash
python -m songMaking.cli \
  --method random \
  --bars 4 \
  --repeat-unit-beats 4.0 \
  --output-dir output/
```
Generates 4-bar melody with 1-bar (4 beat) repeating motif, exact repetition.

### Repetition with Variation
```bash
python -m songMaking.cli \
  --method scored \
  --bars 4 \
  --repeat-unit-beats 4.0 \
  --allow-motif-variation \
  --variation-probability 0.3 \
  --output-dir output/
```
Generates with 30% chance of subtle variation on each repeat (transpose, neighbor, inversion).

### Rhythm Profile Targeting
```bash
python -m songMaking.cli \
  --method markov \
  --bars 2 \
  --rhythm-profile '{"0.5": 0.6, "1.0": 0.4}' \
  --output-dir output/
```
Targets 60% eighth notes, 40% quarter notes.

### Combined Constraints
```bash
python -m songMaking.cli \
  --method scored \
  --bars 4 \
  --repeat-unit-beats 2.0 \
  --rhythm-profile '{"0.5": 0.5, "1.0": 0.5}' \
  --allow-motif-variation \
  --candidates 20 \
  --output-dir output/
```
2-beat repeating units, 50/50 rhythm mix, variations enabled, scored selection.

## Behavioral Changes

### Generation
- **Without structure spec**: Behavior unchanged (backward compatible)
- **With repeat_unit_beats**: First unit extracted and repeated with optional variation
- **With rhythm_profile**: Duration selection weighted by target proportions
- **Scored method**: Now considers structural metrics in candidate scoring

### Scoring
- Default weights unchanged when no structure spec provided
- With structure spec, adds `self_similarity` (weight 0.15) and/or `rhythm_alignment` (weight 0.15)
- Weights auto-normalized to sum to 1.0

### Metadata
- Always includes `structure` section (enabled: false if not used)
- `debug_stats` always includes `repeat_count` (0 if not used) and `actual_duration_distribution`

## Testing

All tests pass:
- **New**: `songMaking/test_structure.py` (9 tests)
  - Structure spec creation
  - Self-similarity and rhythm alignment metrics
  - Motif repetition with/without variation
  - All three generators with structure
  - Utility function correctness

- **Existing**: `songMaking/test_melody_improvements.py` (12 tests)
  - All existing tests still pass (backward compatibility verified)

## Implementation Notes

### Design Decisions
1. **Optional parameters**: Structure spec is fully optional - no breaking changes
2. **Post-generation application**: Repetition applied after initial generation to maintain generator simplicity
3. **Variation types**: Three variation methods (transpose, neighbor, inversion) for musical diversity
4. **Metric integration**: Structural metrics added to existing scoring framework, not replacing it

### Variation Strategies
- **Transpose**: ±1 or ±2 semitones (maintains contour)
- **Neighbor tone**: Single note ±1 semitone (minimal change)
- **Inversion**: Interval directions reversed around anchor (melodic inversion)

### Rhythm Profile Enforcement
- Weighted random selection during generation (probabilistic)
- Not strict enforcement - allows musical flexibility
- Actual distribution tracked in metadata for verification

### Minimal Changes Principle
- No changes to `HarmonySpec` (separation of concerns)
- No changes to MIDI export (structure is generation concern)
- No changes to existing utility functions (new utilities added separately)
- Backward compatible - all existing code works unchanged

## Metadata Schema

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
    "repeat_count": 2,
    "actual_duration_distribution": {
      "0.5": 0.625,
      "1.0": 0.375
    },
    // ... existing fields ...
  }
}
```

## Performance Impact
- Minimal: Structure application is O(n) post-processing
- Scored method: Same candidate count, slightly more complex scoring
- No impact when structure spec not used

## Future Enhancements (Not Implemented)
- Multi-level repetition (nested structures)
- Pitch set constraints for variations
- Exact rhythm enforcement mode
- Cross-generator structure templates
- Structure validation and suggestion

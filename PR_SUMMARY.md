# Pull Request Summary: Melody Structure Constraints

## Overview
This PR implements comprehensive structural constraints for MIDI melody generation in the Hydral /songMaking system, enabling repeating motifs, rhythm profile targeting, subtle variations, and enhanced scoring.

## Changes Summary

### New Files (4)
1. **songMaking/structure.py** - Core `MelodyStructureSpec` dataclass
2. **songMaking/structure_utils.py** - Utility functions for structural operations
3. **songMaking/test_structure.py** - Test suite (9 tests, all passing)
4. **songMaking/STRUCTURE_QUICK_REFERENCE.md** - User documentation

### Modified Files (5)
1. **songMaking/eval.py** - Added structural scoring metrics
2. **songMaking/generators/random.py** - Structure spec support
3. **songMaking/generators/scored.py** - Structure spec + structural scoring
4. **songMaking/generators/markov.py** - Structure spec support
5. **songMaking/cli.py** - New CLI args + enhanced metadata

## Features Implemented

### 1. MelodyStructureSpec
New dataclass defining structural constraints:
- `repeat_unit_beats`: Length of repeating unit (e.g., 4.0 for 1 bar in 4/4)
- `rhythm_profile`: Target duration distribution `{duration: proportion}`
- `allow_motif_variation`: Enable subtle pitch variations
- `variation_probability`: Probability of variation per repeat (0.0-1.0)

### 2. Structural Scoring Metrics
- **Self-similarity** (0-1): Measures repetition consistency
  - Segments melody into units based on repeat_unit_beats
  - Compares consecutive units for exact/partial matches
- **Rhythm alignment** (0-1): Measures rhythm profile match
  - Compares actual vs target duration distribution
  - Uses sum of absolute differences, normalized to 0-1

Both metrics integrate into existing scoring framework with auto-normalized weights.

### 3. Motif Variation Strategies
Three probabilistic variation types:
- **Transpose**: ±1 or ±2 semitones (maintains melodic contour)
- **Neighbor tone**: Single note ±1 semitone (minimal variation)
- **Inversion**: Reverse interval directions around anchor (melodic inversion)

### 4. CLI Extensions
```bash
--repeat-unit-beats FLOAT           # Repeating unit length in beats
--allow-motif-variation             # Enable variations (flag)
--variation-probability FLOAT       # Variation chance (0.0-1.0, default: 0.3)
--rhythm-profile JSON               # Target rhythm as JSON dict
```

Example:
```bash
python -m songMaking.cli \
  --method scored \
  --bars 4 \
  --repeat-unit-beats 4.0 \
  --allow-motif-variation \
  --rhythm-profile '{"0.5": 0.6, "1.0": 0.4}'
```

### 5. Enhanced Metadata
JSON output now includes:
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
    }
  }
}
```

## Testing

### Test Results
- **New tests**: 9/9 passing (test_structure.py)
- **Existing tests**: 26/26 passing
  - test_melody_improvements.py: 12/12 ✓
  - test_pitch_constraint.py: 8/8 ✓
  - test_timing.py: 6/6 ✓
- **Integration test**: PASSED (all generators with all features)

### Test Coverage
- Structure spec creation and configuration
- Self-similarity metric (perfect repetition vs random)
- Rhythm profile alignment (match vs mismatch)
- Motif repetition with/without variation
- All three generators (random, scored, markov) with structure
- Duration distribution and repeat count calculation
- CLI argument parsing and metadata export
- Backward compatibility (all existing tests pass)

## Design Principles

### ✅ Minimal Changes
- No modifications to `HarmonySpec` (separation of concerns)
- No changes to MIDI export (structure is generation-level concern)
- No changes to core utility functions (new utilities added separately)
- All changes are additive, not destructive

### ✅ Backward Compatibility
- Structure spec is completely optional (defaults to None)
- Without structure spec, behavior is identical to before
- All existing code and tests work unchanged
- Zero performance overhead when not using structure features

### ✅ Clean Architecture
- Clear separation: harmony (tonality) vs structure (form)
- Utilities isolated in separate module (structure_utils.py)
- Type hints throughout with proper Optional handling
- Comprehensive docstrings for all public functions

### ✅ Extensibility
- Easy to add new variation strategies
- Straightforward to add new structural constraints
- Metrics integrate cleanly with existing scoring
- CLI args follow established patterns

## Usage Examples

### Python API
```python
from songMaking.structure import create_structured_spec
from songMaking.generators.scored import generate_scored_melody

# Create structure spec
structure = create_structured_spec(
    repeat_unit_beats=4.0,
    rhythm_profile={0.5: 0.6, 1.0: 0.4},
    allow_variation=True,
    variation_prob=0.3
)

# Generate with structure
pitches, durations, score, stats = generate_scored_melody(
    harmony_spec, seed, config, structure
)

# Access structural info
print(f"Repeats: {stats['repeat_count']}")
print(f"Rhythm: {stats['actual_duration_distribution']}")
```

### CLI
```bash
# Simple repetition
python -m songMaking.cli --method random --bars 4 \
  --repeat-unit-beats 4.0

# With variation
python -m songMaking.cli --method scored --bars 4 \
  --repeat-unit-beats 2.0 --allow-motif-variation

# With rhythm profile
python -m songMaking.cli --method markov --bars 2 \
  --rhythm-profile '{"0.5": 0.5, "1.0": 0.5}'

# All features combined
python -m songMaking.cli --method scored --bars 4 \
  --repeat-unit-beats 4.0 --allow-motif-variation \
  --variation-probability 0.4 \
  --rhythm-profile '{"0.5": 0.5, "1.0": 0.3, "2.0": 0.2}' \
  --candidates 20
```

## Performance Impact

- **Without structure**: Zero overhead (early return checks)
- **With structure**: O(n) post-processing for repetition
- **Memory**: Minimal (only structure spec object)
- **Scored method**: Same candidate count, +2 metrics (negligible)

## Breaking Changes

**None.** All changes are backward compatible:
- Structure spec defaults to None (no constraints)
- Existing generators work unchanged
- Metadata always includes structure section (enabled: false when not used)
- All existing tests pass without modification

## Documentation

- **STRUCTURE_QUICK_REFERENCE.md**: User guide with examples
- **STRUCTURE_IMPLEMENTATION_SUMMARY.md**: Technical details
- **Comprehensive docstrings**: All new functions documented
- **Type hints**: Throughout for IDE support

## Future Enhancements
(Not in scope for this PR)
- Multi-level nested repetition
- Pitch set constraints for variations
- Strict rhythm enforcement mode
- Cross-generator structure templates
- Structure validation and suggestions

## Verification

### Quick Verification
```bash
# Run all tests
python songMaking/test_structure.py
python songMaking/test_melody_improvements.py
python songMaking/test_pitch_constraint.py
python songMaking/test_timing.py

# Test CLI
python -m songMaking.cli --method scored --bars 4 \
  --repeat-unit-beats 4.0 --allow-motif-variation

# Check metadata
cat songMaking/output/*.json | python -m json.tool | grep -A 10 structure
```

### Integration Test
All generators work correctly with all structural features combined - verified via integration test showing proper functioning of:
- Repetition application
- Variation strategies
- Rhythm profile influence
- Structural scoring metrics
- Metadata tracking

## Conclusion

This PR successfully implements all requested features:
- ✅ MelodyStructureSpec with repeat_unit_beats and rhythm_profile
- ✅ Applied to random/scored/markov generation
- ✅ Scoring with repeat/self-correlation and rhythm alignment
- ✅ Subtle motif variations (3 strategies)
- ✅ Comprehensive metadata (all requested fields)
- ✅ Minimal changes (no breaking modifications)
- ✅ Focused tests (9 new, 26 existing pass)
- ✅ CLI args and config updated

Ready for review and merge.

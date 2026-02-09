"""
Tests for melody structure specification and structural constraints.
Tests repeat unit, rhythm profile, motif variation, and structural scoring.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from songMaking.harmony import choose_harmony
from songMaking.structure import MelodyStructureSpec, create_structured_spec
from songMaking.generators.random import generate_random_melody
from songMaking.generators.scored import generate_scored_melody
from songMaking.generators.markov import generate_markov_melody
from songMaking.eval import (
    measure_self_similarity,
    measure_rhythm_profile_alignment,
    aggregate_melody_score
)
from songMaking.structure_utils import (
    apply_motif_repetition,
    calculate_repeat_count,
    compute_duration_distribution
)


def test_structure_spec_creation():
    """Test creating structure specs with various configurations."""
    # Default spec - no constraints
    spec1 = MelodyStructureSpec()
    assert spec1.repeat_unit_beats is None
    assert spec1.rhythm_profile is None
    assert not spec1.allow_motif_variation
    
    # Structured spec with repetition
    spec2 = create_structured_spec(
        repeat_unit_beats=4.0,
        rhythm_profile={0.5: 0.5, 1.0: 0.5},
        allow_variation=True,
        variation_prob=0.3
    )
    assert spec2.repeat_unit_beats == 4.0
    assert spec2.rhythm_profile == {0.5: 0.5, 1.0: 0.5}
    assert spec2.allow_motif_variation
    assert spec2.variation_probability == 0.3
    
    print("✓ test_structure_spec_creation passed")


def test_self_similarity_metric():
    """Test self-similarity measurement for repeating patterns."""
    # Perfect repetition
    pitches = [60, 62, 64, 65, 60, 62, 64, 65]
    durations = [1.0] * 8
    similarity = measure_self_similarity(pitches, durations, 4.0)
    assert similarity > 0.9, f"Perfect repetition should score high, got {similarity}"
    
    # No repetition
    pitches2 = [60, 61, 62, 63, 64, 65, 66, 67]
    similarity2 = measure_self_similarity(pitches2, durations, 4.0)
    assert similarity2 < 0.3, f"No repetition should score low, got {similarity2}"
    
    print(f"✓ test_self_similarity_metric passed (perfect={similarity:.2f}, random={similarity2:.2f})")


def test_rhythm_profile_alignment():
    """Test rhythm profile alignment measurement."""
    # Perfect match
    durations = [0.5, 0.5, 1.0, 1.0]
    target = {0.5: 0.5, 1.0: 0.5}
    alignment = measure_rhythm_profile_alignment(durations, target)
    assert alignment > 0.9, f"Perfect match should score high, got {alignment}"
    
    # Complete mismatch
    durations2 = [2.0, 2.0]
    alignment2 = measure_rhythm_profile_alignment(durations2, target)
    assert alignment2 < 0.6, f"Mismatch should score lower, got {alignment2}"
    
    print(f"✓ test_rhythm_profile_alignment passed (match={alignment:.2f}, mismatch={alignment2:.2f})")


def test_motif_repetition_application():
    """Test applying motif repetition to sequences."""
    import random
    rng = random.Random(42)
    
    # Original sequence
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    durations = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    
    # Apply repetition without variation
    new_pitches, new_durations = apply_motif_repetition(
        pitches, durations, repeat_unit_beats=2.0,
        allow_variation=False, rng=rng
    )
    
    # Check that first 4 notes repeat
    assert len(new_pitches) == len(pitches)
    assert new_pitches[:4] == new_pitches[4:8], "Motif should repeat exactly"
    
    # Apply with variation
    new_pitches_var, _ = apply_motif_repetition(
        pitches, durations, repeat_unit_beats=2.0,
        allow_variation=True, variation_probability=1.0, rng=rng
    )
    
    # First occurrence should match original, second might vary
    assert new_pitches_var[:4] == pitches[:4], "First motif should match original"
    # Note: variation is probabilistic, so we can't assert it always differs
    
    print("✓ test_motif_repetition_application passed")


def test_random_generator_with_structure():
    """Test random generator with structure spec."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    
    # Without structure
    pitches1, durations1, stats1 = generate_random_melody(
        spec, 42, {'rest_probability': 0.1}, structure_spec=None
    )
    assert stats1["repeat_count"] == 0
    
    # With repeat structure
    structure_spec = create_structured_spec(
        repeat_unit_beats=4.0,
        allow_variation=False
    )
    pitches2, durations2, stats2 = generate_random_melody(
        spec, 42, {'rest_probability': 0.1}, structure_spec=structure_spec
    )
    assert stats2["repeat_count"] >= 1, "Should detect repeating units"
    
    print(f"✓ test_random_generator_with_structure passed (repeat_count={stats2['repeat_count']})")


def test_scored_generator_with_structure():
    """Test scored generator with structure spec and structural scoring."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    
    structure_spec = create_structured_spec(
        repeat_unit_beats=4.0,
        rhythm_profile={0.5: 0.5, 1.0: 0.5},
        allow_variation=True,
        variation_prob=0.3
    )
    
    pitches, durations, score, stats = generate_scored_melody(
        spec, 42,
        {'rest_probability': 0.1, 'candidate_count': 5},
        structure_spec=structure_spec
    )
    
    assert len(pitches) > 0
    assert score > 0
    assert "repeat_count" in stats
    assert "actual_duration_distribution" in stats
    
    # Verify scoring includes structural metrics
    sounding = [p for p in pitches if p > 0]
    _, metrics = aggregate_melody_score(sounding, durations, structure_spec=structure_spec)
    
    assert "self_similarity" in metrics, "Should include self-similarity metric"
    assert "rhythm_alignment" in metrics, "Should include rhythm alignment metric"
    
    print(f"✓ test_scored_generator_with_structure passed (score={score:.3f})")


def test_markov_generator_with_structure():
    """Test markov generator with structure spec."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    
    structure_spec = create_structured_spec(
        repeat_unit_beats=4.0,
        rhythm_profile={0.5: 0.4, 1.0: 0.6}
    )
    
    pitches, durations, stats = generate_markov_melody(
        spec, 42,
        {'ngram_order': 2},
        structure_spec=structure_spec
    )
    
    assert len(pitches) > 0
    assert stats["repeat_count"] >= 1
    assert "actual_duration_distribution" in stats
    
    # Check rhythm profile influence
    dist = stats["actual_duration_distribution"]
    # Should have more 1.0 than 0.5 based on profile
    if 0.5 in dist and 1.0 in dist:
        # Profile says 60% quarters, 40% eighths
        # Actual might not match perfectly but should be influenced
        print(f"  Rhythm distribution: {dist}")
    
    print(f"✓ test_markov_generator_with_structure passed")


def test_duration_distribution_calculation():
    """Test duration distribution calculation."""
    durations = [0.5, 0.5, 0.5, 1.0, 1.0, 2.0]
    dist = compute_duration_distribution(durations)
    
    assert abs(dist[0.5] - 0.5) < 0.01, "50% should be 0.5"
    assert abs(dist[1.0] - 0.333) < 0.01, "33% should be 1.0"
    assert abs(dist[2.0] - 0.167) < 0.01, "17% should be 2.0"
    
    print(f"✓ test_duration_distribution_calculation passed")


def test_repeat_count_calculation():
    """Test repeat count calculation."""
    pitches = [60, 62, 64, 65] * 3  # 3 repeats of 4-note pattern
    durations = [1.0] * 12
    
    count = calculate_repeat_count(pitches, durations, 4.0)
    assert count == 3, f"Expected 3 repeats, got {count}"
    
    count2 = calculate_repeat_count(pitches, durations, 2.0)
    assert count2 == 6, f"Expected 6 two-beat units, got {count2}"
    
    print("✓ test_repeat_count_calculation passed")


if __name__ == "__main__":
    print("Running structure specification tests...\n")
    
    test_structure_spec_creation()
    test_self_similarity_metric()
    test_rhythm_profile_alignment()
    test_motif_repetition_application()
    test_random_generator_with_structure()
    test_scored_generator_with_structure()
    test_markov_generator_with_structure()
    test_duration_distribution_calculation()
    test_repeat_count_calculation()
    
    print("\n" + "=" * 60)
    print("All structure specification tests passed!")
    print("=" * 60)

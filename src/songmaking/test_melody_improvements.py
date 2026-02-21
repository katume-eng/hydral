"""
Tests for melody fragment generation improvements.
Tests discrete durations, grid snapping, scale constraints, and debug stats.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from songmaking.harmony import choose_harmony
from songmaking.generators.random import generate_random_melody
from songmaking.generators.scored import generate_scored_melody
from songmaking.generators.markov import generate_markov_melody
from songmaking.note_utils import (
    DISCRETE_DURATIONS,
    DURATION_VALUES,
    GRID_RESOLUTION,
    build_scale_pitch_set,
    is_pitch_in_scale
)


def test_discrete_durations_random():
    """Test that random generator only uses discrete note durations."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_random_melody(spec, 42, {'rest_probability': 0.1})
    
    valid_durations = set(DURATION_VALUES)
    
    for dur in durations:
        # Check if duration matches one of the discrete values (with small tolerance)
        assert any(abs(dur - vd) < 0.001 for vd in valid_durations), \
            f"Duration {dur} is not a valid discrete value"
    
    print(f"✓ test_discrete_durations_random passed ({len(durations)} durations checked)")


def test_discrete_durations_scored():
    """Test that scored generator only uses discrete note durations."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, score, debug_stats = generate_scored_melody(
        spec, 42, {'rest_probability': 0.1, 'candidate_count': 5}
    )
    
    valid_durations = set(DURATION_VALUES)
    
    for dur in durations:
        assert any(abs(dur - vd) < 0.001 for vd in valid_durations), \
            f"Duration {dur} is not a valid discrete value"
    
    print(f"✓ test_discrete_durations_scored passed ({len(durations)} durations checked)")


def test_discrete_durations_markov():
    """Test that markov generator only uses discrete note durations."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_markov_melody(
        spec, 42, {'rest_probability': 0.1, 'ngram_order': 2}
    )
    
    valid_durations = set(DURATION_VALUES)
    
    for dur in durations:
        assert any(abs(dur - vd) < 0.001 for vd in valid_durations), \
            f"Duration {dur} is not a valid discrete value"
    
    print(f"✓ test_discrete_durations_markov passed ({len(durations)} durations checked)")


def test_total_duration_constraint():
    """Test that total duration does not exceed bars * beats_per_bar."""
    spec = choose_harmony(100, {'bars': 4, 'min_bpm': 120, 'max_bpm': 120})
    
    for method_fn in [generate_random_melody, generate_markov_melody]:
        if method_fn == generate_markov_melody:
            pitches, durations, debug_stats = method_fn(spec, 100, {'ngram_order': 2})
        else:
            pitches, durations, debug_stats = method_fn(spec, 100, {'rest_probability': 0.1})
        
        total_beats = sum(durations)
        max_beats = spec.total_measures * 4  # 4/4 time
        
        assert total_beats <= max_beats + 0.01, \
            f"Total duration {total_beats} exceeds max {max_beats}"
    
    print("✓ test_total_duration_constraint passed")


def test_scale_constraint_random():
    """Test that random generator only uses pitches from scale."""
    spec = choose_harmony(123, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_random_melody(spec, 123, {'rest_probability': 0.1})
    
    scale_pitches = build_scale_pitch_set(
        spec.tonic_note,
        spec.scale_pattern,
        spec.lowest_midi,
        spec.highest_midi
    )
    
    violations = 0
    for pitch in pitches:
        if pitch > 0 and not is_pitch_in_scale(pitch, scale_pitches):
            violations += 1
    
    assert violations == 0, f"Found {violations} out-of-scale pitches"
    
    print(f"✓ test_scale_constraint_random passed (checked {len([p for p in pitches if p > 0])} pitches)")


def test_scale_constraint_markov():
    """Test that markov generator quantizes to scale pitches."""
    spec = choose_harmony(456, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_markov_melody(spec, 456, {'ngram_order': 2})
    
    scale_pitches = build_scale_pitch_set(
        spec.tonic_note,
        spec.scale_pattern,
        spec.lowest_midi,
        spec.highest_midi
    )
    
    violations = 0
    for pitch in pitches:
        if pitch > 0 and not is_pitch_in_scale(pitch, scale_pitches):
            violations += 1
    
    assert violations == 0, f"Found {violations} out-of-scale pitches"
    
    print(f"✓ test_scale_constraint_markov passed")


def test_pitch_range_constraint():
    """Test that all pitches respect min/max MIDI range."""
    spec = choose_harmony(789, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_random_melody(spec, 789, {'rest_probability': 0.1})
    
    for pitch in pitches:
        if pitch > 0:  # Skip rests
            assert spec.lowest_midi <= pitch <= spec.highest_midi, \
                f"Pitch {pitch} outside range [{spec.lowest_midi}, {spec.highest_midi}]"
    
    print("✓ test_pitch_range_constraint passed")


def test_debug_stats_random():
    """Test that random generator returns debug stats."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_random_melody(spec, 42, {'rest_probability': 0.1})
    
    assert "duration_distribution" in debug_stats
    assert "scale_out_rejections" in debug_stats
    assert "octave_up_events" in debug_stats
    assert "total_beats" in debug_stats
    
    # Check that duration distribution sums to number of notes
    total_in_dist = sum(debug_stats["duration_distribution"].values())
    assert total_in_dist == len(durations), \
        f"Duration distribution count {total_in_dist} != note count {len(durations)}"
    
    # Check that total_beats matches sum of durations
    assert abs(debug_stats["total_beats"] - sum(durations)) < 0.01, \
        f"Debug total_beats {debug_stats['total_beats']} != actual {sum(durations)}"
    
    print("✓ test_debug_stats_random passed")


def test_debug_stats_scored():
    """Test that scored generator returns debug stats."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, score, debug_stats = generate_scored_melody(
        spec, 42, {'rest_probability': 0.1, 'candidate_count': 5}
    )
    
    assert "duration_distribution" in debug_stats
    assert "scale_out_rejections" in debug_stats
    assert "octave_up_events" in debug_stats
    assert "total_beats" in debug_stats
    
    print("✓ test_debug_stats_scored passed")


def test_debug_stats_markov():
    """Test that markov generator returns debug stats."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_markov_melody(spec, 42, {'ngram_order': 2})
    
    assert "duration_distribution" in debug_stats
    assert "scale_out_rejections" in debug_stats
    assert "octave_up_events" in debug_stats
    assert "total_beats" in debug_stats
    
    print("✓ test_debug_stats_markov passed")


def test_octave_up_events_tracked():
    """Test that octave-up events are tracked in debug stats."""
    spec = choose_harmony(999, {'bars': 4, 'min_bpm': 120, 'max_bpm': 120})
    
    # Set high octave-up chance to ensure some events
    config = {'rest_probability': 0.05, 'octave_up_chance': 0.1}
    
    total_octave_ups = 0
    for seed in range(10):
        pitches, durations, debug_stats = generate_random_melody(spec, 999 + seed, config)
        total_octave_ups += debug_stats.get("octave_up_events", 0)
    
    # With 10% chance and multiple seeds, should get at least some octave-ups
    print(f"  Total octave-up events across 10 generations: {total_octave_ups}")
    
    # Assert we got at least one octave-up event (statistically very likely with 10% chance)
    assert total_octave_ups > 0, \
        f"Expected at least one octave-up event with 10% chance across 10 generations, got {total_octave_ups}"
    
    print("✓ test_octave_up_events_tracked passed")


def test_duration_distribution_validity():
    """Test that duration distribution in debug stats is valid."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_random_melody(spec, 42, {'rest_probability': 0.1})
    
    dist = debug_stats["duration_distribution"]
    
    # All keys should be valid duration values
    valid_durations = set(DURATION_VALUES)
    
    for key_str, count in dist.items():
        dur_value = float(key_str)
        assert any(abs(dur_value - vd) < 0.001 for vd in valid_durations), \
            f"Invalid duration {dur_value} in distribution"
        assert count > 0, f"Duration {key_str} has non-positive count {count}"
    
    print("✓ test_duration_distribution_validity passed")


if __name__ == "__main__":
    print("Running melody improvement tests...\n")
    
    test_discrete_durations_random()
    test_discrete_durations_scored()
    test_discrete_durations_markov()
    test_total_duration_constraint()
    test_scale_constraint_random()
    test_scale_constraint_markov()
    test_pitch_range_constraint()
    test_debug_stats_random()
    test_debug_stats_scored()
    test_debug_stats_markov()
    test_octave_up_events_tracked()
    test_duration_distribution_validity()
    
    print("\n" + "=" * 60)
    print("All melody improvement tests passed! ✓")
    print("=" * 60)

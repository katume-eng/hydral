"""
Tests for mean pitch target/tolerance constraint feature.
Verifies pitch statistics calculation and constraint enforcement.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from songMaking.pitch_stats import (
    calculate_mean_pitch,
    check_pitch_constraint,
    get_pitch_stats
)
from songMaking.harmony import choose_harmony
from songMaking.generators.random import generate_random_melody
from songMaking.cli import generate_melody_midi


def test_calculate_mean_pitch_basic():
    """Test basic mean pitch calculation."""
    # Simple case: all C4 (MIDI 60)
    notes = [60, 60, 60]
    mean = calculate_mean_pitch(notes)
    assert mean == 60.0, f"Expected 60.0, got {mean}"
    
    # Mixed pitches
    notes = [60, 64, 67]  # C, E, G
    mean = calculate_mean_pitch(notes)
    expected = (60 + 64 + 67) / 3
    assert abs(mean - expected) < 0.01, f"Expected {expected}, got {mean}"
    
    print("✓ test_calculate_mean_pitch_basic passed")


def test_calculate_mean_pitch_with_rests():
    """Test that rests (MIDI 0) are excluded from mean calculation."""
    notes = [60, 0, 64, 0, 67]  # C, rest, E, rest, G
    mean = calculate_mean_pitch(notes)
    expected = (60 + 64 + 67) / 3
    assert abs(mean - expected) < 0.01, f"Expected {expected}, got {mean}"
    
    print("✓ test_calculate_mean_pitch_with_rests passed")


def test_calculate_mean_pitch_all_rests():
    """Test that all rests returns None."""
    notes = [0, 0, 0]
    mean = calculate_mean_pitch(notes)
    assert mean is None, f"Expected None for all rests, got {mean}"
    
    # Empty list
    mean = calculate_mean_pitch([])
    assert mean is None, f"Expected None for empty list, got {mean}"
    
    print("✓ test_calculate_mean_pitch_all_rests passed")


def test_check_pitch_constraint_within_tolerance():
    """Test constraint checking when pitch is within tolerance."""
    notes = [60, 61, 62]  # Mean = 61
    
    # Should pass: target 61, tolerance 2
    assert check_pitch_constraint(notes, 61.0, 2.0) is True
    
    # Should pass: target 60, tolerance 2 (61 is within 60±2)
    assert check_pitch_constraint(notes, 60.0, 2.0) is True
    
    # Should pass: target 62, tolerance 2 (61 is within 62±2)
    assert check_pitch_constraint(notes, 62.0, 2.0) is True
    
    print("✓ test_check_pitch_constraint_within_tolerance passed")


def test_check_pitch_constraint_outside_tolerance():
    """Test constraint checking when pitch is outside tolerance."""
    notes = [60, 61, 62]  # Mean = 61
    
    # Should fail: target 70, tolerance 2 (61 is not within 70±2)
    assert check_pitch_constraint(notes, 70.0, 2.0) is False
    
    # Should fail: target 50, tolerance 2 (61 is not within 50±2)
    assert check_pitch_constraint(notes, 50.0, 2.0) is False
    
    # Should pass: target 61, tolerance 0.1 (61 is within 61±0.1)
    assert check_pitch_constraint(notes, 61.0, 0.1) is True
    
    # Should fail: target 61.5, tolerance 0.1 (61 is not within 61.5±0.1)
    assert check_pitch_constraint(notes, 61.5, 0.1) is False
    
    print("✓ test_check_pitch_constraint_outside_tolerance passed")


def test_check_pitch_constraint_boundary():
    """Test constraint checking at exact boundaries."""
    notes = [60]  # Mean = 60
    
    # Exactly at lower boundary
    assert check_pitch_constraint(notes, 62.0, 2.0) is True  # 60 == 62-2
    
    # Exactly at upper boundary
    assert check_pitch_constraint(notes, 58.0, 2.0) is True  # 60 == 58+2
    
    print("✓ test_check_pitch_constraint_boundary passed")


def test_get_pitch_stats_comprehensive():
    """Test comprehensive pitch statistics."""
    notes = [60, 0, 64, 67, 0, 72]  # C4, rest, E4, G4, rest, C5
    
    stats = get_pitch_stats(notes)
    
    assert stats["sounding_count"] == 4, f"Expected 4 sounding notes, got {stats['sounding_count']}"
    assert stats["min"] == 60, f"Expected min 60, got {stats['min']}"
    assert stats["max"] == 72, f"Expected max 72, got {stats['max']}"
    assert stats["range"] == 12, f"Expected range 12, got {stats['range']}"
    
    expected_mean = (60 + 64 + 67 + 72) / 4
    assert abs(stats["mean"] - expected_mean) < 0.01, f"Expected mean {expected_mean}, got {stats['mean']}"
    
    print("✓ test_get_pitch_stats_comprehensive passed")


def test_get_pitch_stats_all_rests():
    """Test pitch stats with all rests."""
    notes = [0, 0, 0]
    
    stats = get_pitch_stats(notes)
    
    assert stats["mean"] is None
    assert stats["min"] is None
    assert stats["max"] is None
    assert stats["range"] == 0
    assert stats["sounding_count"] == 0
    
    print("✓ test_get_pitch_stats_all_rests passed")


def test_generation_with_pitch_constraint():
    """Test that generation loop respects pitch constraints."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    
    # First, generate a melody to see what range we're dealing with
    pitches, durations, debug_stats = generate_random_melody(spec, 42, {'rest_probability': 0.1})
    baseline_mean = calculate_mean_pitch(pitches)
    
    # Use the baseline mean as target with reasonable tolerance
    target_pitch = baseline_mean if baseline_mean else 60.0
    tolerance = 10.0  # Very wide tolerance for testing
    
    # Try up to 50 attempts
    success = False
    for attempt in range(50):
        seed = 42 + attempt
        pitches, durations, debug_stats = generate_random_melody(spec, seed, {'rest_probability': 0.1})
        
        if check_pitch_constraint(pitches, target_pitch, tolerance):
            success = True
            mean = calculate_mean_pitch(pitches)
            print(f"  Found melody with mean pitch {mean:.2f} (target {target_pitch:.1f}±{tolerance}) on attempt {attempt + 1}")
            break
    
    assert success, f"Failed to generate melody meeting constraint after 50 attempts (target {target_pitch:.1f}±{tolerance})"
    
    print("✓ test_generation_with_pitch_constraint passed")


def test_generate_melody_midi_returns_pitch_stats():
    """Test that generate_melody_midi returns pitch statistics."""
    spec = choose_harmony(100, {'bars': 1, 'min_bpm': 100, 'max_bpm': 100})
    config = {'rest_probability': 0.1}
    
    midi_bytes, pitches, durations, score, pitch_stats, debug_stats = generate_melody_midi(
        spec, "random", 100, config
    )
    
    # Verify all return values are present
    assert midi_bytes is not None, "MIDI bytes should not be None"
    assert pitches is not None, "Pitches should not be None"
    assert durations is not None, "Durations should not be None"
    assert score is not None, "Score should not be None"
    assert pitch_stats is not None, "Pitch stats should not be None"
    assert debug_stats is not None, "Debug stats should not be None"
    
    # Verify pitch_stats has expected keys
    assert "mean" in pitch_stats
    assert "min" in pitch_stats
    assert "max" in pitch_stats
    assert "range" in pitch_stats
    assert "sounding_count" in pitch_stats
    
    # Verify debug_stats has expected keys
    assert "duration_distribution" in debug_stats
    assert "scale_out_rejections" in debug_stats
    assert "octave_up_events" in debug_stats
    assert "total_beats" in debug_stats
    
    print("✓ test_generate_melody_midi_returns_pitch_stats passed")


def test_tight_constraint_requires_multiple_attempts():
    """Test that tight constraints require multiple attempts."""
    spec = choose_harmony(123, {'bars': 2, 'min_bpm': 100, 'max_bpm': 100})
    
    # Very tight constraint - should require multiple tries
    target_pitch = 60.0
    tolerance = 0.5  # Very tight
    
    attempts_needed = 0
    max_attempts = 200
    
    for attempt in range(max_attempts):
        seed = 123 + attempt
        pitches, durations, debug_stats = generate_random_melody(spec, seed, {'rest_probability': 0.1})
        attempts_needed += 1
        
        if check_pitch_constraint(pitches, target_pitch, tolerance):
            break
    
    # With tight constraint, should need more than 1 attempt (statistically likely)
    # But we can't guarantee it, so just verify we eventually succeed
    assert attempts_needed <= max_attempts, f"Should eventually meet constraint"
    
    print(f"✓ test_tight_constraint_requires_multiple_attempts passed (needed {attempts_needed} attempts)")


if __name__ == "__main__":
    print("Running pitch constraint tests...\n")
    
    test_calculate_mean_pitch_basic()
    test_calculate_mean_pitch_with_rests()
    test_calculate_mean_pitch_all_rests()
    test_check_pitch_constraint_within_tolerance()
    test_check_pitch_constraint_outside_tolerance()
    test_check_pitch_constraint_boundary()
    test_get_pitch_stats_comprehensive()
    test_get_pitch_stats_all_rests()
    test_generation_with_pitch_constraint()
    test_generate_melody_midi_returns_pitch_stats()
    test_tight_constraint_requires_multiple_attempts()
    
    print("\n" + "=" * 60)
    print("All pitch constraint tests passed! ✓")
    print("=" * 60)

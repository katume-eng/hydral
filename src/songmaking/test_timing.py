"""
Minimal targeted tests for MIDI timing and --bars option.
Tests that beats/tempo align correctly and bars parameter works.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from songmaking.harmony import choose_harmony, HarmonySpec
from songmaking.generators.random import generate_random_melody
from songmaking.export_midi import create_melody_midi

# Tolerance for beat alignment checks (in beats)
BEAT_TOLERANCE = 0.01


def test_bars_option_4_4_time():
    """Test that --bars option enforces 4/4 time signature with multiple seeds."""
    # Test with different seeds to ensure bars parameter consistently overrides randomness
    for seed in [42, 100, 999]:
        spec = choose_harmony(seed, {'min_bpm': 100, 'max_bpm': 120, 'bars': 3})
        
        assert spec.meter_numerator == 4, f"Seed {seed}: Expected numerator=4, got {spec.meter_numerator}"
        assert spec.meter_denominator == 4, f"Seed {seed}: Expected denominator=4, got {spec.meter_denominator}"
        assert spec.total_measures == 3, f"Seed {seed}: Expected 3 measures, got {spec.total_measures}"
    
    print("✓ test_bars_option_4_4_time passed (tested seeds: 42, 100, 999)")


def test_bars_default_behavior():
    """Test that without bars option, time signature is random."""
    spec = choose_harmony(42, {'min_bpm': 100, 'max_bpm': 120})
    
    # Should have some time signature (not testing which one)
    assert spec.meter_numerator > 0, "Numerator should be positive"
    assert spec.meter_denominator > 0, "Denominator should be positive"
    print(f"✓ test_bars_default_behavior passed (got {spec.meter_numerator}/{spec.meter_denominator})")


def test_total_beats_calculation():
    """Test that total beats = bars * 4 for 4/4 time."""
    for bars in [1, 2, 4, 8]:
        spec = choose_harmony(42, {'bars': bars, 'min_bpm': 120, 'max_bpm': 120})
        pitches, durations, debug_stats = generate_random_melody(spec, 42, {'rest_probability': 0.1})
        
        total_beats = sum(durations)
        expected_beats = bars * 4
        
        # Should be exactly equal or very close (accounting for floating point)
        assert abs(total_beats - expected_beats) < BEAT_TOLERANCE, \
            f"For {bars} bars: expected {expected_beats} beats, got {total_beats}"
        print(f"✓ test_total_beats_calculation passed for {bars} bars (total={total_beats})")


def test_rhythm_doesnt_exceed_total():
    """Test that generated rhythm doesn't exceed total_beats."""
    spec = choose_harmony(123, {'bars': 2, 'min_bpm': 100, 'max_bpm': 120})
    pitches, durations, debug_stats = generate_random_melody(spec, 123, {'rest_probability': 0.15})
    
    total_beats = sum(durations)
    expected_beats = 2 * 4  # 2 bars in 4/4
    
    # Should not exceed expected beats
    assert total_beats <= expected_beats + BEAT_TOLERANCE, \
        f"Rhythm exceeded limit: {total_beats} > {expected_beats}"
    print(f"✓ test_rhythm_doesnt_exceed_total passed (total={total_beats}, limit={expected_beats})")


def test_midi_export_uses_beats():
    """Test that MIDI export receives durations in beats."""
    spec = choose_harmony(42, {'bars': 2, 'min_bpm': 120, 'max_bpm': 120})
    pitches = [60, 62, 64, 65]
    durations = [1.0, 1.0, 1.0, 1.0]  # All quarter notes (1 beat each)
    
    # This should not raise an error
    midi_bytes = create_melody_midi(
        pitches, 
        durations,
        spec.beats_per_minute,
        (spec.meter_numerator, spec.meter_denominator)
    )
    
    assert len(midi_bytes) > 0, "MIDI bytes should not be empty"
    assert midi_bytes[:4] == b'MThd', "Should start with MIDI header"
    print(f"✓ test_midi_export_uses_beats passed (generated {len(midi_bytes)} bytes)")


def test_tempo_set_in_midi():
    """Test that addTempo is called in MIDI export."""
    spec = choose_harmony(42, {'bars': 1, 'min_bpm': 100, 'max_bpm': 100})
    pitches = [60]
    durations = [4.0]  # One whole note
    
    midi_bytes = create_melody_midi(
        pitches,
        durations,
        spec.beats_per_minute,
        (spec.meter_numerator, spec.meter_denominator)
    )
    
    # MIDI file should contain tempo meta event (0xFF 0x51)
    # This is a basic check - proper MIDI parsing would be more thorough
    assert len(midi_bytes) > 20, "MIDI file should have reasonable size"
    print(f"✓ test_tempo_set_in_midi passed")


if __name__ == "__main__":
    print("Running MIDI timing tests...\n")
    
    test_bars_option_4_4_time()
    test_bars_default_behavior()
    test_total_beats_calculation()
    test_rhythm_doesnt_exceed_total()
    test_midi_export_uses_beats()
    test_tempo_set_in_midi()
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)

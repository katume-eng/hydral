"""
Tests for concatenated fragment metadata.
Ensures note_count is included in JSON output.
"""
import json
import os
import sys
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pretty_midi

from songmaking.export import concat_fragments


def _stub_generate_melody_midi(harmony_spec, method, seed, generation_config):
    pm = pretty_midi.PrettyMIDI(initial_tempo=harmony_spec.beats_per_minute)
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
    instrument.notes.append(pretty_midi.Note(velocity=100, pitch=62, start=0.5, end=1.0))
    pm.instruments.append(instrument)

    with tempfile.NamedTemporaryFile(suffix=".mid") as tmp_midi:
        pm.write(tmp_midi.name)
        tmp_midi.seek(0)
        midi_bytes = tmp_midi.read()

    pitches = [60, 62]
    durations = [0.5, 0.5]
    score = 0.0
    pitch_stats = {"mean": 61.0, "min": 60, "max": 62, "range": 2, "sounding_count": 2}
    debug_stats = {}
    enhanced_pitch_stats = {
        "avg_pitch": 61.0,
        "note_count": 2,
        "pitch_min": 60,
        "pitch_max": 62,
        "pitch_range": 2,
        "pitch_std": 0.0
    }

    return midi_bytes, pitches, durations, score, pitch_stats, debug_stats, enhanced_pitch_stats


def test_fragment_metadata_includes_note_count():
    """Test that fragment metadata includes note_count."""
    original_generate = concat_fragments.generate_melody_midi
    concat_fragments.generate_melody_midi = _stub_generate_melody_midi

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "concat_test")
            concat_fragments.export_concatenated_fragments(
                out_path=out_path,
                harmony="auto",
                method="random",
                seed=42,
                config={"max_attempts": 1},
                n_fragments=1,
                bars=1,
                gap_beats=0.0
            )

            with open(f"{out_path}.json", "r") as f:
                metadata = json.load(f)

            fragment = metadata["fragments"][0]
            assert fragment["note_count"] == 2, f"Expected note_count 2, got {fragment['note_count']}"
            assert abs(fragment["mean_interval"] - 2.0) < 0.01, \
                f"Expected mean_interval 2.0, got {fragment['mean_interval']}"

        print("✓ test_fragment_metadata_includes_note_count passed")
    finally:
        concat_fragments.generate_melody_midi = original_generate


if __name__ == "__main__":
    print("Running concatenated fragment metadata tests...\n")
    test_fragment_metadata_includes_note_count()
    print("\n" + "=" * 60)
    print("All concatenated fragment metadata tests passed! ✓")
    print("=" * 60)

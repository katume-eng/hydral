"""
MIDI export functionality for generated melodies.
Converts pitch/duration sequences to MIDI file format.
"""
from midiutil import MIDIFile
from io import BytesIO
from typing import List, Tuple
import logging

# Configure logging for debug output
logger = logging.getLogger(__name__)


def create_melody_midi(
    pitches: List[int],
    durations: List[float],
    tempo_bpm: int,
    time_signature: Tuple[int, int]
) -> bytes:
    """
    Convert melody sequence to MIDI file bytes.
    
    Args:
        pitches: MIDI note numbers (0 = rest)
        durations: Note lengths in quarter-note beats
        tempo_bpm: Tempo in beats per minute
        time_signature: (numerator, denominator) tuple
    
    Returns:
        MIDI file as bytes
    """
    # Calculate timing metrics
    total_beats = sum(durations)
    beats_per_bar = time_signature[0] * (4.0 / time_signature[1])
    total_seconds_expected = (total_beats / tempo_bpm) * 60.0
    
    # Find end beat of last sounding note
    current_beat = 0.0
    last_note_end_beat = 0.0
    for pitch, duration in zip(pitches, durations):
        if pitch > 0:  # Only count sounding notes
            last_note_end_beat = current_beat + duration
        current_beat += duration
    
    # Check if rhythm aligns with expected total
    near_total_beats = abs(total_beats - round(total_beats / beats_per_bar) * beats_per_bar) < 0.01
    
    # Debug logging before export
    logger.info("=" * 60)
    logger.info("MIDI Export Debug Information")
    logger.info("=" * 60)
    logger.info(f"Tempo: {tempo_bpm} BPM")
    logger.info(f"Time signature: {time_signature[0]}/{time_signature[1]}")
    logger.info(f"Beats per bar: {beats_per_bar}")
    logger.info(f"Total beats: {total_beats}")
    logger.info(f"Total bars: {total_beats / beats_per_bar:.2f}")
    logger.info(f"Total duration (seconds): {total_seconds_expected:.2f}s")
    logger.info(f"Last note ends at beat: {last_note_end_beat}")
    logger.info(f"Rhythm aligned to bar boundaries: {'YES' if near_total_beats else 'NO'}")
    logger.info(f"Number of notes (including rests): {len(pitches)}")
    logger.info(f"Number of sounding notes: {sum(1 for p in pitches if p > 0)}")
    logger.info("=" * 60)
    
    midi_obj = MIDIFile(1)  # one track
    
    track_num = 0
    channel_num = 0
    starting_time = 0.0
    
    # Set tempo and time signature
    # addTempo expects: track, time (in beats), tempo (BPM)
    midi_obj.addTempo(track_num, starting_time, tempo_bpm)
    midi_obj.addTimeSignature(
        track_num,
        starting_time,
        time_signature[0],
        time_signature[1],
        24,  # MIDI clocks per tick
        8    # 32nd notes per quarter
    )
    
    # Add notes
    current_time = 0.0
    default_velocity = 80
    
    for pitch, duration in zip(pitches, durations):
        if pitch > 0:  # 0 = rest
            # addNote expects: track, channel, pitch, time (in beats), duration (in beats), velocity
            midi_obj.addNote(
                track_num,
                channel_num,
                pitch,
                current_time,
                duration,
                default_velocity
            )
        
        current_time += duration
    
    # Write to bytes
    output_buffer = BytesIO()
    midi_obj.writeFile(output_buffer)
    output_buffer.seek(0)
    
    return output_buffer.read()


def save_midi_file(midi_bytes: bytes, filepath: str) -> None:
    """Write MIDI bytes to file."""
    with open(filepath, 'wb') as f:
        f.write(midi_bytes)

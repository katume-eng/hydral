"""
MIDI export functionality for generated melodies.
Converts pitch/duration sequences to MIDI file format.
"""
from midiutil import MIDIFile
from io import BytesIO
from typing import List, Tuple


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
    midi_obj = MIDIFile(1)  # one track
    
    track_num = 0
    channel_num = 0
    starting_time = 0.0
    
    # Set tempo and time signature
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

"""
Pitch statistics utilities for analyzing and constraining melodies.
Calculates mean pitch and checks against target/tolerance constraints.
"""
from typing import List, Optional, Dict, Any
import math


def calculate_mean_pitch(midi_notes: List[int]) -> Optional[float]:
    """
    Calculate the mean MIDI pitch of sounding notes.
    
    Args:
        midi_notes: List of MIDI pitch values (0 indicates rest)
    
    Returns:
        Mean pitch as float, or None if no sounding notes
    """
    sounding_notes = [p for p in midi_notes if p > 0]
    
    if not sounding_notes:
        return None
    
    return sum(sounding_notes) / len(sounding_notes)


def check_pitch_constraint(
    midi_notes: List[int],
    target_pitch: float,
    tolerance: float
) -> bool:
    """
    Check if melody's mean pitch falls within target ± tolerance.
    
    Args:
        midi_notes: List of MIDI pitch values
        target_pitch: Target mean pitch (MIDI value)
        tolerance: Allowed deviation in semitones
    
    Returns:
        True if mean pitch is within tolerance, False otherwise
    """
    mean_pitch = calculate_mean_pitch(midi_notes)
    
    if mean_pitch is None:
        return False
    
    lower_bound = target_pitch - tolerance
    upper_bound = target_pitch + tolerance
    
    return lower_bound <= mean_pitch <= upper_bound


def compute_pitch_stats(notes: List[int]) -> Dict[str, Any]:
    """
    Compute comprehensive pitch statistics for MIDI notes.
    
    Args:
        notes: List of MIDI pitch values (0 indicates rest)
    
    Returns:
        Dictionary with pitch statistics:
        - avg_pitch: Average pitch of sounding notes (None if no sounding notes)
        - note_count: Total number of notes (including rests)
        - pitch_min: Lowest pitch (None if no sounding notes)
        - pitch_max: Highest pitch (None if no sounding notes)
        - pitch_std: Standard deviation of pitches (None if no sounding notes)
    """
    sounding_notes = [p for p in notes if p > 0]
    
    if not sounding_notes:
        return {
            "avg_pitch": None,
            "note_count": len(notes),
            "pitch_min": None,
            "pitch_max": None,
            "pitch_std": None
        }
    
    # Calculate mean
    mean_pitch = sum(sounding_notes) / len(sounding_notes)
    
    # Calculate standard deviation
    if len(sounding_notes) > 1:
        variance = sum((p - mean_pitch) ** 2 for p in sounding_notes) / len(sounding_notes)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0
    
    return {
        "avg_pitch": mean_pitch,
        "note_count": len(notes),
        "pitch_min": min(sounding_notes),
        "pitch_max": max(sounding_notes),
        "pitch_std": std_dev
    }


def get_pitch_stats(midi_notes: List[int]) -> dict:
    """
    Calculate comprehensive pitch statistics for a melody.
    
    Args:
        midi_notes: List of MIDI pitch values
    
    Returns:
        Dictionary with pitch statistics:
        - mean: Mean pitch of sounding notes
        - min: Lowest pitch
        - max: Highest pitch
        - range: Pitch range (max - min)
        - sounding_count: Number of non-rest notes
    """
    sounding_notes = [p for p in midi_notes if p > 0]
    
    if not sounding_notes:
        return {
            "mean": None,
            "min": None,
            "max": None,
            "range": 0,
            "sounding_count": 0
        }
    
    return {
        "mean": sum(sounding_notes) / len(sounding_notes),
        "min": min(sounding_notes),
        "max": max(sounding_notes),
        "range": max(sounding_notes) - min(sounding_notes),
        "sounding_count": len(sounding_notes)
    }

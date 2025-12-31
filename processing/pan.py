import random
from pydub import AudioSegment
import math

def extreme_pan(grains):
    return [
        g.pan(-0.8) if i % 2 == 0 else g.pan(0.8)
        for i, g in enumerate(grains)
    ]


def dynamics_pan(grains, cycles=8):
    N = len(grains)
    return [
        g.pan(math.sin(2 * math.pi * cycles * i / N)) if i % 2 == 0 else g.pan(-math.sin(2 * math.pi * cycles * i / N))
        for i, g in enumerate(grains)
    ]

def state_pan(grains):
    states = [-1.0, -0.5, 0.0, 0.5, 1.0]
    return [
        g.pan(states[i % len(states)])
        for i, g in enumerate(grains)
    ]

def random_state_pan(grains):
    states = [-1.0, -0.5, 0.0, 0.5, 1.0]
    return [
        g.pan(random.choice(states))
        for g in grains
    ]
# core/transform/other.py
import random

def shuffle(grains, seed=None):
    if seed is not None:
        random.seed(seed)
    random.shuffle(grains)
    return grains

def reverse_some(grains, prob=0.2):
    return [
        g.reverse() if random.random() < prob else g
        for g in grains
    ]
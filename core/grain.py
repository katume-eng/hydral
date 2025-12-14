def split_grains(audio, grain_ms):
    grains = []
    for start in range(0, len(audio), grain_ms):
        g = audio[start:start + grain_ms]
        if len(g) == grain_ms:
            grains.append(g)
    return grains

def concat(grains):
    out = grains[0]
    for g in grains[1:]:
        out += g
    return out

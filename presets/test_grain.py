# presets/test_grain.py
from pipeline import hydral_pipeline

seed = 42

def run():

    grain_lengths = [0.02, 0.04, 0.08, 0.15, 0.3]

    for gsec in grain_lengths:
        hydral_pipeline(
            input_wav="data/raw/recorded.wav",
            output_wav=f"/mnt/c/hydral/outputs/test_{gsec*1000}ms_6.wav",
            is_assemble=True,
            grain_sec=gsec,
            seed=seed,
            is_extreme_pan=True
        )

if __name__ == "__main__":
    run()
    print("Done")
"""Generate a random musical recipe (key, scale, progression, tempo)."""

import random


SCALE_TYPES = [
	"major: 全全半全全全半",
	"minor: 全半全全半全全",
	"dorian: 全半全全全半全",
	"mixolydian: 全全半全半全全",
	"phrygian: 半全全全半全全",
	"lydian: 全全全半全半全",
	"locrian: 半全全半全全全",
	"harmonic minor: 全半全全半全半半",
	"melodic minor: 全半全全全半半",
]

KEYS = [
	"C",
	"C#",
	"D",
	"D#",
	"E",
	"F",
	"F#",
	"G",
	"G#",
	"A",
	"A#",
	"B",
]

PROGRESSIONS = [
	"I - IV - V - I",
	"ii - V - I",
	"I - V - vi - IV",
	"vi - IV - I - V",
	"i - bVII - bVI - V",
	"I - vi - ii - V",
	"i - iv - v",
	"I - bVII - IV",
	"ii - iii - IV - V",
	"I - IV - I - V",
]


def pick_tempo(min_bpm: int = 70, max_bpm: int = 180) -> int:
	"""Pick a tempo within a comfortable band."""

	if min_bpm >= max_bpm:
		raise ValueError("min_bpm must be less than max_bpm")
	return random.randint(min_bpm, max_bpm)


def build_prompt() -> str:
	"""Assemble the random musical recipe as a printable string."""

	scale = random.choice(SCALE_TYPES)
	key = random.choice(KEYS)
	progression = random.choice(PROGRESSIONS)
	tempo = pick_tempo()

	return "\n".join(
		[
			"Your random music idea:",
			f"  Key: {key}",
			f"  Scale: {scale}",
			f"  Progression: {progression}",
			f"  Tempo: {tempo} BPM",
		]
	)


def main() -> None:
	print(build_prompt())


if __name__ == "__main__":
	main()

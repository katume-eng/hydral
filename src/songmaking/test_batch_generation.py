"""
バッチ生成の基本動作テスト。
"""
import json
import os
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

# インポート用に親ディレクトリを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from songmaking import cli


def test_resolve_batch_id_collision():
    """バッチIDの重複検知を確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir)
        existing_dir = output_root / "batch_2026-02-16-A"
        existing_dir.mkdir(parents=True)

        try:
            cli.resolve_batch_id(output_root, "2026-02-16-A")
            raise AssertionError("既存ディレクトリがある場合は例外が発生する想定です。")
        except FileExistsError:
            pass

    print("✓ test_resolve_batch_id_collision passed")


def test_generate_and_save_batch_metadata():
    """バッチIDがJSONに保存されることを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "batch_2026-02-16-A"
        args = Namespace(
            method="random",
            mean_pitch_target=None,
            mean_pitch_tolerance=2.0,
            max_attempts=5
        )

        harmony_config = {
            "min_bpm": 80,
            "max_bpm": 80,
            "bars": 1
        }
        generation_config = {
            "rest_probability": 0.15,
            "candidate_count": 5,
            "score_threshold": 0.3,
            "ngram_order": 2
        }

        midi_path, json_path = cli.generate_and_save(
            args,
            seed=123,
            harmony_config=harmony_config,
            generation_config=generation_config,
            structure_spec=None,
            output_path=output_path,
            batch_id="2026-02-16-A",
            batch_index=1
        )

        assert midi_path.exists()
        assert json_path.exists()

        with open(json_path, "r") as f:
            metadata = json.load(f)

        assert metadata["batch_id"] == "2026-02-16-A"
        assert metadata["seed"] == 123

    print("✓ test_generate_and_save_batch_metadata passed")


if __name__ == "__main__":
    print("Running batch generation tests...\n")
    test_resolve_batch_id_collision()
    test_generate_and_save_batch_metadata()
    print("\n============================================================")
    print("All batch generation tests passed! ✓")
    print("============================================================")

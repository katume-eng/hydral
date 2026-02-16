#!/usr/bin/env python3
"""
フォルダ配下の .wav ファイルを再帰的に走査し、未解析のものを解析して JSON を作成する

使用例:
    python processing/analyze_folder_wavs.py --root data/raw
    python processing/analyze_folder_wavs.py --root data/raw --dry-run
    python processing/analyze_folder_wavs.py --root data/raw --jobs 4
    python processing/analyze_folder_wavs.py --root data/raw --force

解析結果の JSON は各 WAV と同じ場所に作成されます:
    /a/b/c/foo.wav -> /a/b/c/foo.json

既に JSON が存在する場合はスキップされます (--force で上書き可能)
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# 既存の Hydral 解析パイプラインを使用
try:
    # スクリプトの親ディレクトリ（リポジトリルート）を sys.path に追加
    _repo_root = Path(__file__).parent.parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    
    from pipelines.analysis_pipelines import run_audio_analysis_pipeline
    HYDRAL_PIPELINE_AVAILABLE = True
except ImportError as e:
    HYDRAL_PIPELINE_AVAILABLE = False
    # 初期化時には警告しない（setup_logging 後に警告する）

# フォールバック用
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False


# グローバル変数（Ctrl+C 用）
interrupted = False


def signal_handler(signum, frame):
    """Ctrl+C ハンドラ"""
    global interrupted
    interrupted = True
    logging.warning("\n中断シグナルを受信しました。処理を終了します...")


@dataclass
class AnalysisResult:
    """解析結果を保持するデータクラス"""
    wav_path: Path
    json_path: Path
    success: bool
    error_message: Optional[str] = None
    skipped: bool = False


class WavAnalyzer:
    """WAV ファイル解析クラス"""

    def __init__(
        self,
        root: Path,
        ext: str = ".wav",
        force: bool = False,
        dry_run: bool = False,
        analysis_version: str = "v1"
    ):
        self.root = root
        self.ext = ext.lower()
        self.force = force
        self.dry_run = dry_run
        self.analysis_version = analysis_version
        self.logger = logging.getLogger(__name__)

    def find_wav_files(self) -> List[Path]:
        """再帰的に WAV ファイルを探す"""
        wav_files = []
        
        # 大文字小文字を区別しない拡張子検索
        for pattern in [f"*{self.ext}", f"*{self.ext.upper()}"]:
            wav_files.extend(self.root.rglob(pattern))
        
        # 重複を除去
        wav_files = list(set(wav_files))
        wav_files.sort()
        
        return wav_files

    def should_analyze(self, wav_path: Path) -> bool:
        """解析すべきかどうかを判定"""
        json_path = wav_path.with_suffix('.json')
        
        if self.force:
            return True
        
        return not json_path.exists()

    def analyze_with_hydral(self, wav_path: Path) -> Dict[str, Any]:
        """Hydral の既存パイプラインで解析"""
        features = run_audio_analysis_pipeline(wav_path)
        
        # numpy 配列を list に変換
        serializable_features = {}
        for key, value in features.items():
            if isinstance(value, np.ndarray):
                serializable_features[key] = value.tolist()
            elif isinstance(value, dict):
                # meta などの辞書も処理
                serializable_features[key] = {
                    k: v.tolist() if isinstance(v, np.ndarray) else v
                    for k, v in value.items()
                }
            else:
                serializable_features[key] = value
        
        return serializable_features

    def analyze_with_librosa(self, wav_path: Path) -> Dict[str, Any]:
        """フォールバック: librosa で基本的な特徴量を抽出"""
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa が利用できません")
        
        # 音声読み込み
        y, sr = librosa.load(wav_path, sr=None, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)
        
        # 基本的な特徴量
        rms = librosa.feature.rms(y=y, hop_length=512)[0]
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=512)[0]
        zcr = librosa.feature.zero_crossing_rate(y, hop_length=512)[0]
        
        features = {
            "rms": rms.tolist(),
            "spectral_centroid": spectral_centroid.tolist(),
            "zero_crossing_rate": zcr.tolist(),
            "meta": {
                "sample_rate": int(sr),
                "duration": float(duration),
                "num_frames": len(rms),
                "hop_length": 512,
            }
        }
        
        return features

    def analyze_wav(self, wav_path: Path) -> Dict[str, Any]:
        """WAV ファイルを解析してフィーチャーを抽出"""
        try:
            if HYDRAL_PIPELINE_AVAILABLE:
                self.logger.debug(f"Hydral パイプラインで解析: {wav_path}")
                features = self.analyze_with_hydral(wav_path)
            elif LIBROSA_AVAILABLE:
                self.logger.debug(f"librosa フォールバックで解析: {wav_path}")
                features = self.analyze_with_librosa(wav_path)
            else:
                raise RuntimeError("解析ライブラリが利用できません")
            
            return features
        except Exception as e:
            self.logger.error(f"解析エラー ({wav_path}): {e}")
            raise

    def create_analysis_json(self, wav_path: Path, features: Dict[str, Any]) -> Dict[str, Any]:
        """解析結果を JSON 形式に整形"""
        # root からの相対パスを取得
        try:
            relative_path = wav_path.relative_to(self.root)
        except ValueError:
            # root の外にある場合は絶対パス
            relative_path = wav_path
        
        analysis_data = {
            "source_wav": str(relative_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "analysis_version": self.analysis_version,
            "features": features
        }
        
        return analysis_data

    def write_json_atomic(self, json_path: Path, data: Dict[str, Any]) -> None:
        """JSON をアトミックに書き込む (temp file -> rename)"""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] 書き込み予定: {json_path}")
            return
        
        # 同じディレクトリに一時ファイルを作成
        json_path.parent.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=json_path.parent,
            prefix=f".{json_path.stem}_",
            suffix='.json.tmp',
            delete=False
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
        
        # アトミックに rename
        tmp_path.replace(json_path)
        self.logger.debug(f"JSON 書き込み完了: {json_path}")

    def process_single_wav(self, wav_path: Path) -> AnalysisResult:
        """単一の WAV ファイルを処理"""
        json_path = wav_path.with_suffix('.json')
        
        try:
            # スキップ判定
            if not self.should_analyze(wav_path):
                self.logger.debug(f"スキップ (既に解析済み): {wav_path}")
                return AnalysisResult(
                    wav_path=wav_path,
                    json_path=json_path,
                    success=True,
                    skipped=True
                )
            
            # 解析実行
            self.logger.info(f"解析中: {wav_path}")
            features = self.analyze_wav(wav_path)
            
            # JSON 作成
            analysis_data = self.create_analysis_json(wav_path, features)
            
            # JSON 書き込み
            self.write_json_atomic(json_path, analysis_data)
            
            return AnalysisResult(
                wav_path=wav_path,
                json_path=json_path,
                success=True
            )
        
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.logger.error(f"処理失敗 ({wav_path}): {error_msg}")
            self.logger.debug(traceback.format_exc())
            
            return AnalysisResult(
                wav_path=wav_path,
                json_path=json_path,
                success=False,
                error_message=error_msg
            )


def process_folder(
    root: Path,
    ext: str = ".wav",
    force: bool = False,
    dry_run: bool = False,
    jobs: int = 1
) -> Dict[str, Any]:
    """
    フォルダ配下の WAV ファイルを解析
    
    Parameters
    ----------
    root : Path
        走査するルートディレクトリ
    ext : str
        対象拡張子
    force : bool
        既存 JSON を上書きするか
    dry_run : bool
        実際には書き込まない (確認用)
    jobs : int
        並列数
    
    Returns
    -------
    Dict[str, Any]
        処理サマリ
    """
    logger = logging.getLogger(__name__)
    
    # WAV ファイルを探す
    analyzer = WavAnalyzer(
        root=root,
        ext=ext,
        force=force,
        dry_run=dry_run
    )
    
    wav_files = analyzer.find_wav_files()
    logger.info(f"発見した WAV ファイル: {len(wav_files)} 個")
    
    if len(wav_files) == 0:
        logger.warning("WAV ファイルが見つかりませんでした")
        return {
            "total_wavs": 0,
            "already_analyzed": 0,
            "newly_analyzed": 0,
            "failed": 0,
            "failed_files": []
        }
    
    # 処理対象を判定
    to_analyze = [f for f in wav_files if analyzer.should_analyze(f)]
    already_done = len(wav_files) - len(to_analyze)
    
    logger.info(f"解析対象: {len(to_analyze)} 個 (スキップ: {already_done} 個)")
    
    if dry_run:
        logger.info("[DRY RUN モード] 実際には書き込みません")
        for wav_path in to_analyze:
            json_path = wav_path.with_suffix('.json')
            logger.info(f"  → {json_path}")
        
        return {
            "total_wavs": len(wav_files),
            "already_analyzed": already_done,
            "newly_analyzed": 0,
            "to_analyze": len(to_analyze),
            "failed": 0,
            "failed_files": []
        }
    
    # 並列処理
    results: List[AnalysisResult] = []
    failed_files: List[tuple] = []
    
    global interrupted
    
    if jobs > 1:
        # ProcessPoolExecutor で並列処理
        logger.info(f"並列処理開始 (jobs={jobs})")
        
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = {
                executor.submit(analyzer.process_single_wav, wav_path): wav_path
                for wav_path in wav_files
            }
            
            for future in as_completed(futures):
                if interrupted:
                    logger.warning("中断シグナルを検出。処理を停止します。")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    if not result.success:
                        failed_files.append((str(result.wav_path), result.error_message))
                except Exception as e:
                    wav_path = futures[future]
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    logger.error(f"予期しないエラー ({wav_path}): {error_msg}")
                    failed_files.append((str(wav_path), error_msg))
    else:
        # シングルスレッド処理
        logger.info("シングルスレッドで処理開始")
        
        for wav_path in wav_files:
            if interrupted:
                logger.warning("中断シグナルを検出。処理を停止します。")
                break
            
            result = analyzer.process_single_wav(wav_path)
            results.append(result)
            
            if not result.success:
                failed_files.append((str(result.wav_path), result.error_message))
    
    # サマリ集計
    total = len(wav_files)
    skipped = sum(1 for r in results if r.skipped)
    succeeded = sum(1 for r in results if r.success and not r.skipped)
    failed = sum(1 for r in results if not r.success)
    
    summary = {
        "total_wavs": total,
        "already_analyzed": skipped,
        "newly_analyzed": succeeded,
        "failed": failed,
        "failed_files": failed_files
    }
    
    return summary


def print_summary(summary: Dict[str, Any]) -> None:
    """処理サマリを表示"""
    print("\n" + "=" * 60)
    print("処理サマリ")
    print("=" * 60)
    print(f"総 WAV ファイル数:     {summary['total_wavs']}")
    print(f"既に解析済み:         {summary['already_analyzed']}")
    print(f"新規解析完了:         {summary['newly_analyzed']}")
    print(f"失敗:                 {summary['failed']}")
    
    if summary.get('to_analyze') is not None:
        print(f"[DRY RUN] 解析予定:   {summary['to_analyze']}")
    
    if summary['failed'] > 0:
        print("\n失敗したファイル:")
        for wav_path, error_msg in summary['failed_files']:
            print(f"  × {wav_path}")
            print(f"    → {error_msg}")
    
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="フォルダ配下の WAV ファイルを再帰的に解析し、JSON を作成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--root',
        type=Path,
        required=True,
        help='走査するルートディレクトリ (必須)'
    )
    
    parser.add_argument(
        '--ext',
        type=str,
        default='.wav',
        help='対象拡張子 (デフォルト: .wav)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際には書き込まず、作る予定の JSON 数と対象ファイルを出力'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='JSON が存在しても上書き再解析'
    )
    
    parser.add_argument(
        '--jobs',
        type=int,
        default=1,
        help='並列数 (デフォルト: 1, 2以上で並列処理)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細なログを出力'
    )
    
    return parser.parse_args()


def setup_logging(verbose: bool = False) -> None:
    """ロギング設定"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )


def main() -> int:
    """メイン処理"""
    args = parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    
    # パイプライン利用可否を確認
    if not HYDRAL_PIPELINE_AVAILABLE:
        logger.warning("Hydral 解析パイプラインが利用できません。フォールバックモードで実行します。")
    
    # Ctrl+C ハンドラ設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # ルートディレクトリの存在確認
    if not args.root.exists():
        logger.error(f"指定されたディレクトリが存在しません: {args.root}")
        return 1
    
    if not args.root.is_dir():
        logger.error(f"指定されたパスはディレクトリではありません: {args.root}")
        return 1
    
    logger.info(f"解析開始: {args.root}")
    
    try:
        summary = process_folder(
            root=args.root,
            ext=args.ext,
            force=args.force,
            dry_run=args.dry_run,
            jobs=args.jobs
        )
        
        print_summary(summary)
        
        # 失敗があった場合は終了コード 1
        return 1 if summary['failed'] > 0 else 0
    
    except KeyboardInterrupt:
        logger.warning("\n中断されました")
        return 130
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        logger.debug(traceback.format_exc())
        return 1


if __name__ == '__main__':
    sys.exit(main())

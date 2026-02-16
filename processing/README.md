# Processing Module

Hydral の音声処理・変換・解析スクリプト集です。

## 利用可能なスクリプト

### analyze_folder_wavs.py

フォルダ配下の `.wav` ファイルを再帰的に走査し、未解析のものを解析して JSON を作成します。

#### 主な機能

- **再帰的走査**: 指定フォルダ配下のすべての WAV ファイルを発見
- **冪等性**: 既に解析済み（JSON が存在）のファイルはスキップ
- **並列処理**: `--jobs` オプションで複数ファイルを並列解析
- **エラー耐性**: 一部のファイルが解析失敗しても処理を継続
- **原子性**: JSON 書き込みは一時ファイル経由で行われ、途中で中断されても破損しない

#### 使用例

基本的な使い方:

```bash
# カレントディレクトリからの相対パスまたは絶対パス
python processing/analyze_folder_wavs.py --root data/raw

# dry-run モードで解析対象を確認
python processing/analyze_folder_wavs.py --root data/raw --dry-run

# 並列処理（4プロセス）
python processing/analyze_folder_wavs.py --root data/raw --jobs 4

# 既存の JSON を上書きして再解析
python processing/analyze_folder_wavs.py --root data/raw --force

# 詳細ログを出力
python processing/analyze_folder_wavs.py --root data/raw --verbose
```

#### 出力形式

各 WAV ファイルと同じ場所に JSON ファイルを作成します:

```
data/raw/
├── recording1.wav
├── recording1.json  ← 新規作成
├── subdir/
│   ├── recording2.wav
│   └── recording2.json  ← 新規作成
```

JSON の構造:

```json
{
  "source_wav": "recording1.wav",
  "created_at": "2026-02-15T08:19:07.936746+00:00",
  "analysis_version": "v1",
  "features": {
    "rms": [0.109, 0.151, ...],
    "low": [0.012, 0.015, ...],
    "mid": [0.045, 0.052, ...],
    "high": [0.023, 0.028, ...],
    "onset": [0.001, 0.003, ...],
    "meta": {
      "sample_rate": 44100,
      "hop_length": 512,
      "num_frames": 44
    }
  }
}
```

#### CLI オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--root` | 走査するルートディレクトリ（必須） | - |
| `--ext` | 対象拡張子 | `.wav` |
| `--dry-run` | 実際には書き込まず、作る予定の JSON 数と対象ファイルを出力 | `False` |
| `--force` | JSON が存在しても上書き再解析 | `False` |
| `--jobs` | 並列数（2以上で並列処理） | `1` |
| `--verbose`, `-v` | 詳細なログを出力 | `False` |

#### 解析パイプライン

1. **Hydral パイプライン**: `pipelines.analysis_pipelines.run_audio_analysis_pipeline` を優先使用
   - RMS エネルギー
   - 周波数帯域エネルギー（低・中・高）
   - オンセット強度
   - 平滑化済み特徴量

2. **フォールバック（librosa）**: Hydral パイプラインが利用できない場合
   - RMS
   - スペクトル重心
   - ゼロ交差率

#### 処理サマリ

実行後に以下のサマリが表示されます:

```
============================================================
処理サマリ
============================================================
総 WAV ファイル数:     10
既に解析済み:         3
新規解析完了:         6
失敗:                 1

失敗したファイル:
  × /path/to/broken.wav
    → NoBackendError: unable to decode audio
============================================================
```

#### 終了コード

- `0`: 成功（失敗なし）
- `1`: 一部のファイルの解析に失敗
- `130`: ユーザーによる中断（Ctrl+C）

#### 技術的な詳細

- **原子的書き込み**: JSON は一時ファイルに書き込んでから rename することで、書き込み途中での中断による破損を防止
- **並列処理**: `ProcessPoolExecutor` を使用して複数の WAV を並列解析
- **シグナルハンドリング**: Ctrl+C を受けた場合、進行中のタスクを完了してから終了
- **大文字小文字の区別なし**: `.wav` と `.WAV` の両方を検出

#### 注意事項

- 既に JSON が存在するファイルは、デフォルトではスキップされます（`--force` で上書き可能）
- 並列処理では各プロセスが独立して動作するため、verbose モードでのログ順序は不定です
- 大量のファイルを処理する場合、メモリ使用量に注意してください（各ファイルは独立して処理されるため通常は問題ありません）

---

### その他のスクリプト

- **band_split/**: 周波数帯域分割（詳細は `band_split/README.md` を参照）
- **export_to_pack.py**: パッケージ化とエクスポート
- **filter_by_tag.py**: タグによるフィルタリング
- その他の処理スクリプト...
